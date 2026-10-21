from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

CognitiveDomainLiteral = Literal[
    "Hyperarousal / Anxiety",
    "Depressive / Melancholic",
    "Agitation / Irritability",
    "Cognitive / Delirium",
    "Obsessive / Fastidious",
    "Social / Attachment",
    "Somatic Threat / Fear",
    "Sleep / Dreams",
    "None",
]


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
    symptom_raw: str = Field(description="One discrete atomic symptom, verbatim wording")
    canonical_label: str | None = Field(
        default=None,
        description="Short normalized concept label, e.g. 'Fear of Death', 'Restlessness', 'Burning Pains'",
    )
    location_raw: list[str] = Field(default_factory=list)
    sensation_raw: list[str] = Field(default_factory=list)
    laterality: Literal["right", "left", "both", "alternating", "unspecified"] = "unspecified"
    modalities: list[ModalityOut] = Field(default_factory=list)
    concomitants_raw: list[str] = Field(default_factory=list)
    causes_raw: list[str] = Field(
        default_factory=list,
        description="Etiology/triggers or preceding symptoms (e.g. 'fright', 'grief', 'cold drinks')",
    )
    clinical_conditions: list[str] = Field(
        default_factory=list,
        description="Named nosological/clinical conditions if any (e.g. 'Asthma', 'Neuralgia', 'Croup')",
    )
    severity_modifiers: list[str] = Field(
        default_factory=list,
        description="Intensity adjectives verbatim from text (e.g. 'great', 'violent', 'extreme', 'slight')",
    )
    cognitive_domain: CognitiveDomainLiteral = Field(
        default="None",
        description="For mental/affective/dream symptoms, primary cognitive-affective domain",
    )
    emphasis: Literal["plain", "italic", "bold", "caps"] = "plain"
    evidence_type: Literal["proving", "clinical", "toxicology", "unspecified"] = "unspecified"
    symptom_kind_hint: Literal["mental", "affective", "dream", "physical", "general", "clinical", "unknown"] = "unknown"
    onset_raw: str | None = Field(default=None, description="Timing/onset if stated, e.g. 'aft. 4 h.'")
    prover_raw: str | None = Field(default=None, description="Prover attribution if stated, e.g. 'Kr.'")
    evidence_quote: str = Field(description="Verbatim substring of chunk, <= 400 chars")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class GeneralModalityOut(BaseModel):
    modality: ModalityOut
    emphasis: Literal["plain", "italic", "bold", "caps"] = "plain"
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


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


class ChunkExtraction(BaseModel):
    symptoms: list[SymptomOut] = Field(default_factory=list)
    general_modalities: list[GeneralModalityOut] = Field(default_factory=list)
    relationships: list[RelationshipOut] = Field(default_factory=list)
    intro: RemedyIntroOut | None = None
    notes: str | None = Field(default=None, description="Ambiguities or omissions for review")
