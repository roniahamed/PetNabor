# শেয়ার্ড সার্ভারে Docker Django API, কাস্টম ডোমেইন ও HTTPS ডেপ্লয়মেন্ট SOP

## ভূমিকা
এই SOP শেয়ার্ড VPS/IP পরিবেশের জন্য, যেখানে একই সার্ভারে একাধিক প্রজেক্ট হোস্ট করা থাকে।
এই পদ্ধতিতে অ্যাপ স্ট্যাক সরাসরি `80/443` পোর্ট দখল করবে না।
হোস্ট মেশিনের Nginx SSL টার্মিনেট করবে এবং অ্যাপকে `127.0.0.1:8002` ঠিকানায় রিভার্স প্রক্সি করবে।

## লক্ষ্যমাত্রা সেটআপ
- ডোমেইন: `api.example.com`
- অভ্যন্তরীণ অ্যাপ এন্ডপয়েন্ট: `127.0.0.1:8002`
- TLS প্রদানকারী: Let's Encrypt
- অ্যাপ স্ট্যাক: Docker Compose
- এজ রিভার্স প্রক্সি: Host Nginx

## আর্কিটেকচার
- ক্লায়েন্ট -> Host Nginx :443
- Host Nginx -> `http://127.0.0.1:8002`
- Docker Nginx -> Django web service :8000

## ধাপ ১: Docker অ্যাপকে localhost পোর্টে চালু করা
`docker-compose.yml` ফাইলে nginx এর পোর্ট ম্যাপিং এভাবে দিন:

```yaml
ports:
  - "127.0.0.1:8002:80"
```

তারপর চালান:

```bash
sudo docker compose down
sudo docker compose up -d --build
```

## ধাপ ২: Host Nginx vhost তৈরি করা
ফাইল তৈরি করুন:

```bash
sudo nano /etc/nginx/sites-available/api.example.com
```

নিচের কনফিগারেশন বসান:

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

সাইট সক্রিয় করুন:

```bash
sudo ln -sf /etc/nginx/sites-available/api.example.com /etc/nginx/sites-enabled/api.example.com
```

## ধাপ ৩: প্রথমবার Nginx যাচাই পাস করানোর জন্য অস্থায়ী সার্টিফিকেট
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

## ধাপ ৪: ACME challenge পথ যাচাই
```bash
sudo mkdir -p /var/www/certbot/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/certbot
echo ok | sudo tee /var/www/certbot/.well-known/acme-challenge/test-file >/dev/null
curl http://api.example.com/.well-known/acme-challenge/test-file
```

প্রত্যাশিত আউটপুট: `ok`

## ধাপ ৫: আসল Let's Encrypt সার্টিফিকেট ইস্যু করা (Docker Certbot)
হোস্টের certbot এ Python conflict থাকলে এই পদ্ধতি ব্যবহার করুন।

অস্থায়ী সার্টিফিকেট lineage মুছে ফেলুন:

```bash
sudo rm -rf /etc/letsencrypt/live/api.example.com
sudo rm -rf /etc/letsencrypt/archive/api.example.com
sudo rm -f /etc/letsencrypt/renewal/api.example.com.conf
```

আসল সার্টিফিকেট ইস্যু করুন:

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

## ধাপ ৬: সার্টিফিকেট প্রয়োগ ও যাচাই
```bash
sudo nginx -t
sudo systemctl restart nginx

curl -I https://api.example.com/api/
```

## সমস্যা সমাধান
### ১) `SSL certificate problem: self-signed certificate`
আসল সার্টিফিকেট ইস্যু বা প্রয়োগ হয়নি। ধাপ ৫ ও ধাপ ৬ পুনরায় চালান।

### ২) `cannot load certificate ... fullchain.pem`
সার্টিফিকেট ফাইল নেই। আগে অস্থায়ী সার্টিফিকেট তৈরি করুন, তারপর আসল সার্টিফিকেট ইস্যু করুন।

### ৩) `nginx.service is not active, cannot reload`
```bash
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl status nginx --no-pager -l
```

### ৪) Host certbot এ `urllib3` বা `appengine` import error
হোস্ট certbot বাদ দিয়ে Docker Certbot ব্যবহার করুন (ধাপ ৫)।

### ৫) ACME challenge ব্যর্থ হলে
- DNS A record সঠিক সার্ভার IP-তে পয়েন্ট করছে কি না যাচাই করুন
- পোর্ট 80 ইন্টারনেট থেকে খোলা আছে কি না যাচাই করুন
- Cloudflare ব্যবহার করলে ভ্যালিডেশনের সময় DNS-only মোড ব্যবহার করুন

## দ্রুত রিকভারি চেকলিস্ট
1. Docker অ্যাপ `127.0.0.1:8002` এ চলছে
2. Host Nginx সাইট সক্রিয়
3. `nginx -t` সফল
4. ACME test file HTTP দিয়ে অ্যাক্সেসযোগ্য
5. আসল সার্টিফিকেট ইস্যু হয়েছে
6. Nginx রিস্টার্ট হয়েছে
7. HTTPS এন্ডপয়েন্ট যাচাই হয়েছে

---
এই নথিটি প্রোডাকশন SOP এবং ইনসিডেন্ট রিকভারি রেফারেন্স হিসেবে ব্যবহার করা যাবে।
