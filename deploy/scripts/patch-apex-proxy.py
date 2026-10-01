"""Point takeley.co / at the API so the official site is served from FastAPI."""

from pathlib import Path

path = Path("/etc/nginx/sites-enabled/takeley")
text = path.read_text()
old = """    location / {
        root /var/www/takeley-apex;
        try_files /index.html =404;
    }"""
new = """    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }"""
if old not in text:
    raise SystemExit("apex location block not found")
path.write_text(text.replace(old, new, 1))
