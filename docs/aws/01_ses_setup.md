# AWS SES Setup Guide — PetNabor
**Region:** `us-east-1`  
**Method:** IAM User + `django-ses` library  
**Status:** ✅ Feature 1 of 5

---

## Overview

এই guide-এ AWS CLI ব্যবহার করে SES সম্পূর্ণ setup করা হবে। কোনো AWS Console login দরকার নেই।

```
Django (django-ses) ──► IAM User (Access Key) ──► SES ──► Email Delivery
```

---

## Prerequisites

### AWS CLI Install করুন (যদি না থাকে)
```bash
# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Version check
aws --version
```

### AWS CLI Configure করুন
```bash
aws configure
# এখানে আপনার root/admin AWS credentials দিন:
# AWS Access Key ID:      [আপনার key]
# AWS Secret Access Key:  [আপনার secret]
# Default region name:    us-east-1
# Default output format:  json
```

> ⚠️ এই configure step-এ root account credentials দিন শুধু IAM user তৈরির জন্য।  
> পরে application-এর জন্য তৈরি হওয়া `petnabor-ses-user`-এর key `.env`-এ দেওয়া হবে।

---

## Step 1: IAM Policy তৈরি করুন

```bash
# project root থেকে run করুন
aws iam create-policy \
    --policy-name PetNaborSESPolicy \
    --policy-document file://docs/aws/iam/ses-policy.json \
    --description "SES email sending policy for PetNabor application" \
    --region us-east-1
```

**Output থেকে `PolicyArn` note করুন।** এরকম দেখাবে:
```
arn:aws:iam::123456789012:policy/PetNaborSESPolicy
```

---

## Step 2: IAM User তৈরি করুন

```bash
aws iam create-user \
    --user-name petnabor-ses-user \
    --tags Key=Project,Value=PetNabor Key=Service,Value=SES
```

---

## Step 3: Policy User-এ Attach করুন

```bash
# নিচের ACCOUNT_ID আপনার 12-digit AWS account ID দিয়ে replace করুন
aws iam attach-user-policy \
    --user-name petnabor-ses-user \
    --policy-arn arn:aws:iam::ACCOUNT_ID:policy/PetNaborSESPolicy
```

**Account ID জানতে:**
```bash
aws sts get-caller-identity --query Account --output text
```

---

## Step 4: Access Key তৈরি করুন

```bash
aws iam create-access-key --user-name petnabor-ses-user
```

**Output এরকম আসবে:**
```json
{
    "AccessKey": {
        "UserName": "petnabor-ses-user",
        "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "Status": "Active"
    }
}
```

> ⚠️ `SecretAccessKey` শুধুমাত্র এক বারই দেখা যাবে। এখনই `.env` ফাইলে save করুন।

`.env` ফাইলে এভাবে রাখুন:
```env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_SES_REGION_NAME=us-east-1
DEFAULT_FROM_EMAIL=noreply@petnabor.com
```

---

## Step 5: Email Identity Verify করুন

### Option A: শুধু Email Address Verify (Sandbox testing-এর জন্য)
```bash
aws sesv2 create-email-identity \
    --email-identity noreply@petnabor.com \
    --region us-east-1
```
এরপর ওই email address-এ একটা verification link আসবে। সেটায় click করুন।

### Option B: পুরো Domain Verify (Production-এর জন্য — Recommended)
```bash
aws sesv2 create-email-identity \
    --email-identity petnabor.com \
    --region us-east-1
```

DNS records দেখতে:
```bash
aws sesv2 get-email-identity \
    --email-identity petnabor.com \
    --region us-east-1 \
    --query 'DkimAttributes'
```

Output-এ DKIM CNAME records আসবে — এগুলো আপনার domain DNS-এ যোগ করুন।

---

## Step 6: Sandbox থেকে Production Access নিন

নতুন SES account sandbox mode-এ থাকে। শুধু verified addresses-এ email পাঠানো যায়।

```bash
aws sesv2 put-account-details \
    --mail-type TRANSACTIONAL \
    --website-url https://petnabor.com \
    --use-case-description "PetNabor is a social media platform for pet lovers. We send OTP verification emails, password reset links, and account notifications to registered users." \
    --production-access-enabled \
    --region us-east-1
```

> ℹ️ Production access সাধারণত ২৪ ঘণ্টার মধ্যে approve হয়।

---

## Step 7: Verification করুন

### IAM setup সঠিক কিনা দেখুন:
```bash
# User exist করছে কিনা
aws iam get-user --user-name petnabor-ses-user

# Policy attached কিনা
aws iam list-attached-user-policies --user-name petnabor-ses-user

# Email identity verify হয়েছে কিনা
aws sesv2 get-email-identity \
    --email-identity petnabor.com \
    --region us-east-1 \
    --query 'VerifiedForSendingStatus'
```

### Django থেকে test email পাঠান:
```bash
# project directory থেকে
python manage.py shell
```
```python
from django.core.mail import send_mail

send_mail(
    subject='PetNabor SES Test',
    message='SES সফলভাবে কাজ করছে!',
    from_email=None,  # settings.DEFAULT_FROM_EMAIL ব্যবহার হবে
    recipient_list=['your-verified-email@example.com'],
)
print("Email sent successfully!")
```

---

## Send Quota দেখুন
```bash
aws sesv2 get-account \
    --region us-east-1 \
    --query 'SendQuota'
```

---

## Troubleshooting

| সমস্যা | সমাধান |
|--------|--------|
| `Email address is not verified` | Step 5 থেকে email verify করুন |
| `AccessDenied` | IAM policy সঠিকভাবে attach হয়েছে কিনা দেখুন |
| `MessageRejected` | Sandbox mode-এ recipient-ও verified হতে হবে |
| `Throttling` | প্রতি সেকেন্ডে সর্বোচ্চ 14টা email (sandbox: 1/sec) |

---

## Cleanup (প্রয়োজনে)
```bash
# Access key delete
aws iam delete-access-key \
    --user-name petnabor-ses-user \
    --access-key-id AKIAIOSFODNN7EXAMPLE

# User delete
aws iam detach-user-policy \
    --user-name petnabor-ses-user \
    --policy-arn arn:aws:iam::ACCOUNT_ID:policy/PetNaborSESPolicy
aws iam delete-user --user-name petnabor-ses-user
```

---

**পরবর্তী Feature:** [02_s3_setup.md](./02_s3_setup.md) — S3 Media Storage
