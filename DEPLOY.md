# Esapiens Sprint 5 — Production Deployment Guide

## Prerequisites
- Hostinger VPS (2GB RAM minimum)
- Docker + Docker Compose installed
- Domain pointing to VPS IP
- Modal account (token-id + token-secret)
- OpenRouter API key
- Brave Search API key

## Step 1: VPS Setup
```bash
# SSH into VPS
ssh root@your-vps-ip

# Run setup script
bash <(curl -s https://raw.githubusercontent.com/echosapiens/esapiens-sprint5/main/VPS_SETUP.sh)
```

## Step 2: Clone & Configure
```bash
cd /root/persistent
git clone https://github.com/echosapiens/esapiens-sprint5.git
cd esapiens-sprint5

# Set environment variables
cat > backend/.env << 'EOF'
OPENROUTER_API_KEY=sk-or-v1-your-key
MODAL_TOKEN_ID=your-modal-token-id
MODAL_TOKEN_SECRET=your-modal-token-secret
BRAVE_SEARCH_API_KEY=your-brave-api-key
JWT_SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///./esapiens.db
EOF
```

## Step 3: Deploy
```bash
docker compose up -d --build
```

## Step 4: Verify
```bash
# Health check
curl http://localhost:8000/health

# Should return: {"status":"ok","runtime":"split-architecture"}

# Check logs
docker compose logs -f backend
```

## Step 5: SSL (Production)
```bash
# Install certbot
apt-get install -y certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d your-domain.com

# Set up auto-renewal
certbot renew --dry-run
```

## Step 6: Monitoring
```bash
# View real-time logs
docker compose logs -f --tail=100

# Check resource usage
docker stats

# Backup database
cp backend/esapiens.db backups/esapiens-$(date +%Y%m%d).db
```

## Architecture Notes
- Backend runs on port 8000 (internal)
- Frontend runs on port 3000 (internal)
- Nginx reverse proxy handles SSL termination
- SQLite database stored at backend/esapiens.db
- Modal handles all heavy compute (BioContainers)
- Rate limiting: 30 req/min chat, 10 req/min pipeline
- JWT auth required for all /api/v1/ endpoints
