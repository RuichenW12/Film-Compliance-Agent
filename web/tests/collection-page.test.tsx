import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import CollectionPage from "@/app/collection/page";


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


describe("CollectionPage", () => {
  it("shows mock verification and attaches the latest matching asset", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/projects/proj_001/assets")) {
        return json([
          {
            version_id: "script-1",
            kind: "script",
            sha256: "a".repeat(64),
            parent_version: null,
            uploaded_by: "u_owner",
            created_at: "2026-08-26T00:00:00Z",
          },
          {
            version_id: "synopsis-1",
            kind: "synopsis",
            sha256: "b".repeat(64),
            parent_version: null,
            uploaded_by: "u_owner",
            created_at: "2026-08-26T00:01:00Z",
          },
        ]);
      }
      if (url.endsWith("/v1/projects/proj_001/materials")) {
        return json([
          {
            material_id: "mat_synopsis",
            name_key: "material.synopsis",
            asset_kind: "synopsis",
            required: true,
            why_clause: null,
            template_uri: null,
            common_rejects_key: null,
            status: "pending",
            asset_version: null,
            invalid_reasons: [],
            waive_reason: null,
          },
        ]);
      }
      if (url.endsWith("/v1/projects/proj_001/facts")) return json([]);
      if (url.endsWith("/v1/projects/proj_001/findings")) return json([]);
      if (url.endsWith("/v1/projects/proj_001/roadmap")) {
        return json({ roadmap: null, state: "CLASSIFIED", pending_flags: [] });
      }
      if (url.endsWith("/v1/projects/proj_001/form")) {
        return json({
          draft_id: "draft-1",
          form_type: "micro_drama",
          frozen: false,
          hash: null,
          fields: {},
          conflicts: [],
          snapshot_version: "v2",
        });
      }
      if (url.endsWith("/v1/projects/proj_001/gate")) {
        return json({ passed: false, gaps: [] });
      }
      if (url.endsWith("/v1/projects/proj_001")) {
        return json({
          project: {
            classification: {
              policy_verification_status: "mock_verified",
            },
          },
          counts: { findings_open_block: 0, materials_pending: 1 },
        });
      }
      if (url.includes("/materials/mat_synopsis/attach")) {
        expect(JSON.parse(String(init?.body))).toEqual({
          asset_version: "synopsis-1",
        });
        return json({});
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<CollectionPage />);
    await user.type(screen.getByLabelText("Project id"), "proj_001");
    await user.click(screen.getByRole("button", { name: "Load" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /integration data/i,
    );
    const synopsisCard = screen
      .getByText("Synopsis", { selector: "strong" })
      .closest("li");
    expect(synopsisCard).not.toBeNull();
    await user.click(
      within(synopsisCard!).getByRole("button", {
        name: "Attach latest matching asset",
      }),
    );
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/materials/mat_synopsis/attach"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
