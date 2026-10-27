import os

from fastapi import APIRouter

from ..llm.schema import STUB_ANSWER, EnrichInput, EnrichOutput

router = APIRouter()


@router.post("/enrich", response_model=EnrichOutput)
def enrich(body: EnrichInput) -> EnrichOutput:
    if os.getenv("LLM_STUB") == "1":
        return STUB_ANSWER  # build and debug without spending a single model call
    raise NotImplementedError("model call comes in Stage 2")
