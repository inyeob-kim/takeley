# TAKELEY production deploy (AWS B: EC2 + RDS)

Cost-focused stack for Seoul (`ap-northeast-2`):

| Piece | Choice |
|-------|--------|
| DNS | Amazon Registrar + Route 53 |
| App | EC2 `t4g.small` (ARM) + Elastic IP + nginx + Let's Encrypt |
| DB | RDS Postgres 16 `db.t4g.micro`, private, SG from app only |
| Hosts | `api.<domain>`, `admin.<domain>` |

```text
Phone / Admin  →  Route53  →  nginx(TLS)  →  uvicorn :8000
                                      └→  admin/dist
worker.main  ──────────────────────────→  RDS Postgres
```

## Prerequisites

1. AWS account, billing enabled
2. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) + `aws configure` (default region `ap-northeast-2`)
3. [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
4. Domain purchased under **Route 53 → Registered domains** (Amazon Registrar)
5. SSH keypair on your laptop

## Step 1 — Domain

1. AWS Console → **Route 53 → Registered domains → Register domain**
2. Buy the name; keep **Create hosted zone** enabled
3. Wait until the domain shows as registered and a public hosted zone exists
4. Verify:

```bash
chmod +x deploy/scripts/*.sh
./deploy/scripts/01-check-domain.sh yourdomain.com
```

Tell the team the exact domain string (e.g. `takeley.app`).

## Step 2–5 — Terraform (SG + RDS + EC2 + DNS)

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit: domain_name, ssh_ingress_cidr (YOUR_IP/32), ssh_public_key, letsencrypt_email
# create_hosted_zone = false  if Step 1 already created the zone

../scripts/02-terraform-apply.sh
```

Save outputs:

- `app_public_ip`
- `database_url` (`terraform output -raw database_url`)
- `api_host` / `admin_host`

Security groups created: `takeley-sg-app` (22/80/443), `takeley-sg-rds` (5432 from app only).

## Step 4 / 6 — Deploy app + Admin

```bash
# From repo root, after terraform apply
./deploy/scripts/03-deploy-app.sh ~/.ssh/takeley ubuntu@$(cd deploy/terraform && terraform output -raw app_public_ip) yourdomain.com
```

On the server:

1. `sudo nano /etc/takeley/backend.env` — paste `DATABASE_URL`, `ADMIN_API_KEY`, OpenAI/X/Firebase paths
2. Copy Firebase JSON to `/etc/takeley/firebase-credentials.json`
3. `cd /opt/takeley/backend && sudo -u takeley .venv/bin/alembic upgrade head`
4. `sudo systemctl enable --now takeley-api takeley-worker`
5. Issue certs (DNS A records must already point at the EIP):

```bash
sudo certbot --nginx -d api.yourdomain.com -d admin.yourdomain.com \
  --email you@email.com --agree-tos --non-interactive
```

6. Re-run `03-deploy-app.sh` so the full HTTPS nginx template is installed (or manually merge SSL lines).

## Step 6 — Clients

- **Admin build** (done inside `03-deploy-app.sh`): `VITE_API_BASE_URL=https://api.<domain>`
- **Flutter**:

```bash
flutter run --dart-define=API_BASE_URL=https://api.yourdomain.com \
  --dart-define=SHARE_ORIGIN=https://api.yourdomain.com
```

- Backend `CORS_ORIGINS` must include `https://admin.<domain>` (see `deploy/env/backend.env.example`).

## Step 7 — Smoke

```bash
./deploy/scripts/04-smoke.sh https://api.yourdomain.com https://admin.yourdomain.com
```

Expect `/health` → `{"status":"ok",...}`, issues JSON 200.

## Local files

| Path | Role |
|------|------|
| `deploy/terraform/` | SG, RDS, EC2+EIP, Route53 A |
| `deploy/nginx/` | api + admin vhosts |
| `deploy/systemd/` | `takeley-api`, `takeley-worker` |
| `deploy/env/` | production env templates |
| `deploy/scripts/` | domain check → apply → deploy → smoke |

Do **not** commit `terraform.tfvars`, `*.tfstate*`, or real `backend.env`.

## Notes

- SQLite is not used in production; only RDS.
- Worker must run on the same box (or later a second instance with the same `DATABASE_URL`).
- Prefer deleting/recreating `db.t4g.micro` only in early MVP — enable `deletion_protection` before real users.
