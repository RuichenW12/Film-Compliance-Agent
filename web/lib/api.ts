import { authHeaders } from "./demoAuth";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";

export type PolicyVerificationStatus = "mock_verified" | "human_verified";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {}
  ) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // fall through to a generic error
    }
    throw new ApiError(
      response.status,
      body?.error.code ?? "UNKNOWN",
      body?.error.message ?? response.statusText,
      body?.error.details ?? {}
    );
  }
  return (await response.json()) as T;
}

export interface NotificationItem {
  notification_id: string;
  user_id: string;
  project_id: string | null;
  kind: string;
  title_key: string;
  body_key: string;
  params: Record<string, unknown>;
  link: string | null;
  read: boolean;
  created_at: string | null;
}

export interface ProjectResponse {
  project: Record<string, unknown> & {
    state?: string;
    policy_stale?: boolean;
    classification: {
      tier?: string;
      tier_provisional?: boolean;
      policy_verification_status: PolicyVerificationStatus;
    } | null;
  };
  counts: { findings_open_block: number; materials_pending: number };
}

export async function getProject(projectId: string): Promise<ProjectResponse> {
  return apiFetch<ProjectResponse>(`/v1/projects/${projectId}`);
}

export async function listNotifications(
  unreadOnly = false
): Promise<NotificationItem[]> {
  const query = unreadOnly ? "?unread_only=true" : "";
  return apiFetch<NotificationItem[]>(`/v1/notifications${query}`);
}

export async function markNotificationRead(
  notificationId: string
): Promise<NotificationItem> {
  return apiFetch<NotificationItem>(
    `/v1/notifications/${notificationId}/read`,
    { method: "POST" }
  );
}

// --------------------------------------------------------------- collection

export interface AssetVersion {
  version_id: string;
  kind: string;
  sha256: string;
  parent_version: string | null;
  uploaded_by: string;
  created_at: string;
}

export interface UploadTicket {
  ticket_id: string;
  upload_url: string;
  method: string;
  backend: string;
  storage_uri: string;
}

export interface MaterialCard {
  material_id: string;
  name_key: string;
  asset_kind: string;
  required: boolean;
  why_clause: { snapshot_version: string; clause_id: string } | null;
  template_uri: string | null;
  common_rejects_key: string | null;
  status: string;
  asset_version: string | null;
  invalid_reasons: string[];
  waive_reason: string | null;
}

export interface FactRecord {
  fact_id: string;
  key: string;
  value: string | number | null;
  status: string;
  source_ref: { type: string; asset_version: string | null; locator: string | null };
}

export interface Finding {
  finding_id: string;
  asset_version: string;
  locator: {
    episode: number | null;
    scene: number | null;
    quote: string;
    line: number | null;
    match_lines: number[];
  };
  category: string;
  severity: string;
  evidence_refs: { snapshot_version: string; clause_id: string }[];
  suggestion: string | null;
  status: string;
}

export interface RoadmapStep {
  idx: number;
  name: string;
  owner: string;
  material_refs: string[];
  status: string;
  est_weeks: number | null;
}

export interface RoadmapView {
  roadmap: {
    template: string;
    steps: RoadmapStep[];
    current_step_idx: number;
    confirmed: boolean;
  } | null;
  state: string | null;
  pending_flags: string[];
}

export interface ExtractResult {
  facts: FactRecord[];
  discarded: string[];
  pending_flags: string[];
  backend: string;
}

export interface ReviewResult {
  findings: Finding[];
  discarded: string[];
  pending_flags: string[];
  backend: string;
  state: string;
}

export async function requestUploadUrl(
  projectId: string,
  kind: string,
  filename?: string
): Promise<UploadTicket> {
  return apiFetch<UploadTicket>(`/v1/projects/${projectId}/assets/upload-url`, {
    method: "POST",
    body: JSON.stringify({ kind, filename: filename ?? null })
  });
}

// Raw bytes, so this one does not go through apiFetch's JSON content type.
export async function uploadBytes(
  uploadUrl: string,
  file: Blob
): Promise<AssetVersion> {
  const response = await fetch(`${API_BASE}${uploadUrl}`, {
    method: "PUT",
    headers: authHeaders(),
    body: file,
    cache: "no-store"
  });
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // fall through
    }
    throw new ApiError(
      response.status,
      body?.error.code ?? "UNKNOWN",
      body?.error.message ?? response.statusText,
      body?.error.details ?? {}
    );
  }
  return (await response.json()) as AssetVersion;
}

