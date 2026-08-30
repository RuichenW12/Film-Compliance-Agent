import type { NextConfig } from "next";

/* The API base the browser uses.
 *
 * Locally this is the API on another port and the browser calls it directly;
 * `WEB_ORIGINS` in `api/main.py` allows that origin through CORS.
 *
 * Deployed it is empty: an empty base makes the browser call the page own
 * origin, where the route handler below relays to the API. */
const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  /* Emit a self-contained server plus only the dependencies it imports, so
   * the runtime image does not carry node_modules. Required by
   * `infra/web.Dockerfile`. */
  output: "standalone",

  env: {
    NEXT_PUBLIC_API_BASE: apiBase
  },

  /* No rewrite for /v1/*. `app/v1/[...path]/route.ts` handles it instead.
   *
   * A rewrite forwards the request untouched, and the deployed API sits behind
   * IAP, which rejects a request carrying no credential. The route handler
   * exists to mint one. Everything else about the arrangement -- one origin
   * for the browser, no CORS, one IAP session -- is the same either way. */
};

export default nextConfig;
