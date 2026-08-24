import { afterEach, describe, expect, it, vi } from "vitest";

import {
  PolicyApiError,
  discardProposal,
  listPendingProposals,
  publishProposal,
  startCrawl,
} from "@/lib/policy-api";


const SOURCE_ID = "nrta_micro_drama";


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


describe("policy API client", () => {
  it("sends the admin role and decodes a crawl", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run_001" }), { status: 202 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(startCrawl(SOURCE_ID)).resolves.toEqual({
      run_id: "run_001",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8080/v1/admin/policy/crawl",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-Mock-Role": "admin",
        }),
        body: JSON.stringify({ source_id: SOURCE_ID }),
      }),
    );
  });

  it("requests only pending proposals", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listPendingProposals()).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8080/v1/admin/policy/proposals?status=pending",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("accepts an empty discard response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(discardProposal("proposal_001")).resolves.toBeUndefined();
  });

  it("turns the stable error envelope into PolicyApiError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "POLICY_NOT_EFFECTIVE",
            message: "proposal is not effective yet",
            details: {},
          },
        }),
        { status: 409 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const promise = publishProposal("proposal_001");

    await expect(promise).rejects.toBeInstanceOf(PolicyApiError);
    await expect(promise).rejects.toMatchObject({
      code: "POLICY_NOT_EFFECTIVE",
      message: "proposal is not effective yet",
      details: {},
      status: 409,
    });
  });
});
