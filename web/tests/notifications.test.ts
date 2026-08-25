import { afterEach, describe, expect, it, vi } from "vitest";

import { listNotifications, markNotificationRead } from "@/lib/api";
import { format } from "@/lib/i18n";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const ITEM = {
  notification_id: "ntf_001",
  user_id: "u_demo",
  project_id: "prj_001",
  kind: "tier_recalculated",
  title_key: "notification.tier_recalculated.title",
  body_key: "notification.tier_recalculated.body",
  params: { snapshot_version: "v2", tier: "T3", previous_tier: "T3" },
  link: "/dashboard?project=prj_001",
  read: false,
  created_at: "2026-08-24T12:00:00+00:00"
};

describe("notification client", () => {
  it("reads the inbox with the demo role headers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([ITEM]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listNotifications()).resolves.toEqual([ITEM]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8080/v1/notifications");
    expect(init.headers["X-Mock-Role"]).toBeDefined();
  });

  it("asks only for unread when told to", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await listNotifications(true);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8080/v1/notifications?unread_only=true"
    );
  });

  it("posts a read receipt", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...ITEM, read: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(markNotificationRead("ntf_001")).resolves.toMatchObject({
      read: true
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8080/v1/notifications/ntf_001/read"
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });
});

describe("message rendering", () => {
  it("fills the params the API sent", () => {
    expect(format(ITEM.body_key, ITEM.params)).toBe(
      "Snapshot v2 moved this project from T3 to T3."
    );
  });

  it("leaves an unsupplied placeholder visible rather than undefined", () => {
    expect(format(ITEM.body_key, { snapshot_version: "v2" })).toContain(
      "{tier}"
    );
  });
});
