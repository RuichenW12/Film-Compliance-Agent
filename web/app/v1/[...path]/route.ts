/**
 * Server-side proxy from this app's own origin to the API.
 *
 * Deployed, the web app and the API are two Cloud Run services on two
 * hostnames, and a browser calling straight across breaks twice over:
 *
 *  - **CORS.** `WEB_ORIGINS` in `api/main.py` lists localhost only, so every
 *    call from the deployed origin is blocked.
 *  - **IAP.** Its session cookie is scoped to one service. A page served from
 *    the web host calling the API host arrives without the API's cookie and is
 *    answered with a Google sign-in redirect in the middle of a `fetch`, which
 *    surfaces as an opaque failure rather than a login prompt.
 *
 * Routing through this handler fixes both: the browser only ever talks to the
 * origin it loaded from, and this server relays onward with credentials of its
 * own. One origin, one IAP session, no CORS.
 *
 * A `next.config` rewrite would have been less code but cannot work here --
 * rewrites forward the request as-is, and IAP will not accept a request with
 * no credential. Hence a handler that mints one.
 *
 * Locally this file is never reached: `NEXT_PUBLIC_API_BASE` points at the API
 * directly, so the browser calls it and CORS allows the localhost origin.
 */

import { type NextRequest } from "next/server";

/** Where to forward. Runtime configuration, so one image serves anywhere. */
const UPSTREAM = process.env.API_UPSTREAM ?? "";

/**
 * The audience the API's IAP will accept.
 *
 * For a service behind IAP this is the OAuth client ID, not the service URL --
 * a token minted for the URL is rejected. Not a secret: a client ID appears in
 * every sign-in redirect. Empty means "no IAP in front of the upstream", which
 * is the case locally.
 */
const IAP_AUDIENCE = process.env.IAP_AUDIENCE ?? "";

const METADATA_TOKEN_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";

/** Hop-by-hop headers, and ones the upstream must compute for itself. */
const STRIP = new Set([
  "host",
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "content-length",
  // The caller's IAP cookie is for *this* service and means nothing to the
  // upstream. Forwarding it would be noise at best and confusing at worst.
  "cookie",
  "authorization"
]);

/**
 * An identity token for the upstream, from the Cloud Run metadata server.
 *
 * Deliberately not cached. Tokens last an hour and caching would save one
 * local request per call, at the cost of expiry logic that is wrong until the
 * first token expires in production -- the worst place to find out.
 */
async function identityToken(): Promise<string | null> {
  if (!IAP_AUDIENCE) return null;
  const response = await fetch(
    `${METADATA_TOKEN_URL}?audience=${encodeURIComponent(IAP_AUDIENCE)}`,
    { headers: { "Metadata-Flavor": "Google" }, cache: "no-store" }
  );
  if (!response.ok) {
    // Say which half failed. "502 from the API" and "this server cannot prove
    // who it is" are different problems and lead to different fixes.
    console.error(
      `[proxy] metadata server refused an identity token: ${response.status}`
    );
    return null;
  }
  return (await response.text()).trim();
}

async function proxy(request: NextRequest): Promise<Response> {
  if (!UPSTREAM) {
    return Response.json(
      {
        error: {
          code: "PROXY_NOT_CONFIGURED",
          message: "API_UPSTREAM is not set on this deployment."
        }
      },
      { status: 500 }
    );
  }

  const incoming = new URL(request.url);
  const target = `${UPSTREAM}${incoming.pathname}${incoming.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!STRIP.has(key.toLowerCase())) headers.set(key, value);
  });

  const token = await identityToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  const response = await fetch(target, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
    cache: "no-store"
  });

  // A redirect to accounts.google.com means the token was missing or wrong.
  // Passing it back would send the browser off to sign in again for a service
  // it never asked about; naming it is far more useful.
  const location = response.headers.get("location") ?? "";
  if (location.includes("accounts.google.com")) {
    console.error("[proxy] upstream IAP rejected this server's credentials");
    return Response.json(
      {
        error: {
          code: "UPSTREAM_AUTH_FAILED",
          message:
            "The API refused this server's credentials. Check IAP_AUDIENCE " +
            "and that this service account may access the API."
        }
      },
      { status: 502 }
    );
  }

  const passthrough = new Headers(response.headers);
  passthrough.delete("content-encoding");
  passthrough.delete("content-length");
  passthrough.delete("transfer-encoding");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: passthrough
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;

// The proxy must never be prerendered or cached: it carries per-request auth
// and mutating calls.
export const dynamic = "force-dynamic";
