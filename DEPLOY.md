# E.sapiens v2 — Production Deployment Guide

> How to deploy the full-stack bioinformatics agent platform to the internet.
> Four paths: Docker/VPS, Render, Railway, and Vercel + Modal.

---

## Architecture Overview (Recap)

```
Browser ──► Nginx (port 80) ──► / → index.html (static SPA)
                │
                ├── /chat  ────► FastAPI backend :8000 (SSE streaming)
                ├── /sessions ─► FastAPI backend :8000
                └── /health ───► FastAPI backend :8000
```

| Component | Stack | Port |
|-----------|-------|------|
| Frontend  | React 18 + Vite + Mantine (static files) | 80 (Nginx) |
| Backend   | Python 3.12 + FastAPI + LangGraph + SSE | 8000 (Uvicorn) |
| Database  | In-memory / SQLite (persistent volume) | — |
| LLM       | OpenRouter API (any model) | — |

**Required env var**: `OPENROUTER_API_KEY` — [get one free](https://openrouter.ai/keys)

---

## Option 1: Docker Compose on a VPS (Recommended)

**Best for**: Full control, lowest cost, already configured.
**Providers**: DigitalOcean ($6/mo droplet), Hetzner (~€4/mo), Linode ($5/mo), AWS EC2 (t2.micro free tier).

### Step 1 — Provision a VM

```bash
# Example: DigitalOcean Ubuntu 24.04 droplet (2GB RAM, $12/mo)
# or any VM with Docker installed

ssh root@your-server-ip

# Install Docker if not present
curl -fsSL https://get.docker.com | sh
```

### Step 2 — Clone the project

```bash
git clone <your-repo-url> /opt/esapiens
cd /opt/esapiens
```

### Step 3 — Deploy with Docker Compose

```bash
export OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here

docker compose up --build -d
```

**What happens**:
- Backend builds from `backend/Dockerfile` (python:3.12-slim, uvicorn on :8000)
- Frontend builds from `frontend/Dockerfile` (multi-stage: node:22 → nginx:alpine on :80)
- `frontend/nginx.conf` proxies `/chat`, `/sessions`, `/health` to backend
- Backend data persists in Docker volume `esapiens-data`

### Step 4 — Verify

```bash
# Health check
curl http://localhost:8000/health

# Frontend
curl http://localhost/ | head -5

# Logs
docker compose logs -f
```

### Step 5 — Add HTTPS with Caddy (5 minutes)

Create `Caddyfile` in the project root:

```
esapiens.yourdomain.com {
    reverse_proxy frontend:80
}
```

Update `docker-compose.yml` to add Caddy:

```yaml
services:
  caddy:
    image: caddy:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
    depends_on:
      - frontend

volumes:
  caddy-data:
```

Or use `nginx + certbot` instead of Caddy.

### Step 6 — Set up as a systemd service (optional)

```bash
cat > /etc/systemd/system/esapiens.service << 'EOF'
[Unit]
Description=E.sapiens Docker Compose
Requires=docker.service
After=docker.service

[Service]
WorkingDirectory=/opt/esapiens
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl enable --now esapiens
```

### Step 7 — Monitor

```bash
docker compose logs --tail=20 -f
docker stats
```

---

## Option 2: Render (Simplest Managed Deployment)

**Best for**: Zero-infrastructure, free tier available, automatic HTTPS.
**Cost**: Free tier (backend sleeps after inactivity) or $7+/mo for always-on.

You'll deploy **two services**: a Web Service (backend) and a Static Site (frontend).

### Part A — Backend (Web Service)

1. Push your code to GitHub/GitLab
2. Go to [dashboard.render.com](https://dashboard.render.com) → **New Web Service**
3. Connect your repo
4. Configure:

| Field | Value |
|-------|-------|
| **Name** | `esapiens-backend` |
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free or Starter ($7/mo) |

5. Add environment variable:

| Key | Value |
|-----|-------|
| `OPENROUTER_API_KEY` | `sk-or-v1-your-key` |

6. Click **Create Web Service**
7. Note the URL (e.g. `https://esapiens-backend.onrender.com`)

### Part B — Frontend (Static Site)

1. In Render dashboard → **New Static Site**
2. Connect the same repo
3. Configure:

| Field | Value |
|-------|-------|
| **Name** | `esapiens-frontend` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm install --legacy-peer-deps && npm run build` |
| **Publish Directory** | `dist` |

4. Add **Redirect/Rewrite Rule** (for SPA routing):
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - **Action**: Rewrite

5. The frontend's `api.ts` makes requests to relative paths (`/chat`, `/sessions`, etc.)
   → You need a **reverse proxy** so the frontend domain proxies API calls to the backend.

   Add another **Redirect/Rewrite Rule**:

   | Field | Value |
   |-------|-------|
   | **Source** | `/chat/*` |
   | **Destination** | `https://esapiens-backend.onrender.com/chat/$1` |
   | **Action** | Proxy |

   Repeat for:
   - `/sessions/*` → `https://esapiens-backend.onrender.com/sessions/$1`
   - `/health` → `https://esapiens-backend.onrender.com/health`

6. Click **Create Static Site**

> **⚠️ Rendering proxy rules**: Free tier proxy rules may not work reliably.
> For production, consider using a single Render Web Service with Nginx reverse proxy
> (see Option 3 — Railway — if this is an issue).

### Render Alternative: Single Web Service with Nginx

If proxy rules are unreliable, deploy as a **single Web Service**:

```
Render Web Service (Docker)
├── Nginx (port 80) → serves frontend + proxies /chat to backend
└── Backend (port 8000)
```

Use a Dockerfile that bundles both:

```dockerfile
FROM python:3.12-slim

# Install Node, build frontend, install nginx
RUN apt-get update && apt-get install -y nginx nodejs npm

WORKDIR /app
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Build frontend
RUN cd frontend && npm install --legacy-peer-deps && npm run build
RUN cp -r frontend/dist/* /usr/share/nginx/html/

# Install backend deps
RUN cd backend && pip install -r requirements.txt

# Configure nginx
COPY nginx.conf /etc/nginx/sites-enabled/default

CMD service nginx start && cd backend && uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## Option 3: Railway (Docker-First Managed)

**Best for**: One-click deployment with native Docker support, automatic HTTPS.
**Cost**: Free $5 credit (enough for months), then $5/mo for starter.

### Step 1 — Set up

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select your repo

### Step 2 — Configure Backend

Railway detects the `docker-compose.yml` and offers to deploy both services.

If using individual services instead of compose:

1. **New Service** → **Deploy from GitHub** → select repo
2. **Root Directory** → `/backend`
3. Railway auto-detects the Dockerfile
4. Add environment variable:
   - `OPENROUTER_API_KEY` = `sk-or-v1-your-key`
   - `PORT` = `8000` (Railway sets this, but explicit helps)
5. Deploy — Railway builds the Docker image and starts it

### Step 3 — Configure Frontend

1. **New Service** → **Deploy from GitHub** → select repo
2. **Root Directory** → `/frontend`
3. Railway auto-detects the Dockerfile (multi-stage build)
4. Set the **Public Domain** for this service
5. Add environment variable:
   - `VITE_API_URL` = `https://<backend-url>.railway.app` (optional, if API is separately hosted)

> ⚠️ The frontend Dockerfile already bundles nginx with the correct proxy config.
> If both services are on Railway, update `frontend/nginx.conf` to proxy to the
> backend's Railway URL instead of `backend:8000`.

### Step 4 — Update nginx.conf for Railway

In `nginx.conf`, change:

```nginx
location /chat {
    proxy_pass https://<your-backend>.railway.app;  # Railway backend URL
    # ... rest stays the same
}
```

> **Alternative**: Use Railway's **Private Networking** — both services can
> communicate via `backend.railway.internal:8000` without public exposure.

---

## Option 4: Vercel (Frontend) + Modal (Backend)

**Best for**: Modern serverless, auto-scaling backend, free frontend tier.
**Cost**: Vercel free tier (ample). Backend on Modal: $0 for dev, ~$2/mo for light use.

### Part A — Deploy Frontend to Vercel

1. Push to GitHub
2. Go to [vercel.com](https://vercel.com) → **Add New Project**
3. Import your repo → set Root Directory to `frontend`
4. Configure:

| Setting | Value |
|---------|-------|
| **Framework** | Vite |
| **Build Command** | `npm install --legacy-peer-deps && npm run build` |
| **Output Directory** | `dist` |
| **Node Version** | 20.x |

5. Add environment variable (not strictly needed — frontend uses relative paths):

| Key | Value |
|-----|-------|
| `VITE_API_URL` | `https://<your-modal-app>.modal.run` |

6. Deploy — Vercel gives you a URL like `esapiens.vercel.app`

### Part B — Deploy Backend to Modal

Modal runs serverless Python with autoscaling. Create a new file

**`backend/modal_deploy.py`**:

```python
"""Modal deployment for E.sapiens backend.
Deploy:  modal deploy backend/modal_deploy.py
Serve:   modal serve backend/modal_deploy.py
"""

import modal
import os
from pathlib import Path

app = modal.App("esapiens-backend")

# ── Build image with all deps ──────────────────────────────────────────────
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(
        str(Path(__file__).parent / "requirements.txt")
    )
    .apt_install("curl")
)

# ── Web endpoint ───────────────────────────────────────────────────────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("esapiens-openrouter")],
    max_containers=10,
    container_idle_timeout=120,  # Keep warm for 2 min after last request
)
@modal.asgi_app()
def api():
    """Expose the FastAPI app as a Modal ASGI endpoint."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from app import app as fastapi_app
    return fastapi_app
```

Then:

```bash
# Create the secret
modal secret create esapiens-openrouter OPENROUTER_API_KEY=sk-or-v1-your-key

# Deploy (one-time)
modal deploy backend/modal_deploy.py

# Output: https://<workspace>--esapiens-backend-api.modal.run
```

### Part C — Wire Frontend → Modal Backend

Since Vercel static sites can't proxy, update the frontend to point to Modal:

**`frontend/src/lib/api.ts`** — change the base URL:

```typescript
const CHAT_BASE = 'https://<workspace>--esapiens-backend-api.modal.run';
//                                         ^— your actual Modal URL
```

Then redeploy the frontend on Vercel.

### Part D — Add CORS (if needed)

The backend's `app.py` already allows `*` origins. If you want to lock it down:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://esapiens.vercel.app"],  # your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Option 5: Fly.io (Best for Global Edge)

**Best for**: Low-latency global deployment with automatic HTTPS.
**Cost**: Free tier includes 3 shared VMs.

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create fly.toml for backend
cd backend
fly launch
# Name: esapiens-backend
# Port: 8000

# Set env var
fly secrets set OPENROUTER_API_KEY=sk-or-v1-your-key

# Deploy
fly deploy

# Create fly.toml for frontend (static)
cd ../frontend
fly launch
# Name: esapiens-frontend
# Use built Dockerfile
```

---

## Comparison Matrix

| Feature | Docker/VPS | Render | Railway | Vercel+Modal | Fly.io |
|---------|-----------|--------|---------|-------------|--------|
| **Setup time** | 30 min | 10 min | 10 min | 15 min | 15 min |
| **Cost (min)** | $5-6/mo | Free ~ $7/mo | Free ~ $5/mo | Free | Free |
| **Auto HTTPS** | Manual (Caddy) | ✅ | ✅ | ✅ | ✅ |
| **SSE support** | ✅ | ⚠️ (proxy rules) | ✅ | ✅ | ✅ |
| **Scaling** | Manual | Auto (paid) | Auto | Auto | Auto |
| **Cold start** | None | 15-30s (free) | None | 1-2s (Modal) | None |
| **GPU support** | ✅ (expensive) | ❌ | ❌ | ✅ (Modal) | ❌ |
| **Persistent DB** | Docker volume | Disk | Volumes | Modal Volumes | Volumes |
| **Monitoring** | docker logs | Dashboard | Dashboard | Dashboard | Dashboard |

---

## Environment Variables Quick Reference

```bash
# Required everywhere
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here

# For Vercel+Modal — override API base URL in frontend
VITE_API_URL=https://your-backend-url.com
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Frontend loads but API calls fail | CORS or proxy misconfiguration | Check nginx/frontend proxy routes; verify CORS headers |
| SSE streaming hangs | Buffering enabled | Ensure `proxy_buffering off;` in nginx for `/chat` |
| 502 Bad Gateway | Backend not running or port mismatch | `docker compose logs backend` to check |
| Blank page after deploy | SPA routing not configured | Add `try_files $uri $uri/ /index.html;` to nginx |
| `OPENROUTER_API_KEY` errors | Env var not set | Check deployment platform's env variable configuration |
| Free Render backend slow | Free tier sleeps after inactivity | Upgrade to paid plan or add uptime monitor |
| Docker build slow on first deploy | No layer caching | Add `.dockerignore` for `node_modules`, `.venv`, `__pycache__` |
| "Address already in use" | Port conflict | Change port mapping in `docker-compose.yml` |

---

## Security Checklist

- [ ] Set `OPENROUTER_API_KEY` — never hardcode, always env vars
- [ ] Restrict CORS to your domain in production
- [ ] Use HTTPS (Caddy, Let's Encrypt, or platform-provided)
- [ ] Lock down CORS `allow_origins` to specific domain (not `*`)
- [ ] Rate-limit the `/chat` endpoint (add slowapi or nginx rate limiting)
- [ ] Keep Docker/OS updated
- [ ] Use read-only filesystem for frontend container
- [ ] Set `OPENROUTER_API_KEY` spending limits in OpenRouter dashboard