#!/bin/bash
set -euxo pipefail

# Bootstrap Ubuntu ARM for TAKELEY (API + worker + nginx).
# App code is deployed later via deploy/scripts/03-deploy-app.sh

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  nginx \
  certbot \
  python3-certbot-nginx \
  python3.11 \
  python3.11-venv \
  python3-pip \
  git \
  curl \
  ufw \
  fail2ban

mkdir -p /opt/takeley/{backend,admin,logs,storage}
mkdir -p /etc/takeley
id -u takeley >/dev/null 2>&1 || useradd --system --home /opt/takeley --shell /usr/sbin/nologin takeley
chown -R takeley:takeley /opt/takeley

# Placeholder nginx until TLS + deploy fill real vhosts.
cat >/etc/nginx/sites-available/takeley <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    location / {
        return 200 'TAKELEY bootstrap — deploy app next\n';
        add_header Content-Type text/plain;
    }
}
NGINX

ln -sfn /etc/nginx/sites-available/takeley /etc/nginx/sites-enabled/takeley
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Soft marker for operators
cat >/etc/takeley/bootstrap.env <<EOF
DOMAIN_NAME=${domain_name}
LETSENCRYPT_EMAIL=${letsencrypt_email}
PROJECT=${project}
BOOTSTRAPPED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo "TAKELEY bootstrap complete for ${domain_name}"
