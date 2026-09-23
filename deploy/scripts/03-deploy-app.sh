#!/usr/bin/env bash
# Step 4+6: rsync backend+admin build, install venv, nginx TLS, systemd
set -euo pipefail

KEY="${1:-}"
HOST="${2:-}"
DOMAIN="${3:-}"

if [[ -z "$KEY" || -z "$HOST" || -z "$DOMAIN" ]]; then
  echo "Usage: $0 <ssh-private-key> <app-eip> <domain>"
  echo "  e.g. $0 ~/.ssh/takeley.pem 1.2.3.4 takeley.app"
  exit 1
fi

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new ubuntu@"$HOST")
RSYNC=(rsync -az --delete -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new")

echo "== Build admin =="
(
  cd "$REPO/admin"
  VITE_API_BASE_URL="https://api.${DOMAIN}" npm run build
)

echo "== Sync code =="
"${SSH[@]}" 'sudo mkdir -p /opt/takeley/{backend,admin,storage/issue_images,storage/briefs,logs} && sudo chown -R ubuntu:ubuntu /opt/takeley'
"${RSYNC[@]}" \
  --exclude '.venv' --exclude '__pycache__' --exclude '.env' --exclude 'takeley.db' --exclude 'storage' \
  "$REPO/backend/" "ubuntu@${HOST}:/opt/takeley/backend/"
"${RSYNC[@]}" "$REPO/admin/dist/" "ubuntu@${HOST}:/opt/takeley/admin/dist/"
"${RSYNC[@]}" "$REPO/deploy/systemd/" "ubuntu@${HOST}:/tmp/takeley-systemd/"
"${RSYNC[@]}" "$REPO/deploy/nginx/takeley.conf.template" "ubuntu@${HOST}:/tmp/takeley.conf.template"
"${RSYNC[@]}" "$REPO/deploy/env/backend.env.example" "ubuntu@${HOST}:/tmp/backend.env.example"

echo "== Remote install =="
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
DOMAIN='$DOMAIN'

# env file (create once)
if [[ ! -f /etc/takeley/backend.env ]]; then
  sudo mkdir -p /etc/takeley
  sudo cp /tmp/backend.env.example /etc/takeley/backend.env
  sudo sed -i "s/DOMAIN_NAME/\${DOMAIN}/g" /etc/takeley/backend.env
  echo "Created /etc/takeley/backend.env — EDIT DATABASE_URL, ADMIN_API_KEY, API keys before start."
fi

# Python venv
cd /opt/takeley/backend
python3.11 -m venv .venv || python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

# systemd
sudo cp /tmp/takeley-systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# nginx vhosts
sudo mkdir -p /var/www/certbot
sed "s/DOMAIN_NAME/\${DOMAIN}/g" /tmp/takeley.conf.template | sudo tee /etc/nginx/sites-available/takeley >/dev/null
sudo ln -sfn /etc/nginx/sites-available/takeley /etc/nginx/sites-enabled/takeley
sudo rm -f /etc/nginx/sites-enabled/default
# Temporarily comment ssl server blocks if certs missing — use HTTP-only stub for first certbot
if [[ ! -d /etc/letsencrypt/live/api.\${DOMAIN} ]]; then
  sudo tee /etc/nginx/sites-available/takeley >/dev/null <<EOF
server {
    listen 80;
    server_name api.\${DOMAIN} admin.\${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location /health { proxy_pass http://127.0.0.1:8000/health; proxy_set_header Host \\\$host; }
    location / { return 200 'ok'; add_header Content-Type text/plain; }
}
EOF
fi
sudo nginx -t && sudo systemctl reload nginx

# ownership
sudo id -u takeley >/dev/null 2>&1 || sudo useradd --system --home /opt/takeley --shell /usr/sbin/nologin takeley
sudo chown -R takeley:takeley /opt/takeley

echo "Remote install done. Next on server:"
echo "  1) sudo nano /etc/takeley/backend.env   # paste terraform database_url + secrets"
echo "  2) cd /opt/takeley/backend && sudo -u takeley .venv/bin/alembic upgrade head"
echo "  3) sudo systemctl enable --now takeley-api takeley-worker"
echo "  4) sudo certbot --nginx -d api.\${DOMAIN} -d admin.\${DOMAIN} --email YOU@email --agree-tos -n"
echo "  5) re-run deploy to install full HTTPS nginx template after certs exist"
REMOTE

echo "Deploy sync complete."
