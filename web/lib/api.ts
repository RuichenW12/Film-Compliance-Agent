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
