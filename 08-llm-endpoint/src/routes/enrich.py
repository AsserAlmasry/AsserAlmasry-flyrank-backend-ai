import os

from fastapi import APIRouter

from ..llm.client import make_client, model_name
from ..llm.prompt import system_prompt, user_message
from ..llm.schema import STUB_ANSWER, EnrichInput, EnrichOutput

router = APIRouter()


@router.post("/enrich")
def enrich(body: EnrichInput):
    if os.getenv("LLM_STUB") == "1":
        return STUB_ANSWER  # build and debug without spending a single model call
    res = make_client().chat.completions.create(
        model=model_name(),
        temperature=0,  # same input -> same answer; this is classification, not creative writing
        messages=[{"role": "system", "content": system_prompt()},
                  {"role": "user", "content": user_message(body.title, body.description)}],
    )
    return {"raw": res.choices[0].message.content}  # Stage 2 only: raw text, made trustworthy in Stage 3
