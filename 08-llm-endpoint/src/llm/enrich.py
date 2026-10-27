"""validate input -> build prompt -> call model -> parse + validate -> repair once -> clean JSON or a clear 422."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

from .client import complete, make_client, model_name
from .prompt import PROMPT_VERSION, system_prompt, user_message
from .schema import EnrichInput, EnrichOutput

QUARANTINE = Path(__file__).resolve().parents[2] / "logs" / "quarantine.jsonl"


class Unrepairable(Exception):
    """The model's answer failed the schema twice (original + one repair) -> 422."""


def extract_json(text: str | None) -> dict:
    """Models like ```json fences and 'Sure! Here's the JSON:'. Strip all that and parse the first object."""
    if not text or not text.strip():
        raise ValueError("empty answer (possibly a refusal)")
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object found in the answer")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("answer is JSON but not an object")
    return obj


def check(text: str | None) -> tuple[EnrichOutput | None, str | None]:
    """Parse + validate. Returns (result, None) or (None, a readable error for the repair prompt)."""
    try:
        return EnrichOutput.model_validate(extract_json(text)), None
    except (ValueError, json.JSONDecodeError) as exc:
        return None, f"not valid JSON: {exc}"
    except ValidationError as exc:
        return None, "; ".join(f"{'.'.join(map(str, e['loc'])) or 'object'}: {e['msg']}" for e in exc.errors())


def quarantine(inp: EnrichInput, raw: str | None, error: str) -> None:
    QUARANTINE.parent.mkdir(parents=True, exist_ok=True)
    with QUARANTINE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "prompt_version": PROMPT_VERSION, "model": model_name(),
                             "input": inp.model_dump(), "raw_output": raw, "error": error}, ensure_ascii=False) + "\n")


def enrich(inp: EnrichInput, client: OpenAI | None = None) -> EnrichOutput:
    client = client or make_client()
    messages = [{"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_message(inp.title, inp.description)}]

    res, _ = complete(client, messages)
    raw = res.choices[0].message.content
    result, error = check(raw)
    if result is not None:
        return result

    # Repair retry: exactly one. Hand the model its own broken answer and the exact validation error.
    repair_messages = messages + [
        {"role": "assistant", "content": raw or ""},
        {"role": "user", "content": f"Your previous answer was rejected for this reason: {error}. "
                                    "Return only corrected JSON matching the schema."},
    ]
    res, _ = complete(client, repair_messages)
    raw2 = res.choices[0].message.content
    result, error2 = check(raw2)
    if result is not None:
        return result

    quarantine(inp, raw2, f"first: {error} | after repair: {error2}")
    raise Unrepairable(error2)
