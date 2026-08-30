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
  it("submits classification inputs without inventing an exact amount", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ project_id: "proj_001", state: "DRAFT" }))
      .mockResolvedValueOnce(json({ state: "INTAKE_DONE", missing: [] }))
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
            policy_verification_status: "mock_verified",
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
    const synopsis = screen
      .getByText("What happens")
      .closest("label")!
      .querySelector("textarea")!;
    await user.type(synopsis, "A workplace romance.");
    expect(synopsis).toHaveValue("A workplace romance.");
    await user.click(
      screen.getByRole("button", { name: "Run classification" })
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(screen.getByRole("alert")).toHaveTextContent(/integration data/i);
    const intent = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    expect(intent.synopsis).toBe("A workplace romance.");
    expect(intent.amount_bracket).toBe("unknown");
    expect(intent).not.toHaveProperty("investment_amount_rmb");
    expect(intent.is_ai_generated).toBe(true);
  });
});
