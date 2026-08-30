// Locked decision 2: there is no real auth. The role switcher writes a role
// here and every request carries it. Replacing this file with a real identity
// provider is the whole migration path.

export type DemoRole = "creator" | "institution" | "admin";

const ROLE_KEY = "fca.demoRole";
const USER_KEY = "fca.demoUserId";

export const DEFAULT_ROLE: DemoRole = "creator";
export const DEFAULT_USER_ID = "u_demo";

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

export function getRole(): DemoRole {
  const stored = browserStorage()?.getItem(ROLE_KEY);
  return stored === "institution" || stored === "admin" || stored === "creator"
    ? stored
    : DEFAULT_ROLE;
}

export function setRole(role: DemoRole): void {
  browserStorage()?.setItem(ROLE_KEY, role);
}

export function getUserId(): string {
  return browserStorage()?.getItem(USER_KEY) ?? DEFAULT_USER_ID;
}

export function setUserId(userId: string): void {
  browserStorage()?.setItem(USER_KEY, userId);
}

// The API contract names this header X-Mock-Role; X-User-Id identifies the actor.
export function authHeaders(): Record<string, string> {
  return { "X-Mock-Role": getRole(), "X-User-Id": getUserId() };
}
