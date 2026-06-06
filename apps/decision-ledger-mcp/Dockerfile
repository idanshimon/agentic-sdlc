# syntax=docker/dockerfile:1.7
# multi-stage: install deps, build TS, copy dist into slim runtime
FROM node:20-alpine AS builder
WORKDIR /build
COPY package*.json tsconfig.json ./
RUN npm ci --omit=optional
COPY src ./src
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
RUN apk add --no-cache tini
COPY package*.json ./
RUN npm ci --omit=dev --omit=optional
COPY --from=builder /build/dist ./dist
# bundles are mounted at /app/standards-bundles by Container App volume
ENV STANDARDS_BUNDLES_ROOT=/app/standards-bundles
EXPOSE 3001
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/server.js", "--transport", "http", "--port", "3001"]
