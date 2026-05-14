# ── Frontend Dockerfile (multi-stage) ───────────────────────────────────────
# E.sapiens v2 — React + Vite + Mantine v7
#
# Stage 1: Build the Vite app with Node 22
# Stage 2: Serve static files with nginx:alpine
# ────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build ──────────────────────────────────────────────────────────

FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./

# --legacy-peer-deps needed for some Mantine peer dep combinations
RUN npm install --legacy-peer-deps

COPY . .

RUN npm run build

# ── Stage 2: Serve ──────────────────────────────────────────────────────────

FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config with proxy pass to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
