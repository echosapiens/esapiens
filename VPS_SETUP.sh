# Esapiens Sprint 4 — Hostinger VPS Setup
# Run these commands once on the VPS (as root or with sudo)

# 1. Basic security
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp      # SSH
ufw allow 443/tcp     # HTTPS
ufw allow 80/tcp      # HTTP (redirect to HTTPS later)
ufw --force enable

# 2. Install Docker
apt-get update
apt-get install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker

# 3. Clone the project
cd /root
git clone https://github.com/echosapiens/esapiens-sprint4.git persistent/esapiens-sprint4
cd persistent/esapiens-sprint4

# 4. Set environment variables
cat > backend/.env << 'EOF'
OPENROUTER_API_KEY=sk-or-v1-your-key
MODAL_TOKEN_ID=your-modal-token-id
MODAL_TOKEN_SECRET=your-modal-token-secret
JWT_SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///./data/esapiens.db
EOF

# 5. Start the services
docker compose up -d

# 6. Verify
docker compose ps
curl http://localhost:8000/health