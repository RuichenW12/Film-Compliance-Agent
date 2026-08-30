# The Next.js front end.
#
# Two stages so the runtime image does not carry the toolchain or
# node_modules: `next build` with `output: "standalone"` emits a server plus
# exactly the dependencies it imports, which is a fraction of the install.

FROM node:22-slim AS build
WORKDIR /app

# Dependencies first, so a change to a page does not reinstall them.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./

# Baked in at build time, not read at runtime. `NEXT_PUBLIC_*` values are
# substituted into the client bundle by `next build`, so this cannot be set by
# a Cloud Run environment variable afterwards.
#
# It is empty on purpose: an empty base makes the browser call the page's own
# origin, and `next.config.ts` rewrites `/v1/*` to the API server-side. One
# origin means one IAP session and no CORS. See the rewrite for why that
# matters.
ENV NEXT_PUBLIC_API_BASE=""
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
# No `public/` copy: this app has none. Its favicon is a route (`/icon.svg`)
# rather than a static file, so there is nothing to carry over. Add the copy
# back the moment a static asset appears -- a missing public/ is a silent 404,
# not a build failure.

# Cloud Run supplies PORT and does not promise 3000. A container listening on a
# fixed port is marked unhealthy and never receives traffic.
ENV PORT=3000 HOSTNAME=0.0.0.0
EXPOSE 3000
CMD ["node", "server.js"]
