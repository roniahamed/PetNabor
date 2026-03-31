# Production SOP: Docker Django API + Custom Domain + HTTPS on a Shared Server

## Overview
This SOP is for a shared VPS/IP where multiple projects run on the same host.
In this model, your app stack must not bind directly to `80/443`.
Host-level Nginx terminates SSL and reverse proxies to your app at `127.0.0.1:8002`.

## Target Setup
- Domain: `api.example.com`
- App endpoint (internal): `127.0.0.1:8002`
- TLS provider: Let's Encrypt
- App stack: Docker Compose
- Edge reverse proxy: Host Nginx

## Architecture
- Client -> Host Nginx :443
- Host Nginx -> `http://127.0.0.1:8002`
- Docker Nginx -> Django web service :8000

## Step 1: Run Docker app on localhost-only port
Set Docker Nginx port mapping in `docker-compose.yml`:

```yaml
ports:
  - "127.0.0.1:8002:80"
```

Start services:

```bash
sudo docker compose down
sudo docker compose up -d --build
```

## Step 2: Create host Nginx vhost
Create file:

```bash
sudo nano /etc/nginx/sites-available/api.example.com
```

Paste:

```nginx
upstream app_backend {
    server 127.0.0.1:8002;
    keepalive 32;
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    server_name api.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 5000M;

    location / {
        proxy_pass http://app_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

Enable site:

```bash
sudo ln -sf /etc/nginx/sites-available/api.example.com /etc/nginx/sites-enabled/api.example.com
```

## Step 3: Create a temporary certificate for first Nginx validation
```bash
sudo mkdir -p /etc/letsencrypt/live/api.example.com
sudo openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout /etc/letsencrypt/live/api.example.com/privkey.pem \
    -out /etc/letsencrypt/live/api.example.com/fullchain.pem \
  -days 1 \
    -subj "/CN=api.example.com"

sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## Step 4: Verify ACME challenge path
```bash
sudo mkdir -p /var/www/certbot/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/certbot
echo ok | sudo tee /var/www/certbot/.well-known/acme-challenge/test-file >/dev/null
curl http://api.example.com/.well-known/acme-challenge/test-file
```

Expected output: `ok`

## Step 5: Issue real Let's Encrypt certificate (Docker Certbot)
Use this path if host certbot is broken due to Python conflicts.

Remove temporary lineage:

```bash
sudo rm -rf /etc/letsencrypt/live/api.example.com
sudo rm -rf /etc/letsencrypt/archive/api.example.com
sudo rm -f /etc/letsencrypt/renewal/api.example.com.conf
```

Issue trusted cert:

```bash
sudo docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/www/certbot:/var/www/certbot \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
    -d api.example.com \
    --email admin@example.com \
  --agree-tos \
  --no-eff-email
```

## Step 6: Apply and verify
```bash
sudo nginx -t
sudo systemctl restart nginx

curl -I https://api.example.com/api/
```

## Troubleshooting
### 1) `SSL certificate problem: self-signed certificate`
A trusted cert has not been issued/applied yet. Re-run Step 5 and Step 6.

### 2) `cannot load certificate ... fullchain.pem`
Certificate files are missing. Create temporary cert, then issue real cert.

### 3) `nginx.service is not active, cannot reload`
```bash
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl status nginx --no-pager -l
```

### 4) Host certbot crashes with `urllib3`/`appengine` import errors
Use Docker Certbot in Step 5 instead of host certbot.

### 5) ACME challenge fails
- DNS A record must point to the correct server IP
- Port 80 must be publicly open
- If using Cloudflare, set DNS record to DNS-only during validation

## Quick Recovery Checklist
1. Docker app is running on `127.0.0.1:8002`
2. Host Nginx site is enabled
3. `nginx -t` passes
4. ACME test file is reachable over HTTP
5. Real certificate is issued
6. Nginx is restarted
7. HTTPS endpoint is verified

---
This document can be used as your production SOP and incident recovery reference.
