// Mirror of schemas/enums.py (API contract v1 section 2).
// Whoever changes one changes the other in the same PR.

export const PROJECT_STATES = [
  "DRAFT",
  "INTAKE_DONE",
  "FORM_JUDGED",
  "CLASSIFIED",
  "ROADMAP_CONFIRMED",
  "COLLECTING_MATERIALS",
  "REVIEW_RUNNING",
  "REVISION_LOOP",
  "GATE_D3_PASSED",
  "FORM_FROZEN",
  "INSTITUTION_REVIEW",
  "INSTITUTION_RETURNED",
  "READY_FOR_EXTERNAL_FILING",
  "FILED",
  "PRODUCTION",
  "NEEDS_HUMAN_FORMTYPE",
  "NEEDS_HUMAN_SUBJECT",
  "EXIT_NON_DRAMA",
  "EXIT_T2",
  "EXIT_T3",
  "EXIT_SISTER_PATH"
] as const;
export type ProjectState = (typeof PROJECT_STATES)[number];

export const TIERS = ["T1", "T2", "T3", "undetermined"] as const;
export type Tier = (typeof TIERS)[number];

export const FORM_TYPES = [
  "micro_drama",
  "web_film",
  "non_drama",
  "undetermined"
] as const;
export type FormType = (typeof FORM_TYPES)[number];

export const BUDGET_BANDS = ["band_a", "band_b", "band_c", "unknown"] as const;
export type BudgetBand = (typeof BUDGET_BANDS)[number];

export const FINDING_SEVERITIES = [
  "block",
  "co_review_required",
  "caution",
  "pass",
  "needs_human"
] as const;
export type FindingSeverity = (typeof FINDING_SEVERITIES)[number];

export const ALERT_OPTIONS = [
  "A_keep_and_coreview",
  "B_modify",
  "C_escalate"
] as const;
export type AlertOption = (typeof ALERT_OPTIONS)[number];
