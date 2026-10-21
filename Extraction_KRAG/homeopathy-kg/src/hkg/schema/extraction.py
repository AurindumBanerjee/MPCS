from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class ModalityOut(BaseModel):
    direction: Literal["worse", "better"]
    factor_raw: str = Field(description="Verbatim text, e.g. 'after midnight', 'warm drinks'")
    factor_type: Literal[
        "time",
        "temperature",
        "weather",
        "position",
        "motion",
        "touch_pressure",
        "food_drink",
        "eating",
        "sleep",
        "emotion",
        "company",
        "season",
        "other",
    ] = "other"


class SymptomOut(BaseModel):
    symptom_raw: str = Field(description="One discrete symptom, verbatim wording")
    location_raw: list[str] = Field(default_factory=list)
    sensation_raw: list[str] = Field(default_factory=list)
    laterality: Literal["right", "left", "both", "alternating", "unspecified"] = "unspecified"
    modalities: list[ModalityOut] = Field(default_factory=list)
    concomitants_raw: list[str] = Field(default_factory=list)
    emphasis: Literal["plain", "italic", "bold", "caps"] = "plain"
    evidence_type: Literal["proving", "clinical", "toxicology", "unspecified"] = "unspecified"
    symptom_kind_hint: Literal["mental", "physical", "general", "clinical", "unknown"] = "unknown"
    evidence_quote: str = Field(description="Verbatim substring of chunk, <= 400 chars")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, values: Any) -> Any:
        """Groq API may return null for empty list fields; coerce to []."""
        if isinstance(values, dict):
            for key in ("location_raw", "sensation_raw", "modalities", "concomitants_raw"):
                if key in values and values[key] is None:
                    values[key] = []
        return values


class GeneralModalityOut(BaseModel):
    modality: ModalityOut
    emphasis: Literal["plain", "italic", "bold", "caps"] = "plain"
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_modality(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # If LLM returned flattened modality fields directly
            if "modality" not in values and ("factor_raw" in values or "direction" in values):
                modality_dict = {
                    "direction": values.pop("direction", "worse"),
                    "factor_raw": values.pop("factor_raw", ""),
                    "factor_type": values.pop("factor_type", "other"),
                }
                values["modality"] = modality_dict
            if not values.get("evidence_quote") and isinstance(values.get("modality"), dict):
                values["evidence_quote"] = values["modality"].get("factor_raw", "")
        return values


class RelationshipOut(BaseModel):
    type: Literal["compare", "antidote", "complementary", "follows_well", "inimical", "similar"]
    remedy_raw: str
    note_raw: str | None = None


class RemedyIntroOut(BaseModel):
    latin_name: str | None = None
    common_names: list[str] = Field(default_factory=list)
    abbreviations: list[str] = Field(default_factory=list)
    kingdom: Literal["plant", "mineral", "animal", "nosode", "other", "unknown"] = "unknown"
    constitution_note: str | None = None
    evidence_quote: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, values: Any) -> Any:
        if isinstance(values, dict):
            for key in ("common_names", "abbreviations"):
                if key in values and values[key] is None:
                    values[key] = []
        return values


class ChunkExtraction(BaseModel):
    symptoms: list[SymptomOut] = Field(default_factory=list)
    general_modalities: list[GeneralModalityOut] = Field(default_factory=list)
    relationships: list[RelationshipOut] = Field(default_factory=list)
    intro: RemedyIntroOut | None = None
    notes: str | None = Field(default=None, description="Ambiguities or omissions for review")

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, values: Any) -> Any:
        """Groq API returns explicit null for empty list fields; coerce to []."""
        if isinstance(values, dict):
            for key in ("symptoms", "general_modalities", "relationships"):
                if key in values and values[key] is None:
                    values[key] = []
        return values
