"""Shared enumerations (API contract v1 section 2).

Front-end mirror lives in web/lib/enums.ts; whoever changes one changes both.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectState(StrEnum):
    DRAFT = "DRAFT"
    INTAKE_DONE = "INTAKE_DONE"
    FORM_JUDGED = "FORM_JUDGED"
    CLASSIFIED = "CLASSIFIED"
    ROADMAP_CONFIRMED = "ROADMAP_CONFIRMED"
    COLLECTING_MATERIALS = "COLLECTING_MATERIALS"
    REVIEW_RUNNING = "REVIEW_RUNNING"
    REVISION_LOOP = "REVISION_LOOP"
    GATE_D3_PASSED = "GATE_D3_PASSED"
    FORM_FROZEN = "FORM_FROZEN"
    INSTITUTION_REVIEW = "INSTITUTION_REVIEW"
    INSTITUTION_RETURNED = "INSTITUTION_RETURNED"
    READY_FOR_EXTERNAL_FILING = "READY_FOR_EXTERNAL_FILING"
    FILED = "FILED"
    PRODUCTION = "PRODUCTION"
    NEEDS_HUMAN_FORMTYPE = "NEEDS_HUMAN_FORMTYPE"
    NEEDS_HUMAN_SUBJECT = "NEEDS_HUMAN_SUBJECT"
    EXIT_NON_DRAMA = "EXIT_NON_DRAMA"
    EXIT_T2 = "EXIT_T2"
    EXIT_T3 = "EXIT_T3"
    EXIT_SISTER_PATH = "EXIT_SISTER_PATH"


TERMINAL_STATES: frozenset[ProjectState] = frozenset(
    {
        ProjectState.EXIT_NON_DRAMA,
        ProjectState.EXIT_T2,
        ProjectState.EXIT_T3,
        ProjectState.EXIT_SISTER_PATH,
    }
)


class Phase(StrEnum):
    PRE_SHOOT = "PRE_SHOOT"
    PRODUCTION = "PRODUCTION"
    FINAL_REVIEW = "FINAL_REVIEW"


class FormType(StrEnum):
    MICRO_DRAMA = "micro_drama"
    WEB_FILM = "web_film"
    NON_DRAMA = "non_drama"
    UNDETERMINED = "undetermined"


class ClaimedFormType(StrEnum):
    MICRO_DRAMA = "micro_drama"
    WEB_FILM = "web_film"
    SINGLE_VIDEO = "single_video"
    ANIME = "anime"
    UNKNOWN = "unknown"


class Tier(StrEnum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    UNDETERMINED = "undetermined"


class ProductionStage(StrEnum):
    """How far along the work is, and it decides what the product asks for.

    Not idle curiosity twice over. 总局令第16号 article 12 requires a one-class
    filing *before* production starts, so someone whose work is already made is
    not early -- they are late, and the product should say so rather than hand
    them a roadmap beginning with a step they have passed.

    And it governs the interface. At `IDEA` a creator has a premise and nothing
    else: no budget, no episode count, no running time. Asking anyway produced a
    form that demanded answers nobody at that stage has, so the stage now
    decides which questions are worth putting.

    `SHOOTING` was removed when the product narrowed to AI micro-dramas: there
    is no camera, so there is no state between having a script and having a
    finished work. `FINISHED` became `PRODUCTION_COMPLETE` for the same reason
    -- what is finished is the production, not a shoot.
    """

    IDEA = "idea"
    SCRIPT_READY = "script_ready"
    PRODUCTION_COMPLETE = "production_complete"
    UNKNOWN = "unknown"


class AmountBracket(StrEnum):
    """Where the budget sits relative to the tier thresholds.

    Replaces `BudgetBand`, whose `band_a/b/c` were invented before any threshold
    was published and could only ever produce a provisional tier (D-003). These
    are defined *by* the thresholds, so answering one is enough to settle a tier
    without naming a figure: "under the lower line" decides three-class as
    surely as a number would.

    Deliberately threshold-relative rather than numeric, because the numbers
    differ by production mode -- 1,000,000 and 3,000,000 for live action,
    300,000 and 800,000 for AI. One enum, resolved against whichever set applies;
    the interface shows the figures.
    """

    BELOW_LOWER = "below_lower"
    BETWEEN = "between"
    AT_OR_ABOVE_UPPER = "at_or_above_upper"
    UNKNOWN = "unknown"


class FindingSeverity(StrEnum):
    BLOCK = "block"
    CO_REVIEW_REQUIRED = "co_review_required"
    CAUTION = "caution"
    PASS = "pass"
    NEEDS_HUMAN = "needs_human"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SELF_FIXED = "self_fixed"
    RESOLVED = "resolved"
    WAIVED = "waived"


class AlertOption(StrEnum):
    A_KEEP_AND_COREVIEW = "A_keep_and_coreview"
    B_MODIFY = "B_modify"
    C_ESCALATE = "C_escalate"


class MaterialStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    WAIVED = "waived"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class TaskType(StrEnum):
    FACT_EXTRACT = "fact_extract"
    REVIEW_FULL = "review_full"
    REVIEW_INCREMENTAL = "review_incremental"
    FORM_GENERATE = "form_generate"
    TEASER = "teaser"
    POLICY_CRAWL = "policy_crawl"
    US_RESEARCH = "us_research"


class FieldStatus(StrEnum):
    FILLED = "filled"
    PENDING = "pending"
    CONFLICT = "conflict"
    PENDING_INSTITUTION = "pending_institution"


class InstitutionDecision(StrEnum):
    ACCEPT = "accept"
    RETURN = "return"
    ESCALATE = "escalate"
    PENDING = "pending"


class NotificationKind(StrEnum):
    REVIEW_DONE = "review_done"
    GATE_READY = "gate_ready"
    POLICY_STALE = "policy_stale"
    TIER_RECALCULATED = "tier_recalculated"
    INSTITUTION_RETURNED = "institution_returned"
    TASK_FAILED = "task_failed"


class Role(StrEnum):
    CREATOR = "creator"
    INSTITUTION = "institution"
    ADMIN = "admin"


class Actor(StrEnum):
    SYSTEM = "system"
    CREATOR = "creator"
    INSTITUTION = "institution"
    ADMIN = "admin"
    USER = "user"


class AssetKind(StrEnum):
    SYNOPSIS = "synopsis"
    SCRIPT = "script"
    SUPPORTING_DOCUMENT = "supporting_document"
    PROMPTS = "prompts"
    FINAL_FILM = "final_film"
    SUBTITLE_SHEET = "subtitle_sheet"


class FactStatus(StrEnum):
    CONFIRMED = "confirmed"
    CONFLICT = "conflict"
    PENDING_INSTITUTION = "pending_institution"


class SourceRefType(StrEnum):
    ASSET = "asset"
    USER_ANSWER = "user_answer"
    INSTITUTION = "institution"


class Regime(StrEnum):
    CURRENT = "current"
    FROM_2026_09_01 = "from_2026_09_01"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    GATE_BLOCKED = "GATE_BLOCKED"
    STATE_INVALID = "STATE_INVALID"
    UPSTREAM_LLM_ERROR = "UPSTREAM_LLM_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    UNSUPPORTED_SCRIPT_TYPE = "UNSUPPORTED_SCRIPT_TYPE"
    UNREADABLE_SCRIPT = "UNREADABLE_SCRIPT"
    SCRIPT_TOO_LARGE = "SCRIPT_TOO_LARGE"


class ExitKind(StrEnum):
    EXIT_NON_DRAMA = "EXIT_NON_DRAMA"
    EXIT_SISTER_PATH = "EXIT_SISTER_PATH"
    EXIT_T2 = "EXIT_T2"
    EXIT_T3 = "EXIT_T3"
