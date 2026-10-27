import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..llm.client import LLMConfigError, LLMTimeout, LLMUnavailable
from ..llm.enrich import Unrepairable, enrich as run_enrich, fallback
from ..llm.schema import STUB_ANSWER, EnrichInput, EnrichOutput

router = APIRouter()


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


@router.post("/enrich", response_model=EnrichOutput,
             responses={400: {"description": "Invalid input (field named)"},
                        422: {"description": "Model answer failed the schema, even after one repair"},
                        502: {"description": "Provider config error (bad key / model)"},
                        503: {"description": "Provider unavailable"},
                        504: {"description": "Model timed out"}})
def enrich(body: EnrichInput):
    if os.getenv("LLM_STUB") == "1":
        return STUB_ANSWER  # build and debug without spending a single model call
    if os.getenv("LLM_ENABLED", "true").lower() in ("false", "0", "no", "off"):
        return fallback(body)  # kill switch: someone who is not me can turn the model off without a deploy
    try:
        return run_enrich(body)  # always a validated EnrichOutput: raw model text never reaches the caller
    except Unrepairable as exc:
        return error(422, "unprocessable_model_output",
                     f"The model's answer did not match the schema after one repair attempt ({exc}).")
    except LLMTimeout as exc:
        return error(504, "model_timeout", str(exc))
    except LLMUnavailable as exc:
        return error(503, "model_unavailable", str(exc))
    except LLMConfigError as exc:
        return error(502, "model_config_error", str(exc))
