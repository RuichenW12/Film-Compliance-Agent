import { afterEach, describe, expect, it, vi } from "vitest";

import {
  confirmReview,
  createIdeaReview,
  createScriptReview,
  getReview,
  reanalyzeReview,
} from "@/lib/reviews-api";
import { ApiError } from "@/lib/api";


const VIEW = {
  review_id: "review_001",
  state: "AWAITING_CONFIRMATION",
  mode: "script",
  candidates: null,
  confirmed: null,
  intake_status: "complete",
  semantic_status: null,
  source_filename: "demo.md",
  source_sha256: "abc",
  source_download_url: "/v1/reviews/review_001/source",
  amount_options: [],
  classification: null,
  findings: [],
  artifacts: [],
};


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


describe("reviews API client", () => {
  it("lets the browser set the multipart boundary for a script upload", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(VIEW)));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["# Demo"], "demo.md", { type: "text/markdown" });

    await createScriptReview(file);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8080/v1/reviews");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const body = init.body as FormData;
    expect(body.get("mode")).toBe("script");
    expect(body.get("script")).toBe(file);
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
    expect(headers["X-Mock-Role"]).toBe("creator");
  });

  it("creates idea mode without attaching a placeholder file", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      json({ ...VIEW, mode: "idea", source_filename: null })
    );
    vi.stubGlobal("fetch", fetchMock);

    await createIdeaReview();

    const body = fetchMock.mock.calls[0][1]?.body as FormData;
    expect(body.get("mode")).toBe("idea");
    expect(body.has("script")).toBe(false);
  });

  it("recovers and confirms a review through the facade endpoints", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(VIEW)));
    vi.stubGlobal("fetch", fetchMock);
    const details = {
      title: "Demo",
      tags: ["family"],
      synopsis: "A short synopsis.",
      episode_count: 10,
      episode_minutes: 3,
      amount_bracket: "between" as const,
    };

    await getReview("review_001");
    await confirmReview("review_001", details);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8080/v1/reviews/review_001"
    );
    const confirm = fetchMock.mock.calls[1];
    expect(confirm[0]).toBe(
      "http://localhost:8080/v1/reviews/review_001/confirm"
    );
    expect(JSON.parse(String(confirm[1]?.body))).toEqual(details);
    expect((confirm[1]?.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json"
    );
  });

  it("posts edited confirmation details to an encoded reanalysis URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ ...VIEW, state: "COMPLETE" }));
    vi.stubGlobal("fetch", fetchMock);
    const details = {
      title: "Edited",
      tags: ["family"],
      synopsis: "An edited synopsis.",
      episode_count: 12,
      episode_minutes: 2,
      amount_bracket: "between" as const,
    };

    await reanalyzeReview("review/with space", details);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://localhost:8080/v1/reviews/review%2Fwith%20space/reanalyze"
    );
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(details);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json"
    );
  });

  it("decodes the stable error envelope for reanalysis", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "STATE_INVALID",
              message: "review is not complete",
              details: { state: "ANALYZING" },
            },
          }),
          {
            status: 409,
            statusText: "Conflict",
            headers: { "Content-Type": "application/json" },
          }
        )
      )
    );
    const details = {
      title: "Edited",
      tags: ["family"],
      synopsis: "An edited synopsis.",
      episode_count: 12,
      episode_minutes: 2,
      amount_bracket: "between" as const,
    };

    const error = await reanalyzeReview("review_001", details).catch(
      (caught: unknown) => caught
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "STATE_INVALID",
      message: "review is not complete",
      details: { state: "ANALYZING" },
    });
  });

  it("falls back safely when an error response is a malformed JSON object", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ unexpected: true }), {
          status: 502,
          statusText: "Bad Gateway",
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    const details = {
      title: "Edited",
      tags: ["family"],
      synopsis: "An edited synopsis.",
      episode_count: 12,
      episode_minutes: 2,
      amount_bracket: "between" as const,
    };

    const error = await reanalyzeReview("review_001", details).catch(
      (caught: unknown) => caught
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 502,
      code: "UNKNOWN",
      message: "Bad Gateway",
      details: {},
    });
  });
});
