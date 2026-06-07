# Build the Next.js standalone bundle from the monorepo root.
#
# CRITICAL — two build-time traps governed by openspec/changes/add-ledger-insights-ui-deploy/:
#   1. NEXT_PUBLIC_* must be set as ENV BEFORE `pnpm build` (Next inlines at
#      build time; runtime env vars are ignored for those keys).
#   2. openspec/ must be COPY'd into the runtime image — the /changes route
#      reads openspec/changes/ from disk at request time. Build context MUST
#      be the monorepo root, not apps/ledger-insights-ui/.
#
# Build context: . (monorepo root). Filtered by /.dockerignore.

# ------------------------------ builder ------------------------------
FROM node:22-alpine AS builder
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

# Copy the app sources (workspace files live inside apps/ledger-insights-ui/).
COPY apps/ledger-insights-ui ./apps/ledger-insights-ui

# NEXT_PUBLIC_* build args — passed by scripts/build-ledger-insights-ui.sh.
# Defaults make local `docker build` produce a working Demo Mode image
# without explicit args.
ARG NEXT_PUBLIC_DEMO_MODE=1
ARG NEXT_PUBLIC_ORCHESTRATOR_URL=https://ca-orchestrator.placeholder.eastus2.azurecontainerapps.io
ARG NEXT_PUBLIC_LEDGER_MCP_URL=https://ca-ledger-mcp.placeholder.eastus2.azurecontainerapps.io

WORKDIR /repo/apps/ledger-insights-ui

# Set as ENV so `pnpm build` sees them. THIS IS THE TRAP — without these
# ENV lines, NEXT_PUBLIC_* are not visible to next build and the bundle
# ships with `undefined`.
ENV NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE \
    NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL \
    NEXT_PUBLIC_LEDGER_MCP_URL=$NEXT_PUBLIC_LEDGER_MCP_URL \
    NEXT_TELEMETRY_DISABLED=1 \
    CI=true

# pnpm 11 CI hardening — explicitly allow native build scripts (sharp, unrs-resolver).
RUN pnpm install --config.dangerously-allow-all-builds=true --frozen-lockfile=false --prod=false

RUN pnpm build

# ------------------------------ runner ------------------------------
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

# Next.js standalone output lays out the runtime at the ROOT of .next/standalone
# (server.js is .next/standalone/server.js, not nested under the app dir).
COPY --from=builder /repo/apps/ledger-insights-ui/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/apps/ledger-insights-ui/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/ledger-insights-ui/.next/static ./.next/static

# /changes reads openspec/changes/ from disk at request time. The Next.js
# server runs from /app, so openspec/ must live at /app/openspec/.
COPY --chown=nextjs:nodejs openspec ./openspec

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