export async function listAssets(projectId: string): Promise<AssetVersion[]> {
  return apiFetch<AssetVersion[]>(`/v1/projects/${projectId}/assets`);
}

export async function extractFacts(
  projectId: string,
  versionId: string
): Promise<ExtractResult> {
  return apiFetch<ExtractResult>(
    `/v1/projects/${projectId}/assets/${versionId}/extract-facts`,
    { method: "POST" }
  );
}

export async function listFacts(projectId: string): Promise<FactRecord[]> {
  return apiFetch<FactRecord[]>(`/v1/projects/${projectId}/facts`);
}

export async function listMaterials(projectId: string): Promise<MaterialCard[]> {
  return apiFetch<MaterialCard[]>(`/v1/projects/${projectId}/materials`);
}

export async function attachMaterial(
  projectId: string,
  materialId: string,
  assetVersion: string
): Promise<MaterialCard> {
  return apiFetch<MaterialCard>(
    `/v1/projects/${projectId}/materials/${materialId}/attach`,
    { method: "POST", body: JSON.stringify({ asset_version: assetVersion }) }
  );
}

export async function validateMaterial(
  projectId: string,
  materialId: string
): Promise<MaterialCard> {
  return apiFetch<MaterialCard>(
    `/v1/projects/${projectId}/materials/${materialId}/validate`,
    { method: "POST" }
  );
}

export async function waiveMaterial(
  projectId: string,
  materialId: string,
  reason: string
): Promise<MaterialCard> {
  return apiFetch<MaterialCard>(
    `/v1/projects/${projectId}/materials/${materialId}/waive`,
    { method: "POST", body: JSON.stringify({ reason }) }
  );
}

export async function getRoadmap(projectId: string): Promise<RoadmapView> {
  return apiFetch<RoadmapView>(`/v1/projects/${projectId}/roadmap`);
}

export async function confirmRoadmap(projectId: string): Promise<RoadmapView> {
  return apiFetch<RoadmapView>(`/v1/projects/${projectId}/roadmap/confirm`, {
    method: "POST"
  });
}

export async function runReview(projectId: string): Promise<ReviewResult> {
  return apiFetch<ReviewResult>(`/v1/projects/${projectId}/review`, {
    method: "POST"
  });
}

export async function listFindings(projectId: string): Promise<Finding[]> {
  return apiFetch<Finding[]>(`/v1/projects/${projectId}/findings`);
}

// -------------------------------------------------------------- institution

export interface Institution {
  institution_id: string;
  name: string;
  license_no: string;
  valid_until: string;
  registered_capital_rmb: number;
  has_foreign: boolean;
}

export interface LicenseCheck {
  institution_id: string | null;
  valid_until: string | null;
  capital_ok: boolean | null;
  no_foreign_ok: boolean | null;
  mock: boolean;
  reasons: string[];
}

export interface InstitutionReview {
  review_id: string;
  institution_id: string | null;
  license_check: LicenseCheck | null;
  decision: string;
  return_comments: string | null;
  signed_agreement_uri: string | null;
  decided_at: string | null;
}

export interface ReviewStateResponse {
  review: InstitutionReview;
  state: string;
}

export interface FilingResponse {
  state: string;
  registration_number: string | null;
}

export async function listInstitutions(): Promise<Institution[]> {
  return apiFetch<Institution[]>("/v1/institutions");
}

export async function loadInstitutions(
  institutions: Institution[]
): Promise<Institution[]> {
  return apiFetch<Institution[]>("/v1/admin/institutions", {
    method: "PUT",
    body: JSON.stringify(institutions)
  });
}

export async function submitToInstitution(
  projectId: string,
  institutionId: string
): Promise<ReviewStateResponse> {
  return apiFetch<ReviewStateResponse>(
    `/v1/projects/${projectId}/institution/submit`,
    { method: "POST", body: JSON.stringify({ institution_id: institutionId }) }
  );
}

export async function readReview(
  projectId: string
): Promise<InstitutionReview | null> {
  return apiFetch<InstitutionReview | null>(
    `/v1/projects/${projectId}/institution`
  );
}

