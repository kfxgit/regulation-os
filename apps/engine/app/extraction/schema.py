"""The Pydantic extraction contract: what Claude must return, enforced
before any AI output is trusted (see CLAUDE.md section 4, "AI is not the
source of truth").

Where the five confidence scores come from (they don't all live here):
  - confidence_extraction      -- self-reported by Claude in this contract
  - confidence_classification  -- self-reported by Claude in this contract
  - confidence_interpretation  -- self-reported by Claude in this contract
  - confidence_source_match    -- computed later by OUR fuzzy-match code
                                   (app/extraction/verification.py), never
                                   self-reported -- the AI doesn't get to
                                   grade its own citation accuracy
  - confidence_applicability   -- belongs to ApplicabilityRule, Phase 2
                                   scope (the applicability engine), not
                                   produced by this contract

No defaults on confidence or high-risk fields: if Claude's response is
missing one, Pydantic validation fails loudly rather than the field
silently becoming 0.0 or False (see "NO SILENT DEFAULTS").
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClauseType, DocumentType, ObligationFrequency


class ExtractedObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(min_length=1, description="Who must act, e.g. 'Banks', 'Microfinance Banks'.")
    action: str = Field(min_length=1, description="The verb phrase describing what must be done.")
    object: str = Field(min_length=1, description="The thing the action is performed on or with.")
    frequency: Optional[ObligationFrequency] = Field(
        default=None,
        description="How often this recurs, only if explicitly stated. Null if not stated -- never guess.",
    )
    deadline_description: Optional[str] = Field(
        default=None,
        description="The deadline exactly as stated in the source. Null if no deadline is stated -- never invent one.",
    )
    source_quote: str = Field(
        min_length=1,
        description="Exact verbatim text from the source this obligation is based on.",
    )
    confidence_extraction: float = Field(ge=0, le=1)
    confidence_classification: float = Field(ge=0, le=1)


class ExtractedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_type: ClauseType
    requirement_text: str = Field(
        min_length=1,
        description="The requirement restated clearly but faithfully -- not a summary that drops conditions or exceptions.",
    )
    source_quote: str = Field(
        min_length=1,
        description="Exact verbatim text from the source page this requirement is based on. Must be an exact substring of the source text.",
    )
    effective_date: Optional[date] = Field(
        default=None, description="Effective date if explicitly stated. Null if not stated."
    )
    contains_high_risk_language: bool = Field(
        description=(
            "True if this clause contains money, percentages, dates, deadlines, thresholds, "
            "or prohibition language (e.g. 'must not', 'shall not exceed'). These get extra "
            "human review before they can become ACTIVE."
        )
    )
    high_risk_notes: Optional[str] = Field(
        default=None,
        description="If contains_high_risk_language is true, briefly say what the high-risk element is.",
    )
    confidence_extraction: float = Field(ge=0, le=1)
    confidence_classification: float = Field(ge=0, le=1)
    confidence_interpretation: float = Field(
        ge=0,
        le=1,
        description="Confidence in what this clause means/requires, separate from confidence in copying the text correctly.",
    )
    obligations: list[ExtractedObligation] = Field(
        default_factory=list,
        description="Zero or more obligations this requirement creates. Definitions and pure exceptions typically have zero. Leave empty if none -- never invent one to fill this field.",
    )


class PageExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: list[ExtractedRequirement] = Field(default_factory=list)


class ExtractedDocumentMetadata(BaseModel):
    """For batch ingestion: read off a document's own first page instead
    of requiring it typed in by hand for every file.

    reference_number and issue_date are Optional -- if a document
    genuinely doesn't state one clearly, that's a fact, not something to
    guess (see "no silent defaults"). The caller must treat a null here
    as "needs manual input", never invent a value to fill the DB's
    NOT NULL columns.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, description="The document's title or subject line.")
    reference_number: Optional[str] = Field(
        default=None,
        description="The official reference/circular number, e.g. 'BPRD Circular No. 01 of 2019'. Null if not clearly stated.",
    )
    issue_date: Optional[date] = Field(
        default=None, description="The date the document was issued, as stated on the document. Null if not clearly stated."
    )
    document_type: DocumentType
    confidence_extraction: float = Field(ge=0, le=1)
