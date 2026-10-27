"""LLM integration: one narrow job (categorise a title), schema-validated, repaired once, cost-logged, cached by hash."""
import hashlib
import json
import logging
import re
import time
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config, db

log = logging.getLogger("shelfwatch.llm")
PROMPT_VERSION = "categorise-v1"
SYSTEM_PROMPT = (config.BASE / "prompts" / f"{PROMPT_VERSION}.md").read_text("utf-8")


class Category(str, Enum):
    fiction = "fiction"; poetry = "poetry"; history = "history"; science = "science"; business = "business"  # noqa: E702
    self_help = "self_help"; cooking = "cooking"; travel = "travel"; biography_memoir = "biography_memoir"  # noqa: E702
    music = "music"; religion_spirituality = "religion_spirituality"; children = "children"; other = "other"  # noqa: E702


class Enrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category
    summary: str = Field(min_length=1, max_length=200)
    confidence: float = Field(ge=0, le=1)


# --- offline demo mode (LLM_STUB=1): keyword rules, clearly not AI, so the app runs with no key at all
STUB_RULES = [
    ("poetry", ("poem", "poetry", "verse", "sonnet")), ("cooking", ("recipe", "cook", "kitchen", "meal")),
    ("history", ("history", "historical", "war", "century", "1936", "olympics")), ("music", ("band", "music", "punk", "song")),
    ("science", ("science", "physics", "biology", "humankind", "brain")), ("business", ("business", "startup", "money")),
    ("self_help", ("habit", "self", "agreements", "happiness", "productivity")), ("travel", ("travel", "journey", "trip")),
    ("biography_memoir", ("memoir", "biography", "life of", "autobiography")), ("children", ("children", "kids", "picture book")),
    ("religion_spirituality", ("god", "faith", "spiritual", "prayer")), ("fiction", ("novel", "fiction", "mystery", "romance", "thriller")),
]


def stub_enrich(title: str, description: str | None) -> Enrichment:
    text = f"{title} {description or ''}".lower()
    short = title if len(title) <= 120 else title[:117] + "..."  # long titles must still fit the 200-char summary
    for category, words in STUB_RULES:
        if any(w in text for w in words):
            return Enrichment(category=category, summary=f"{short} (categorised by keyword rules).", confidence=0.4)
    return Enrichment(category="other", summary=f"{short} (no keyword matched).", confidence=0.1)


def content_hash(title: str, description: str | None) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}|{title}|{description or ''}".encode()).hexdigest()


def parse(text: str | None) -> tuple[Enrichment | None, str | None]:
    try:
        cleaned = re.sub(r"```(?:json)?", "", text or "").strip()
        obj, _ = json.JSONDecoder().raw_decode(cleaned[cleaned.index("{"):])
        return Enrichment.model_validate(obj), None
    except ValueError as exc:  # no "{", bad JSON
        return None, f"not valid JSON: {exc}"
    except ValidationError as exc:
        return None, "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())


def llm_enrich(title: str, description: str | None, client=None) -> Enrichment | None:
    from openai import OpenAI
    client = client or OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
                              timeout=config.LLM_TIMEOUT_S, max_retries=1)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Input: " + json.dumps({"title": title, "description": (description or "")[:2000]})}]
    for repair in (0, 1):  # one try + exactly one repair
        t0 = time.monotonic()
        res = client.chat.completions.create(model=config.LLM_MODEL, messages=messages, temperature=0)
        raw = res.choices[0].message.content
        result, error = parse(raw)
        usage = getattr(res, "usage", None)
        log.info(json.dumps({"event": "llm_call", "prompt_version": PROMPT_VERSION, "model": config.LLM_MODEL,
                             "input_tokens": getattr(usage, "prompt_tokens", None),
                             "output_tokens": getattr(usage, "completion_tokens", None),
                             "duration_ms": round((time.monotonic() - t0) * 1000), "repair": repair,
                             "outcome": "ok" if result else "invalid"}))
        if result:
            return result
        messages += [{"role": "assistant", "content": raw or ""},
                     {"role": "user", "content": f"Your answer was rejected: {error}. Return only corrected JSON."}]
    return None  # never store something that failed the schema


def enrich_books(book_ids: list[int], client=None) -> dict:
    """Categorise books. Results are cached by a hash of (prompt version, title, description):
    an unchanged title is never sent to the model twice."""
    stats = {"cached": 0, "enriched": 0, "failed": 0}
    for book_id in book_ids:
        with db.tx() as conn:
            book = conn.execute("SELECT title, description FROM books WHERE id=?", (book_id,)).fetchone()
            existing = conn.execute("SELECT content_hash FROM enrichments WHERE book_id=?", (book_id,)).fetchone()
        if book is None:
            continue
        h = content_hash(book["title"], book["description"])
        if existing and existing["content_hash"] == h:
            stats["cached"] += 1
            continue
        try:
            result = stub_enrich(book["title"], book["description"]) if config.LLM_STUB else llm_enrich(
                book["title"], book["description"], client)
        except Exception as exc:  # provider down: the scan still succeeds, enrichment is retried next scan
            log.warning("enrichment failed for book %s: %s", book_id, exc)
            result = None
        if result is None:
            stats["failed"] += 1
            continue
        with db.tx() as conn:
            conn.execute("""INSERT OR REPLACE INTO enrichments (book_id, content_hash, category, summary, confidence,
                            model, prompt_version, created_at) VALUES (?,?,?,?,?,?,?,?)""",
                         (book_id, h, result.category.value, result.summary, result.confidence,
                          "stub-keyword-rules" if config.LLM_STUB else config.LLM_MODEL, PROMPT_VERSION, db.now()))
        stats["enriched"] += 1
    log.info("enrichment: %s", stats)
    return stats
