# ── Stage 1: build React app ──────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# In production the /lf-proxy path is served by nginx and proxied to Langfuse,
# eliminating the need for the separate langfuse-proxy.mjs Node process.
ARG VITE_LANGFUSE_URL=/lf-proxy
ENV VITE_LANGFUSE_URL=$VITE_LANGFUSE_URL

RUN npm run build

# ── Stage 2: serve with nginx ─────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE 80

# envsubst '$LANGFUSE_HOST' only replaces that one variable;
# all nginx $variables ($host, $uri, etc.) are left untouched.
CMD ["/bin/sh", "-c", \
  "envsubst '$LANGFUSE_HOST' < /etc/nginx/templates/default.conf.template \
   > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
