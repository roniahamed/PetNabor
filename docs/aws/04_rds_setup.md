# AWS RDS Setup Guide — PetNabor
**Engine:** PostgreSQL 16 + PostGIS
**Instance:** `db.t3.medium` (2 vCPU, 4 GB RAM)
**Region:** `us-east-1`
**Method:** CLI
**Status:** ✅ Feature 4 of 5

---

## Overview

```
Django App (EC2)
    │
    ▼
RDS PostgreSQL 16 (petnabor-db)  ← Private subnet, no public access
    └── PostGIS extension enabled (for geo-location features)
```

---

## Prerequisites

- VPC configured (default VPC ব্যবহার করব)
- AWS CLI configured

---

## Step 1: Default VPC এবং Subnet IDs পান

```bash
# Default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=is-default,Values=true" \
    --query 'Vpcs[0].VpcId' \
    --output text)
echo "VPC ID: $VPC_ID"

# Subnet IDs (কমপক্ষে ২টা লাগবে, ভিন্ন AZ-এ)
aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'Subnets[*].{ID:SubnetId,AZ:AvailabilityZone}' \
    --output table
```

Note করুন: দুটো ভিন্ন AZ-এর subnet ID (`us-east-1a`, `us-east-1b` etc.)

---

## Step 2: RDS Subnet Group তৈরি করুন

```bash
aws rds create-db-subnet-group \
    --db-subnet-group-name petnabor-db-subnet-group \
    --db-subnet-group-description "PetNabor RDS subnet group" \
    --subnet-ids SUBNET_ID_1 SUBNET_ID_2 \
    --region us-east-1
```

---

## Step 3: Security Group তৈরি করুন (RDS-এর জন্য)

```bash
# Security Group তৈরি
RDS_SG_ID=$(aws ec2 create-security-group \
    --group-name petnabor-rds-sg \
    --description "PetNabor RDS PostgreSQL access" \
    --vpc-id $VPC_ID \
    --query 'GroupId' \
    --output text)
echo "RDS Security Group ID: $RDS_SG_ID"

# PostgreSQL port শুধু EC2 থেকে allow (এখন temporarily all — EC2 SG পেলে restrict করুন)
aws ec2 authorize-security-group-ingress \
    --group-id $RDS_SG_ID \
    --protocol tcp \
    --port 5432 \
    --cidr 10.0.0.0/8
```

> ⚠️ EC2 setup (Feature 5) হলে এই rule update করুন যাতে শুধু EC2 security group থেকে access হয়।

---

## Step 4: RDS Instance তৈরি করুন

> ⚠️ PASSWORD মনে রাখুন এবং `.env`-এ রাখুন। একবার হারালে reset করতে হবে।

```bash
aws rds create-db-instance \
    --db-instance-identifier petnabor-db \
    --db-instance-class db.t3.medium \
    --engine postgres \
    --engine-version "16.4" \
    --master-username petnabor_user \
    --master-user-password "YourStrongPassword123!" \
    --allocated-storage 20 \
    --storage-type gp3 \
    --db-name petnabor_db \
    --db-subnet-group-name petnabor-db-subnet-group \
    --vpc-security-group-ids $RDS_SG_ID \
    --backup-retention-period 7 \
    --no-publicly-accessible \
    --deletion-protection \
    --auto-minor-version-upgrade \
    --region us-east-1
```

**সময়:** ১০-১৫ মিনিট লাগবে।

---

## Step 5: Instance Available হয়েছে কিনা দেখুন

```bash
# Status check
aws rds describe-db-instances \
    --db-instance-identifier petnabor-db \
    --query 'DBInstances[0].{Status:DBInstanceStatus,Endpoint:Endpoint.Address}' \
    --output table \
    --region us-east-1
```

`"available"` আসলে এগিয়ে যান। Endpoint note করুন:
```
petnabor-db.xxxxxxxxxx.us-east-1.rds.amazonaws.com
```

---

## Step 6: PostGIS Extension Enable করুন

EC2 বা Docker থেকে RDS-এ connect করুন:

```bash
# Docker থেকে (local dev-এ)
docker compose exec web python -c "
import psycopg2
conn = psycopg2.connect(
    host='RDS_ENDPOINT',
    dbname='petnabor_db',
    user='petnabor_user',
    password='YourStrongPassword123!',
    sslmode='require'
)
cur = conn.cursor()
cur.execute('CREATE EXTENSION IF NOT EXISTS postgis;')
cur.execute('CREATE EXTENSION IF NOT EXISTS postgis_topology;')
conn.commit()
print('✅ PostGIS extensions enabled!')
cur.close()
conn.close()
"
```

Verify:
```bash
docker compose exec web python -c "
import psycopg2
conn = psycopg2.connect(host='RDS_ENDPOINT', dbname='petnabor_db',
    user='petnabor_user', password='YourStrongPassword123!', sslmode='require')
cur = conn.cursor()
cur.execute(\"SELECT PostGIS_Version();\")
print('PostGIS:', cur.fetchone()[0])
conn.close()
"
```

---

## Step 7: .env আপডেট করুন

```env
# Local Docker DB
POSTGRES_HOST=db
POSTGRES_DB=petnabor_db
POSTGRES_USER=petnabor_user
POSTGRES_PASSWORD=YourLocalPassword

# Production RDS (USE_RDS=True হলে এগুলো active হবে)
USE_RDS=False
RDS_HOST=petnabor-db.xxxxxxxxxx.us-east-1.rds.amazonaws.com
RDS_DB=petnabor_db
RDS_USER=petnabor_user
RDS_PASSWORD=YourStrongPassword123!
RDS_PORT=5432
POSTGRES_SSLMODE=require
```

---

## Step 8: Migrations চালান

```bash
docker compose exec web python manage.py migrate
```

---

## Step 9: Test করুন

```bash
docker compose exec web python -c "
from django.db import connection
from django.contrib.gis.db.models.functions import Distance
cursor = connection.cursor()
cursor.execute('SELECT version();')
print('PostgreSQL:', cursor.fetchone()[0])
cursor.execute(\"SELECT PostGIS_Version();\")
print('PostGIS:', cursor.fetchone()[0])
print('✅ RDS সংযোগ সফল!')
"
```

---

## Troubleshooting

| সমস্যা | সমাধান |
|--------|--------|
| Connection timeout | Security group inbound rule check করুন |
| SSL error | `POSTGRES_SSLMODE=prefer` দিয়ে try করুন |
| PostGIS not found | Step 6 আবার run করুন |
| `rds_superuser` error | master user দিয়ে connect করুন |

---

## RDS Backup & Security

```bash
# Manual snapshot
aws rds create-db-snapshot \
    --db-instance-identifier petnabor-db \
    --db-snapshot-identifier petnabor-db-manual-$(date +%Y%m%d)

# Deletion protection (already enabled)
# aws rds modify-db-instance --db-instance-identifier petnabor-db --deletion-protection
```

---

**পরবর্তী Feature:** [05_ec2_setup.md](./05_ec2_setup.md) — Application Server
