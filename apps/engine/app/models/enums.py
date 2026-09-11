import enum


class DocumentType(str, enum.Enum):
    CIRCULAR = "CIRCULAR"
    MASTER_CIRCULAR = "MASTER_CIRCULAR"
    NOTIFICATION = "NOTIFICATION"
    LAW = "LAW"
    RULE = "RULE"
    GUIDELINE = "GUIDELINE"
    AMENDMENT = "AMENDMENT"


class OcrStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class ClauseType(str, enum.Enum):
    """What kind of text this requirement row captures.
    Document != rule: a document has more than just rules."""

    RULE = "RULE"
    DEFINITION = "DEFINITION"
    EXCEPTION = "EXCEPTION"
    PROCEDURE = "PROCEDURE"
    TABLE_DATA = "TABLE_DATA"
    AMENDMENT_TEXT = "AMENDMENT_TEXT"


class RequirementStatus(str, enum.Enum):
    """AI output starts as DRAFT. A human must approve before ACTIVE.
    SUPERSEDED / REPEALED rows are never deleted."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REPEALED = "REPEALED"


class RelationshipType(str, enum.Enum):
    AMENDS = "AMENDS"
    REPLACES = "REPLACES"
    PARTIALLY_REPLACES = "PARTIALLY_REPLACES"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"
    CLARIFIES = "CLARIFIES"
    REPEALS = "REPEALS"


class ScopeType(str, enum.Enum):
    INCLUDES = "INCLUDES"
    EXCLUDES = "EXCLUDES"


class ChangeType(str, enum.Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    REPEALED = "REPEALED"
    MOVED = "MOVED"


class ObligationFrequency(str, enum.Enum):
    ONE_TIME = "ONE_TIME"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    CONTINUOUS = "CONTINUOUS"


class ExtractionRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ReviewDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CORRECTED = "CORRECTED"
