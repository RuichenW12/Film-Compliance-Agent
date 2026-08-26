import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import WizardPage from "@/app/wizard/page";


function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


describe("WizardPage", () => {
  it("submits an exact RMB investment amount", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ project_id: "proj_001", state: "DRAFT" }))
      .mockResolvedValueOnce(json({ state: "INTAKE_DONE", missing: [] }))
      .mockResolvedValueOnce(json({ tracks_enabled: { china: true, us: false } }))
      .mockResolvedValueOnce(
        json({
          classification: {
            form_type: "micro_drama",
            tier: "T2",
            tier_provisional: false,
            special_subject_hit: false,
            co_review_required: false,
            matched_rules: [],
            policy_snapshot_version: "v2",
            pending_flags: [],
            evidence_refs: []
          },
          exit: null,
          roadmap_preview: { template: "T2_5steps" },
          state: "CLASSIFIED"
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<WizardPage />);
    await user.type(screen.getByLabelText("Logline"), "A workplace romance.");
    await user.type(
      screen.getByLabelText("Investment amount (RMB)"),
      "1500000"
    );
    await user.click(
      screen.getByRole("button", { name: "Run classification" })
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    const intent = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    expect(intent.investment_amount_rmb).toBe(1_500_000);
  });
});
