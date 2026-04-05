# AWS S3 Setup Guide — PetNabor
**Region:** `us-east-1`  
**Bucket:** `petnabor-media`  
**Method:** IAM Policy + django-storages  
**Status:** ✅ Feature 2 of 5

---

## Overview

S3 bucket-এ সব media (ছবি, ভিডিও) এবং static files store হবে।  
CloudFront (Feature 3) পরে এই bucket-এর সামনে বসবে।

```
Django (django-storages) ──► S3 bucket (petnabor-media)
                                  ├── /media/    (user uploads)
                                  └── /static/   (CSS, JS, icons)
```

---

## Prerequisites

- AWS CLI configured (`aws configure` বা SSO login)
- `aws` branch-এ থাকুন

---

## Step 1: S3 Bucket তৈরি করুন

```bash
# us-east-1-এ bucket তৈরি (এই region-এ LocationConstraint লাগে না)
aws s3api create-bucket \
    --bucket petnabor-media \
    --region us-east-1
```

Expected output:
```json
{
    "Location": "/petnabor-media"
}
```

---

## Step 2: Bucket Versioning Enable করুন (optional কিন্তু recommended)

```bash
aws s3api put-bucket-versioning \
    --bucket petnabor-media \
    --versioning-configuration Status=Enabled
```

---

## Step 3: Public Access Block করুন (CloudFront দিয়ে serve হবে)

```bash
aws s3api put-public-access-block \
    --bucket petnabor-media \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

---

## Step 4: CORS Configure করুন

```bash
# project root থেকে run করুন
aws s3api put-bucket-cors \
    --bucket petnabor-media \
    --cors-configuration file://docs/aws/s3/cors.json
```

---

## Step 5: IAM Policy তৈরি করুন

```bash
aws iam create-policy \
    --policy-name PetNaborS3Policy \
    --policy-document file://docs/aws/iam/s3-policy.json \
    --description "S3 media bucket read/write policy for PetNabor"
```

Output থেকে ARN note করুন:
```
arn:aws:iam::ACCOUNT_ID:policy/PetNaborS3Policy
```

Account ID জানতে:
```bash
aws sts get-caller-identity --query Account --output text
```

---

## Step 6: Policy Attach করুন

### Option A — বিদ্যমান IAM User-এ (যদি থাকে)
```bash
aws iam attach-user-policy \
    --user-name petnabor-ses-user \
    --policy-arn arn:aws:iam::ACCOUNT_ID:policy/PetNaborS3Policy
```

### Option B — EC2 Instance Role-এ (Production-এর জন্য — Recommended)
EC2 setup-এর সময় করা হবে।

---

## Step 7: Bucket সঠিকভাবে তৈরি হয়েছে কিনা Verify করুন

```bash
# Bucket list
aws s3 ls | grep petnabor

# CORS check
aws s3api get-bucket-cors --bucket petnabor-media

# Public access check
aws s3api get-public-access-block --bucket petnabor-media
```

---

## Step 8: .env আপডেট করুন

```env
USE_S3=True
AWS_STORAGE_BUCKET_NAME=petnabor-media
AWS_S3_REGION_NAME=us-east-1
AWS_CLOUDFRONT_DOMAIN=             # Feature 3-এ পূরণ করবেন
```

---

## Step 9: Static files S3-এ আপলোড করুন

```bash
docker compose exec web python manage.py collectstatic --noinput
```

Expected: static files S3-এর `static/` folder-এ upload হবে।

---

## Step 10: Test করুন

```bash
docker compose exec web python -c "
from django.conf import settings
from django.core.files.storage import default_storage
print('Storage backend:', settings.STORAGES['default']['BACKEND'])
print('Media URL:', settings.MEDIA_URL)
print('Static URL:', settings.STATIC_URL)
# Test file upload
from django.core.files.base import ContentFile
path = default_storage.save('test/hello.txt', ContentFile(b'PetNabor S3 Test'))
url = default_storage.url(path)
print('Test file URL:', url)
default_storage.delete(path)
print('✅ S3 storage working!')
"
```

---

## Troubleshooting

| সমস্যা | সমাধান |
|--------|--------|
| `NoCredentialsError` | `.env`-এ credentials check করুন |
| `AccessDenied` | IAM policy attach হয়েছে কিনা দেখুন |
| `NoSuchBucket` | bucket name `.env`-এ সঠিক দিন |
| `SignatureDoesNotMatch` | system clock sync করুন |

---

## Cleanup (প্রয়োজনে)

```bash
# Bucket সব content সহ delete
aws s3 rm s3://petnabor-media --recursive
aws s3api delete-bucket --bucket petnabor-media --region us-east-1
```

---

**পরবর্তী Feature:** [03_cloudfront_setup.md](./03_cloudfront_setup.md) — CDN for S3
