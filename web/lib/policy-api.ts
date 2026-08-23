export type ImpactNode = "D1c" | "C1-a";
export type ProposalStatus = "pending" | "published" | "discarded";
export type RunStatus =
  | "running"
  | "no_change"
  | "proposal_created"
  | "failed";

export interface CrawlResponse {
  run_id: string;
}

export interface PolicyRun {
  run_id: string;
  source_id: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  previous_sha256: string | null;
  current_sha256: string | null;
  proposal_id: string | null;
  error: string | null;
}

export interface ProposalSummary {
  proposal_id: string;
  summary: string;
  impact: ImpactNode[];
  effective_from: string;
  status: ProposalStatus;
}

export interface ProposalDetail extends ProposalSummary {
  source_diff_uri: string;
  source_diff_text: string;
  draft_pack_updates: Record<string, Record<string, unknown>>;
  published_version: string | null;
}

export interface PublishResponse {
  snapshot_version: string;
}

export interface SnapshotSummary {
  version: string;
  published_at: string;
  effective_from: string;
  published_by: string;
  thresholds_published: boolean;
}

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export class PolicyApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown>,
    public readonly status: number,
  ) {
    super(message);
    this.name = "PolicyApiError";
  }
}

const API_BASE =
  process.env.NEXT_PUBLIC_POLICY_API_BASE_URL ?? "http://127.0.0.1:8000";

async function decodePolicyError(response: Response): Promise<PolicyApiError> {
  try {
    const payload = (await response.json()) as ErrorEnvelope;
    if (payload.error?.code && payload.error.message) {
      return new PolicyApiError(
        payload.error.code,
        payload.error.message,
        payload.error.details ?? {},
        response.status,
      );
    }
  } catch {
    // Fall through to a safe generic transport error.
  }
  return new PolicyApiError(
    "POLICY_API_ERROR",
    `policy API request failed (${response.status})`,
    {},
    response.status,
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Mock-Role": "admin",
    },
  });
  if (!response.ok) {
    throw await decodePolicyError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function startCrawl(sourceId: string): Promise<CrawlResponse> {
  return request("/v1/admin/policy/crawl", {
    method: "POST",
    body: JSON.stringify({ source_id: sourceId }),
  });
}

export function getRun(runId: string): Promise<PolicyRun> {
  return request(`/v1/admin/policy/runs/${encodeURIComponent(runId)}`);
}

export function listPendingProposals(): Promise<ProposalSummary[]> {
  return request("/v1/admin/policy/proposals?status=pending");
}

export function getProposal(proposalId: string): Promise<ProposalDetail> {
  return request(
    `/v1/admin/policy/proposals/${encodeURIComponent(proposalId)}`,
  );
}

export function publishProposal(
  proposalId: string,
): Promise<PublishResponse> {
  return request(
    `/v1/admin/policy/proposals/${encodeURIComponent(proposalId)}/publish`,
    { method: "POST" },
  );
}

export function discardProposal(proposalId: string): Promise<void> {
  return request(
    `/v1/admin/policy/proposals/${encodeURIComponent(proposalId)}/discard`,
    { method: "POST" },
  );
}

export function listSnapshots(): Promise<SnapshotSummary[]> {
  return request("/v1/admin/policy/snapshots");
}
