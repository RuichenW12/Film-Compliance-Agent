import { authHeaders } from "./demoAuth";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";

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
  locator: { episode: number | null; scene: number | null; quote: string };
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
