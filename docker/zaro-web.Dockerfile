# syntax=docker/dockerfile:1
# =============================================================================
# ZARO Web (Next.js) - production image
# =============================================================================

FROM node:22-alpine AS base

WORKDIR /repo

# Pin the exact pnpm release used to generate pnpm-lock.yaml (same as CI);
# corepack's bundled default may resolve a different major.
RUN corepack enable && corepack prepare pnpm@11.20.0 --activate

FROM base AS deps

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/zaro-web/package.json apps/zaro-web/package.json
COPY packages/zaro-sdk/package.json packages/zaro-sdk/package.json
COPY packages/tsconfig ./packages/tsconfig
RUN pnpm install --frozen-lockfile

FROM base AS builder

COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/packages/zaro-sdk/node_modules ./packages/zaro-sdk/node_modules
COPY . .

# Opt in to Next standalone output for the container runtime image.
ENV NEXT_STANDALONE=1

RUN pnpm --filter @zaro/web build

FROM base AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

WORKDIR /repo/apps/zaro-web

COPY --from=builder /repo/apps/zaro-web/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/apps/zaro-web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/zaro-web/.next/static ./.next/static

USER nextjs

EXPOSE 3001
ENV PORT=3001

CMD ["node", "server.js"]
