import { API_BASE, ApiError, type ApiErrorBody } from "./api";
import { authHeaders } from "./demoAuth";


export type ReviewState =
  | "UPLOADING"
  | "EXTRACTING"
  | "AWAITING_CONFIRMATION"
  | "ANALYZING"
  | "COMPLETE"
  | "FAILED";
export type ReviewMode = "script" | "idea";
export type AmountBracket =
  | "below_lower"
  | "between"
  | "at_or_above_upper";

export interface CandidateValue {
  value: string | number | string[];
  origin: "extracted" | "suggested";
  confidence: number | null;
  source_quote: string | null;
  explanation: string | null;
}

export interface CandidateReviewDetails {
  title: CandidateValue | null;
  tags: CandidateValue | null;
  synopsis: CandidateValue | null;
  episode_count: CandidateValue | null;
  episode_minutes: CandidateValue | null;
  amount_bracket: CandidateValue | null;
  structure: {
    source_episode_count: number | null;
    source_total_minutes: number | null;
    source_scene_count: number;
  } | null;
}

export interface ConfirmedReviewDetails {
  title: string;
  tags: string[];
  synopsis: string;
  episode_count: number;
  episode_minutes: number;
  amount_bracket: AmountBracket;
}

export interface ReviewAmountOption {
  value: AmountBracket;
  label: string;
  lower_rmb: number;
  upper_rmb: number;
}

export interface ReviewClassification {
  class_name: string;
  co_review_required: boolean;
  subjects: string[];
  snapshot_version: string;
  evidence_refs: { snapshot_version: string; clause_id: string }[];
  route: Record<string, unknown> | null;
}

export interface ReviewFinding {
  risk_id: string;
  episode: number | null;
  scene: number | null;
  quote: string;
  category: string;
  status: string;
  evidence_refs: { snapshot_version: string; clause_id: string }[];
  explanation: string | null;
  suggestion: string | null;
}

export interface ReviewArtifactLink {
  artifact_type: "form" | "summary" | "annotated-script";
  filename: string;
  download_url: string;
}

export interface ReviewView {
  review_id: string;
  state: ReviewState;
  mode: ReviewMode;
  candidates: CandidateReviewDetails | null;
  confirmed: ConfirmedReviewDetails | null;
  intake_status: "not_started" | "running" | "complete" | "partial" | "unavailable";
  semantic_status: "complete" | "pending" | null;
  source_filename: string | null;
  source_sha256: string | null;
  source_download_url: string | null;
  amount_options: ReviewAmountOption[];
  classification: ReviewClassification | null;
  findings: ReviewFinding[];
  artifacts: ReviewArtifactLink[];
}


async function reviewRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // The stable error object below covers non-JSON proxy failures.
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


export function createScriptReview(file: File): Promise<ReviewView> {
  const body = new FormData();
  body.set("mode", "script");
  body.set("script", file);
  return reviewRequest<ReviewView>("/v1/reviews", { method: "POST", body });
}

export function createIdeaReview(): Promise<ReviewView> {
  const body = new FormData();
  body.set("mode", "idea");
  return reviewRequest<ReviewView>("/v1/reviews", { method: "POST", body });
}

export function getReview(reviewId: string): Promise<ReviewView> {
  return reviewRequest<ReviewView>(`/v1/reviews/${encodeURIComponent(reviewId)}`);
}

export function confirmReview(
  reviewId: string,
  details: ConfirmedReviewDetails
): Promise<ReviewView> {
  return reviewRequest<ReviewView>(
    `/v1/reviews/${encodeURIComponent(reviewId)}/confirm`,
    { method: "POST", body: JSON.stringify(details) }
  );
}

export function retryReviewIntake(reviewId: string): Promise<ReviewView> {
  return reviewRequest<ReviewView>(
    `/v1/reviews/${encodeURIComponent(reviewId)}/retry-intake`,
    { method: "POST" }
  );
}

export function reviewDownloadUrl(path: string): string {
  return `${API_BASE}${path}`;
}
