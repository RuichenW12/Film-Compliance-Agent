import { afterEach, describe, expect, it, vi } from "vitest";


describe("Cloud Run API proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("gets the upstream identity token from the Cloud Run metadata endpoint", async () => {
    vi.stubEnv("API_UPSTREAM", "https://api-preview.example");
    vi.stubEnv("IAP_AUDIENCE", "iap-client.apps.googleusercontent.com");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("signed-token"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const { GET } = await import("@/app/v1/[...path]/route");
    const response = await GET(
      new Request("https://web-preview.example/v1/institutions") as never
    );

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://metadata.google.internal/computeMetadata/v1/instance/" +
        "service-accounts/default/identity?audience=" +
        "iap-client.apps.googleusercontent.com"
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      headers: { "Metadata-Flavor": "Google" },
      cache: "no-store",
    });
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://api-preview.example/v1/institutions"
    );
    expect(
      (fetchMock.mock.calls[1]?.[1]?.headers as Headers).get("Authorization")
    ).toBe("Bearer signed-token");
    expect(response.status).toBe(200);
  });
});
