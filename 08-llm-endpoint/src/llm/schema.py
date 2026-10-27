"""The contract, written down before any model is called. Closed lists are enums."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(str, Enum):
    fiction = "fiction"
    poetry = "poetry"
    history = "history"
    science = "science"
    business = "business"
    self_help = "self_help"
    cooking = "cooking"
    travel = "travel"
    biography_memoir = "biography_memoir"
    music = "music"
    religion_spirituality = "religion_spirituality"
    other = "other"


class QualityFlag(str, Enum):
    missing_description = "missing_description"
    very_short_description = "very_short_description"
    truncated_description = "truncated_description"
    promotional_tone = "promotional_tone"
    not_english = "not_english"


class EnrichInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class EnrichOutput(BaseModel):
    """What the endpoint promises to return. Anything else from the model is rejected."""
    model_config = ConfigDict(extra="forbid")
    category: Category
    summary: str = Field(min_length=1, max_length=200)
    quality_flags: list[QualityFlag] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0)


STUB_ANSWER = EnrichOutput(category=Category.other, summary="Stub mode: no model was called.",
                           quality_flags=[], confidence=0.0)
