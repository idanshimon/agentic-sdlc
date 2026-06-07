# Build the Next.js standalone bundle from the repo root.
# Single builder stage (avoids pnpm node_modules cross-stage hash mismatch),
# then a slim runtime stage with the standalone output.
FROM node:22-alpine AS builder
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@11.1.2 --activate
COPY apps/ledger-insights-ui ./apps/ledger-insights-ui
WORKDIR /repo/apps/ledger-insights-ui
ENV NEXT_TELEMETRY_DISABLED=1 CI=true
# pnpm 11 CI hardening — explicitly allow native build scripts (sharp, unrs-resolver).
# --dangerously-allow-all-builds is the documented escape hatch for CI/Docker.
RUN pnpm install --config.dangerously-allow-all-builds=true --frozen-lockfile=false --prod=false
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
# Next.js standalone output lays out the runtime at the ROOT of .next/standalone
# (server.js is .next/standalone/server.js, not nested under the app dir).
COPY --from=builder /repo/apps/ledger-insights-ui/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/apps/ledger-insights-ui/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/ledger-insights-ui/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