export async function decideReview(
  projectId: string,
  body: {
    decision: string;
    return_comments?: string;
    signed_agreement_uri?: string;
  }
): Promise<ReviewStateResponse> {
  return apiFetch<ReviewStateResponse>(
    `/v1/projects/${projectId}/institution/decide`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function resumeAfterReturn(
  projectId: string
): Promise<FilingResponse> {
  return apiFetch<FilingResponse>(
    `/v1/projects/${projectId}/institution/resume`,
    { method: "POST" }
  );
}

export async function recordFiling(
  projectId: string,
  registrationNumber: string
): Promise<FilingResponse> {
  return apiFetch<FilingResponse>(`/v1/projects/${projectId}/filing`, {
    method: "POST",
    body: JSON.stringify({ registration_number: registrationNumber })
  });
}

/** The 备案 form as the product has it so far.
 *
 *  A field is `filled` only where a confirmed fact backs it. `pending` is
 *  unanswered and holds the form shut; `pending_institution` is a gap the
 *  creator declared and the filing company will supply (D-044). Both render
 *  待补充 -- the difference is whether anyone said so on the record. */
export interface FormField {
  value: string | number | null;
  status: "filled" | "pending" | "conflict" | "pending_institution";
  source_ref: { type: string } | null;
  confirmed_at: string | null;
  override_reason: string | null;
}

export interface FormDraft {
  draft_id: string;
  form_type: string;
  frozen: boolean;
  hash: string | null;
  fields: Record<string, FormField>;
  conflicts: { check: string; message_key: string; items: string[] }[];
  snapshot_version: string;
}

export interface GateResult {
  passed: boolean;
  gaps: { check: string; items: string[] }[];
}

export async function getForm(projectId: string): Promise<FormDraft> {
  return apiFetch<FormDraft>(`/v1/projects/${projectId}/form`);
}

export async function getGate(projectId: string): Promise<GateResult> {
  return apiFetch<GateResult>(`/v1/projects/${projectId}/gate`);
}

export async function confirmField(
  projectId: string,
  key: string,
  value: string | number
): Promise<FormDraft> {
  return apiFetch<FormDraft>(
    `/v1/projects/${projectId}/form/fields/${key}/confirm`,
    { method: "POST", body: JSON.stringify({ value }) }
  );
}

/** Declare that the filing institution supplies this one, rather than guessing. */
export async function deferField(
  projectId: string,
  key: string,
  reason: string
): Promise<FormDraft> {
  return apiFetch<FormDraft>(
    `/v1/projects/${projectId}/form/fields/${key}/defer`,
    { method: "POST", body: JSON.stringify({ reason }) }
  );
}

export async function passGate(
  projectId: string
): Promise<{ state: string; passed: boolean }> {
  return apiFetch<{ state: string; passed: boolean }>(
    `/v1/projects/${projectId}/gate/pass`,
    { method: "POST" }
  );
}

export async function freezeForm(projectId: string): Promise<FormDraft> {
  return apiFetch<FormDraft>(`/v1/projects/${projectId}/form/freeze`, {
    method: "POST"
  });
}

/** One row of the institution's inbox.
 *
 *  `title_working` is nullable on purpose: a project whose creator never named
 *  it stays unnamed here rather than borrowing a title from somewhere.
 *  `licence_reasons` is empty when the mock check passed -- there is no `ok`
 *  field, because what a reviewer needs is the reason, not the verdict. */
export interface QueueRow {
  project_id: string;
  title_working: string | null;
  state: string;
  tier: string | null;
  institution_id: string | null;
  review_id: string | null;
  decision: string | null;
  submitted_at: string | null;
  licence_reasons: string[];
}

export async function getInstitutionQueue(
  institutionId?: string
): Promise<QueueRow[]> {
  const query = institutionId
    ? `?institution_id=${encodeURIComponent(institutionId)}`
    : "";
  return apiFetch<QueueRow[]>(`/v1/institution/queue${query}`);
}

/** Re-decide a project whose rules moved. Only valid while it is stale and
 *  before its form has been locked and sent. */
export async function reclassifyProject(
  projectId: string
): Promise<{ classification: { tier: string } | null; state: string }> {
  return apiFetch(`/v1/projects/${projectId}/reclassify`, { method: "POST" });
}

/** One budget band and what it would mean, read from the pinned snapshot.
 *
 *  `statutory_deadline_key` is null for the two classes whose deadline the
 *  regulation does not state — two-class has none, and three-class is platform
 *  self-review rather than an administrative approval. Null means "not stated",
 *  never "fast": rendering it as a blank is the honest reading. */
export interface BudgetBand {
  tier: string;
  amount_bracket: string;
  lower_rmb: number;
  upper_rmb: number;
  authority: string;
  pre_shoot_filing: string;
  blocks_release: boolean;
  steps_yours: number;
  steps_total: number;
  statutory_deadline_key: string | null;
  deadline_clause: string | null;
  clause_refs: string[];
}
