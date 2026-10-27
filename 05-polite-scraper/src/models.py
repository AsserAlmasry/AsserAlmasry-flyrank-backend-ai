"""The record schema (Pydantic) and the normalization that turns raw strings into clean values."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_price(text: str | None) -> float | None:
    """'£51.77' -> 51.77 (Decimal first, so no float rounding surprises from the string)."""
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text.replace(",", ""))
    if not m:
        return None
    try:
        return float(Decimal(m.group()))
    except InvalidOperation:
        return None


def parse_available_count(text: str | None) -> int | None:
    m = re.search(r"\((\d+) available\)", text or "")
    return int(m.group(1)) if m else None


class Book(BaseModel):
    """A finished, trusted record. Anything that does not fit goes to errors.json instead."""
    model_config = ConfigDict(extra="forbid")

    # identity + provenance
    product_url: str = Field(pattern=r"^https://books\.toscrape\.com/catalogue/[^\s]+/index\.html$")
    source_page: str = Field(pattern=r"^https://books\.toscrape\.com/")
    fetched_at: datetime

    # raw values (kept side by side with the clean ones)
    title: str = Field(min_length=1)
    price_text: str
    availability_text: str
    rating_text: Literal["One", "Two", "Three", "Four", "Five"]
    description: str | None = None

    # clean values
    price_gbp: float = Field(gt=0, lt=10_000)
    in_stock: bool
    available_count: int | None = Field(default=None, ge=0)
    rating: int = Field(ge=1, le=5)

    @field_validator("description")
    @classmethod
    def empty_description_is_none(cls, v: str | None) -> str | None:
        return v if v and v.strip() else None


def normalize(raw: dict) -> dict:
    """Add the clean fields next to the raw ones. Does not validate; Book(**...) does that."""
    avail = raw.get("availability_text") or ""
    return {
        **raw,
        "price_gbp": parse_price(raw.get("price_text")),
        "in_stock": avail.lower().startswith("in stock"),
        "available_count": parse_available_count(avail),
        "rating": RATINGS.get(raw.get("rating_text") or ""),
    }
