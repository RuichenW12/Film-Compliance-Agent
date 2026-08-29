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

/** Where the budget sits relative to the tier thresholds, not a fixed figure.
 *
 *  The thresholds differ by production mode — 1,000,000 and 3,000,000 for live
 *  action, 300,000 and 800,000 for AI — so the bracket is relative and the
 *  interface fills in the numbers from whichever set applies. */
export const AMOUNT_BRACKETS = [
  "unknown",
  "below_lower",
  "between",
  "at_or_above_upper"
] as const;
export type AmountBracket = (typeof AMOUNT_BRACKETS)[number];

/** The figures behind each bracket, by production mode.
 *
 *  Duplicated from the snapshot so the dropdown can name real amounts, which is
 *  the difference between a question a creator can answer and one they cannot.
 *  If a future notice moves a threshold this goes stale — the tier itself is
 *  computed server-side from the pinned snapshot and stays correct, but these
 *  labels would need updating with it. */
export const BRACKET_LABELS: Record<
  Exclude<AmountBracket, "unknown">,
  string
> = {
  below_lower: "Under ¥300,000",
  between: "¥300,000 – ¥800,000",
  at_or_above_upper: "¥800,000 or more"
};

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
