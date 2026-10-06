"""The Pydantic extraction contract: what Claude must return, enforced
before any AI output is trusted (see CLAUDE.md section 4, "AI is not the
source of truth").

CLAUDE.md section 4's confidence-score principle isn't one fixed list of
five columns on every table -- each table carries whichever scores have a
real, distinct meaning for it:
  - RegulatoryRequirement: extraction, source_match, classification,
    interpretation (four -- applicability was dropped as a column here;
    see below)
  - RegulatoryRelationship / ApplicabilityRule: extraction, classification,
    source_match (three -- applicability would be circular on a table
    whose entire row IS the applicability judgment, and interpretation
    doesn't add anything beyond extraction for a single reference/scope
    value)

Where each score comes from (they don't all live in this file):
  - confidence_extraction      -- self-reported by Claude in this contract
                                   (all tables)
  - confidence_classification  -- self-reported by Claude in this contract
                                   (all tables: clause_type /
                                   relationship_type / scope_type)
  - confidence_interpretation  -- self-reported by Claude in this contract
                                   (RegulatoryRequirement only)
  - confidence_source_match    -- computed later by OUR fuzzy-match code
                                   (app/extraction/verification.py), never
                                   self-reported -- the AI doesn't get to
                                   grade its own citation accuracy (all
                                   tables; requirements match against the
                                   page's raw OCR text, relationships/
                                   applicability rules match against the
                                   parent requirement_text they were
                                   derived from)

RegulatoryRequirement.confidence_applicability and
Obligation.confidence_applicability existed since Phase 0 but were never
populated by any extraction code -- confirmed 0/387 and 0/337 rows
non-null before removing them (2026-10-06). ApplicabilityRule's own
confidence_extraction, on its own table, does that job now: one score per
scoping rule, not one aggregate column on the parent.

No defaults on confidence or high-risk fields: if Claude's response is
missing one, Pydantic validation fails loudly rather than the field
silently becoming 0.0 or False (see "NO SILENT DEFAULTS").
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClauseType, DocumentType, ObligationFrequency, RelationshipType, ScopeType


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


class ExtractedRelationship(BaseModel):
    """One document-to-document relationship claimed by a clause (usually
    an AMENDMENT_TEXT one). A single clause can name several documents at
    once (a master circular superseding six prior letters, say), so the
    caller collects these into a list, not a single value.

    target_document_reference is the referenced document exactly as
    named in the text -- resolving that to an actual Document row (or
    recording it as external, if we don't hold that document) happens
    later, in app/extraction/relationships.py, never here. This contract
    only captures what the clause says.
    """

    model_config = ConfigDict(extra="forbid")

    target_document_reference: str = Field(
        min_length=1,
        description="The referenced document exactly as named in the text, e.g. 'BSD Circular No. 05 dated February 14, 2008'.",
    )
    relationship_type: RelationshipType
    confidence_extraction: float = Field(ge=0, le=1)
    confidence_classification: float = Field(
        ge=0,
        le=1,
        description="Confidence that relationship_type is the correct classification (e.g. AMENDS vs SUPERSEDES vs REFERENCES), separate from confidence in having found a reference at all.",
    )


class ExtractedRelationships(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationships: list[ExtractedRelationship] = Field(
        default_factory=list,
        description="Every document this clause references as amended/replaced/superseded/etc. Empty if the clause does not reference another document.",
    )


class ExtractedApplicabilityRule(BaseModel):
    """Who/what one clause says it applies to (or explicitly doesn't).
    Resolving entity_type/product_type/business_activity against our
    taxonomy tables (or keeping them as unresolved text) happens later,
    in app/extraction/applicability_resolver.py, never here.

    At least one of entity_type/product_type/business_activity/
    condition_text must be set -- an empty rule with nothing scoped
    carries no information and should not be extracted.
    """

    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeType
    entity_type: Optional[str] = Field(
        default=None,
        description="Who this applies to, exactly as named (e.g. 'Banks', 'DFIs', 'Islamic Banking Subsidiaries'). Null if this rule does not scope by entity type.",
    )
    product_type: Optional[str] = Field(
        default=None,
        description="What product this applies to, exactly as named (e.g. 'Digital Wallet', 'BNPL'). Null if this rule does not scope by product.",
    )
    business_activity: Optional[str] = Field(
        default=None,
        description="What business activity this applies to, exactly as named (e.g. 'Cross-border remittance'). Null if this rule does not scope by activity.",
    )
    condition_text: Optional[str] = Field(
        default=None,
        description="Any additional qualifying condition beyond entity/product/activity, exactly as stated (e.g. 'with majority foreign shareholding greater than 50%', 'sold through digital channels'). Null if none.",
    )
    confidence_extraction: float = Field(ge=0, le=1)
    confidence_classification: float = Field(
        ge=0,
        le=1,
        description="Confidence that scope_type (INCLUDES vs EXCLUDES) is correct, separate from confidence in having found a scoping statement at all.",
    )


class ExtractedApplicabilityRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[ExtractedApplicabilityRule] = Field(
        default_factory=list,
        description="Every applicability scoping this clause states (who/what it applies to, or is explicitly excluded from). Empty if the clause states no scoping at all.",
    )
