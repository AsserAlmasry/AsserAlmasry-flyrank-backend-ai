import json
from functools import lru_cache
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
PROMPT_VERSION = "enrich-v1"


@lru_cache
def system_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"{version}.md").read_text("utf-8")


def user_message(title: str, description: str | None) -> str:
    # Untrusted content goes in the USER message, JSON-encoded so it cannot break out of its own quotes.
    return "Input: " + json.dumps({"title": title, "description": description}, ensure_ascii=False)
