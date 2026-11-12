# Revizio Web — build Vite puis serve via nginx
FROM node:20-alpine AS builder

WORKDIR /app

# pnpm
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# Copie des manifests workspace pour un install cache-friendly
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY packages/shared/design-tokens/package.json ./packages/shared/design-tokens/
COPY apps/web/package.json ./apps/web/

RUN pnpm install --frozen-lockfile --filter web... --filter @revizio/design-tokens...

# Copie du code
COPY packages/shared/design-tokens ./packages/shared/design-tokens
COPY apps/web ./apps/web

RUN pnpm --filter web build

# --- Runtime nginx ---
FROM nginx:1.27-alpine AS runtime
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
