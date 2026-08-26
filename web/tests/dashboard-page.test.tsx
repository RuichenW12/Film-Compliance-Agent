import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/dashboard/page";


function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


describe("DashboardPage", () => {
  it("shows the pinned mock-policy warning", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(
        json({
          project: {
            state: "CLASSIFIED",
            policy_stale: false,
            classification: {
              tier: "T2",
              tier_provisional: false,
              policy_verification_status: "mock_verified",
            },
          },
          counts: { findings_open_block: 0, materials_pending: 2 },
        }),
      )
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(json({ passed: false, gaps: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<DashboardPage />);
    await user.type(screen.getByLabelText("Project id"), "proj_001");
    await user.click(screen.getByRole("button", { name: "Load" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /integration data/i,
    );
  });
});
