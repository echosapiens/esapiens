# ── Multi-stage Node 22 build for E.sapiens frontend ──────────────────────

# ── Builder: install dependencies and build ───────────────────────────────
FROM node:22-slim AS builder

WORKDIR /app

# Backend URL for Next.js rewrites (baked in at build time)
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=${BACKEND_URL}

# Copy dependency manifests first for better Docker layer caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --prefer-offline 2>/dev/null || npm install

# Copy source code
COPY . .

# Ensure public directory exists (Next.js standalone requires it)
RUN mkdir -p public

# Build the Next.js application
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Runner: minimal image with standalone output ─────────────────────────
FROM node:22-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built assets from builder
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Set ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

# Expose the Next.js port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD node -e "fetch('http://localhost:3000').then(r => process.exit(r.ok ? 0 : 1))" || exit 1

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Start the standalone Next.js server
CMD ["node", "server.js"]