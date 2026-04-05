# AWS CloudFront Setup Guide — PetNabor
**Region:** Global (CloudFront is global, origin in `us-east-1`)
**Origin:** `petnabor-media` S3 bucket
**Custom Domain:** `cdn.petnabor.com`
**Method:** OAC (Origin Access Control) — more secure than legacy OAI
**Status:** ✅ Feature 3 of 5

---

## Overview

```
User Browser
    │
    ▼
CloudFront CDN (cdn.petnabor.com)
    │  ← Cache করে, fast serve করে
    ▼
S3 Bucket (petnabor-media) ← শুধু CloudFront access পাবে
    ├── /media/     (user uploaded files)
    └── /static/    (CSS, JS, icons)
```

---

## Prerequisites

- S3 bucket `petnabor-media` তৈরি ✅ (Feature 2)
- AWS CLI configured

---

## Step 1: Origin Access Control (OAC) তৈরি করুন

```bash
aws cloudfront create-origin-access-control \
    --origin-access-control-config file://docs/aws/cloudfront/oac-config.json \
    --region us-east-1
```

Output থেকে এটা note করুন:
```json
{
    "OriginAccessControl": {
        "Id": "XXXXXXXXXXXXXX",   ← এটা OAC_ID
        ...
    }
}
```

---

## Step 2: SSL Certificate তৈরি করুন (CloudFront-এর জন্য us-east-1 লাগবে)

```bash
aws acm request-certificate \
    --domain-name cdn.petnabor.com \
    --validation-method DNS \
    --region us-east-1
```

Output থেকে CertificateArn note করুন।

### DNS Validation Record দেখুন:
```bash
aws acm describe-certificate \
    --certificate-arn arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID \
    --region us-east-1 \
    --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

Output example:
```json
{
    "Name": "_abc123.cdn.petnabor.com.",
    "Type": "CNAME",
    "Value": "_xyz.acm-validations.aws."
}
```

**GoDaddy-তে এই CNAME যোগ করুন।** ১৫-৩০ মিনিট পরে certificate validated হবে।

### Certificate validate হয়েছে কিনা দেখুন:
```bash
aws acm describe-certificate \
    --certificate-arn arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID \
    --region us-east-1 \
    --query 'Certificate.Status'
```
`"ISSUED"` আসলে এগিয়ে যান।

---

## Step 3: CloudFront Distribution তৈরি করুন

নিচের command-এ `OAC_ID` এবং `CERT_ARN` replace করুন:

```bash
aws cloudfront create-distribution \
--distribution-config '{
  "CallerReference": "petnabor-cdn-2026",
  "Comment": "PetNabor CDN for media and static files",
  "DefaultCacheBehavior": {
    "TargetOriginId": "petnabor-s3-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true,
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"]
    }
  },
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "petnabor-s3-origin",
        "DomainName": "petnabor-media.s3.us-east-1.amazonaws.com",
        "S3OriginConfig": {"OriginAccessIdentity": ""},
        "OriginAccessControlId": "OAC_ID"
      }
    ]
  },
  "Aliases": {
    "Quantity": 1,
    "Items": ["cdn.petnabor.com"]
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "CERT_ARN",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  },
  "Enabled": true,
  "PriceClass": "PriceClass_All",
  "HttpVersion": "http2and3"
}'
```

Output থেকে note করুন:
```
"Id": "EXXXXXXXXXXXXXXX"    ← DISTRIBUTION_ID
"DomainName": "dXXXXXX.cloudfront.net"  ← CloudFront domain
```

---

## Step 4: S3 Bucket Policy আপডেট করুন

`docs/aws/cloudfront/s3-bucket-policy.json` ফাইলে `ACCOUNT_ID` এবং `DISTRIBUTION_ID` replace করুন:

```bash
# Account ID
aws sts get-caller-identity --query Account --output text

# DISTRIBUTION_ID = Step 3 থেকে পাওয়া Id
```

তারপর policy apply করুন:
```bash
aws s3api put-bucket-policy \
    --bucket petnabor-media \
    --policy file://docs/aws/cloudfront/s3-bucket-policy.json
```

---

## Step 5: GoDaddy-তে CNAME যোগ করুন

| Type | Name | Value |
|------|------|-------|
| CNAME | `cdn` | `dXXXXXX.cloudfront.net` |

(Step 3-এর `DomainName` value বসান)

---

## Step 6: Distribution Ready হয়েছে কিনা দেখুন

```bash
aws cloudfront get-distribution \
    --id DISTRIBUTION_ID \
    --query 'Distribution.Status'
```
`"Deployed"` আসলে সম্পূর্ণ।

⏳ সাধারণত ১৫-২০ মিনিট লাগে।

---

## Step 7: .env আপডেট করুন

```env
AWS_CLOUDFRONT_DOMAIN=cdn.petnabor.com
USE_S3=True
```

### Docker restart করুন:
```bash
docker compose up -d --force-recreate web
```

### Test করুন:
```bash
docker compose exec web python -c "
from django.conf import settings
print('Media URL:', settings.MEDIA_URL)
# Expected: https://cdn.petnabor.com/media/
print('Static URL:', settings.STATIC_URL)
# Expected: https://cdn.petnabor.com/static/
"
```

---

## Step 8: Static files আপলোড করুন

```bash
docker compose exec web python manage.py collectstatic --noinput
```

---

## Troubleshooting

| সমস্যা | সমাধান |
|--------|--------|
| 403 Forbidden | S3 bucket policy check করুন (Step 4) |
| SSL error | Certificate `ISSUED` হয়েছে কিনা দেখুন |
| CNAME not resolving | ১৫-৩০ মিনিট অপেক্ষা করুন |
| Media not showing | `USE_S3=True` এবং `AWS_CLOUDFRONT_DOMAIN` set আছে কিনা দেখুন |

---

## Cache Invalidation (ফাইল আপডেট করলে)

```bash
aws cloudfront create-invalidation \
    --distribution-id DISTRIBUTION_ID \
    --paths "/media/*" "/static/*"
```

---

**পরবর্তী Feature:** [04_rds_setup.md](./04_rds_setup.md) — PostgreSQL (PostGIS) RDS
