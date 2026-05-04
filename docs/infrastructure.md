# PetNabor Backend Infrastructure & Caching

_Production Infrastructure, Deployment Strategy, Database Topology, Caching Model, Performance & Security_

**Prepared by**

**Roni Ahamed**

**Backend Developer**

> Read alongside: PetNabor Architectural Overview

## Executive Summary

PetNabor runs on a stateless Django ASGI backend deployed as Docker containers on AWS, backed by managed cloud services for all stateful workloads. The system is designed for horizontal scalability, high availability, and secure media delivery.

| Layer | Technology |
| --- | --- |
| API Framework | Django 4.x + Django REST Framework |
| Runtime | Gunicorn + Uvicorn (ASGI) — supports REST and WebSocket |
| Database | AWS RDS PostgreSQL with PostGIS extension |
| Cache & Message Broker | AWS ElastiCache Redis |
| Async Task Queue | Celery + Celery Beat |
| Object Storage | AWS S3 |
| CDN | AWS CloudFront |
| Authentication | JWT (SimpleJWT) with refresh token rotation |
| Real-time | Django Channels over WebSocket |
| Push Notifications | Firebase Cloud Messaging (FCM) |
| Phone OTP | Twilio |
| Email | AWS SES |
| Payments | Stripe + Stripe Connect |
| Maps / Geospatial | Google Maps API / Mapbox + PostGIS |
| Containerization | Docker — same image across all environments |
| Reverse Proxy | Nginx |
| Load Balancer | AWS Application Load Balancer (ALB) |
| Secret Management | AWS Secrets Manager / SSM Parameter Store |
| Social Login | Firebase (Google + Apple) |

The sections that follow document each layer in detail: infrastructure topology, runtime processes, database schema, caching strategy, security controls, and observability.

## 1. Purpose

This document defines the production infrastructure, deployment strategy, database topology, caching model, performance approach, redundancy plan, and security infrastructure for PetNabor.

Read it together with PetNabor Architectural Overview, which explains the application architecture and domain components.

## 2. Infrastructure Objectives

| Objective | Design Decision |
| --- | --- |
| Managed durability | AWS-managed stateful services for database, object storage, CDN, and Redis |
| Horizontal scale | Multiple stateless web and worker containers behind a load balancer |
| Secure edge | All public traffic served through HTTPS with a wildcard SSL certificate |
| Fast media delivery | Media stored in S3, delivered through CloudFront |
| Operational visibility | Centralized logs, metrics, error reporting, and alerts |
| Failure recovery | Automated backups, point-in-time restore, redeployable containers, and rollback procedures |
| Cost discipline | Simple managed services scaled at measured bottlenecks |

## 3. Production AWS Topology

### 3.1 System Topology

The production AWS topology is structured as follows:

Internet Clients  →  DNS  →  CloudFront + Wildcard SSL  →  ALB / Reverse Proxy

→  Private App Subnets (Nginx + Django ASGI + Celery)

→  RDS PostgreSQL / ElastiCache Redis / S3 / External APIs

### 3.2 Production Services

| Area | Service |
| --- | --- |
| Cloud provider | AWS account access |
| Object storage | AWS S3 |
| Database | AWS RDS PostgreSQL with PostGIS extension support |
| Domain | DNS access, preferably Route 53 |
| CDN | AWS CloudFront |
| TLS | Wildcard SSL certificate via AWS Certificate Manager |
| Push/social login | Firebase project for FCM, Google Login, Apple Login |
| Maps | Google Maps API or Mapbox account |
| SMS | Twilio account for phone OTP verification |
| Email | AWS SES or SMTP provider for email OTP |
| Payments | Stripe and Stripe Connect |

## 4. Runtime Architecture

### 4.1 Application Processes

| Process | Runtime | Responsibility |
| --- | --- | --- |
| Web/API | Gunicorn with Uvicorn worker | Django REST API, admin, WebSocket entrypoint |
| Nginx | Nginx container | Reverse proxy, WebSocket upgrade, upload limits |
| Celery worker | Celery | OTP, notifications, media processing, referrals, async jobs |
| Celery Beat | Celery Beat | Scheduled cleanup, reconciliation, expiry jobs |

Production process separation by workload:

| Workload | Deployment Unit |
| --- | --- |
| HTTP REST / Admin | web service |
| WebSocket traffic | Same ASGI web service or separately scaled ASGI service |
| Media jobs | Dedicated Celery queue/worker |
| Notification jobs | Dedicated Celery queue/worker |
| OTP jobs | Dedicated high-priority Celery queue/worker |
| Payment/webhook jobs | Dedicated queue if throughput increases |

### 4.2 Deployment Strategy

The application is packaged as a Docker image and deployed to AWS. Stateful dependencies run as managed services. The same image is used across all environments.

Deployment sequence:

1. Build and tag an application Docker image

2. Push the image to a registry such as Amazon ECR

3. Run migrations as a controlled one-off task before or during release

4. Roll out web containers

5. Roll out Celery workers

6. Verify health checks, logs, queue depth, and error rates

7. Invalidate CloudFront paths only when static assets or cache-sensitive content require it

### 4.3 Environment Configuration

Production environment variables:

| Variable | Purpose |
| --- | --- |
| DEBUG | Must be False in production |
| SECRET_KEY | Django cryptographic secret |
| DJANGO_ALLOWED_HOSTS | API/admin hostnames |
| CSRF_TRUSTED_ORIGINS | Trusted HTTPS origins |
| CORS_ALLOWED_ORIGINS | Frontend app origins |
| POSTGRES_DB / USER / PASSWORD / HOST / PORT | RDS database connection |
| REDIS_URL | Redis endpoint for cache/Channels |
| CELERY_BROKER_URL | Redis broker URL |
| CELERY_RESULT_BACKEND | Celery result backend URL |
| AWS_ACCESS_KEY_ID / IAM role | S3/SES access |
| AWS_STORAGE_BUCKET_NAME | S3 media/static bucket |
| AWS_CLOUDFRONT_DOMAIN | CDN asset domain |
| TWILIO_ACCOUNT_SID / AUTH_TOKEN / PHONE_NUMBER | Twilio OTP sender |
| EMAIL_HOST / PORT / USE_TLS / HOST_USER / PASSWORD | SMTP or SES endpoint |
| STRIPE_SECRET_KEY / PUBLISHABLE_KEY / WEBHOOK_SECRET | Stripe keys |
| FRONTEND_BASE_URL | Stripe redirect and frontend link base |

Use AWS Secrets Manager or SSM Parameter Store for production secrets. Do not commit .env, Firebase JSON, Stripe secrets, Twilio secrets, or SMTP credentials to source control.

## 5. Server Architecture

### 5.1 Network Layout

| Layer | Placement |
| --- | --- |
| Public subnets | Load balancer, NAT gateway if needed |
| Private app subnets | Django/Nginx containers and Celery workers |
| Private data subnets | RDS and Redis |
| S3 | Access via public AWS endpoint or VPC endpoint |

### Security Group Model

| Source | Destination | Ports |
| --- | --- | --- |
| Internet | CloudFront/ALB | 443 |
| ALB | Nginx/app service | 80 or app port |
| App service | RDS | 5432 |
| App service | Redis | 6379 |
| App/worker | S3 | HTTPS 443 |
| App/worker | Firebase/Twilio/Stripe/SMTP | HTTPS/SMTP provider ports |

### 5.2 Load Balancing

Use an Application Load Balancer when running multiple app instances.

| Requirement | Reason |
| --- | --- |
| WebSocket support | Chat uses /ws/ connections |
| Long idle timeout | WebSocket connections need a longer timeout than REST |
| Health checks | Remove unhealthy containers from rotation |
| TLS termination | Terminate HTTPS at ALB or CloudFront using wildcard cert |
| Forwarded headers | Preserve scheme/host/IP for Django settings and audit logs |

### 5.3 Redundancy

| Component | Redundancy Strategy |
| --- | --- |
| Web containers | Minimum two instances across availability zones |
| Celery workers | Minimum two workers for critical queues |
| RDS | Multi-AZ, automated backups, point-in-time restore |
| Redis | Managed Redis with automatic failover if available |
| S3 | Native multi-AZ durability |
| CloudFront | Global edge network |
| DNS | Managed DNS with low-risk TTLs during migration |

## 6. Database Design and Schema Overview

### 6.1 Database Engine

| Setting | Value |
| --- | --- |
| Engine | AWS RDS PostgreSQL |
| Extension | PostGIS |
| Django backend | django.contrib.gis.db.backends.postgis |
| Primary access pattern | Django ORM |
| Backup | Automated backups with PITR |
| Availability | Multi-AZ |

### 6.2 Schema Domains

| Domain | Key Tables / Models |
| --- | --- |
| Users | users.User, users.Profile, users.OTPVerification |
| Pets | pet.PetProfile |
| Social graph | friends.FriendRequest, friends.Friendship, friends.UserBlock |
| Posts | post.Post, PostMedia, PostLike, PostComment, SavedPost, Hashtag |
| Stories | story.Story, StoryView, StoryReaction, StoryReply |
| Blogs | blog.BlogCategory, Blog, BlogLike, BlogComment, BlogViewTracker |
| Messaging | messaging.ChatThread, ThreadParticipant, Message |
| Meetings | meeting.Meeting, MeetingFeedback |
| Notifications | notifications.NotificationSettings, FCMDevice, Notifications |
| Referrals | referral.ReferralSettings, ReferralWallet, ReferralTransaction |
| Vendor/Product | vendor.Vendor, VendorPlan, VendorSubscription, product.Categories, Brand, Product, ProductMedia |
| Tips | tip.TipSettings, StripeConnectAccount, Tip, TipWithdrawal |
| Moderation | report.Report |
| Settings | site_settings.SiteSettings |

### 6.3 Indexing Principles

| Query Pattern | Index Strategy |
| --- | --- |
| Feed ordering | Composite indexes on owner/privacy/status/time |
| Messaging inbox | Thread participant, last message timestamp, unread state |
| Product listings | Category, vendor, active state, brand, created time |
| Product analytics | Product, event type, created time |
| OTP verification | User/identity, OTP type, expiry, consumed status |
| Notifications | Recipient, read state, created time |
| Geospatial discovery | PostGIS GiST/SP-GiST indexes for location fields |

### 6.4 Migration Policy

| Rule | Reason |
| --- | --- |
| Run migrations as a release step | Avoid multiple app containers racing migrations |
| Review long-running migrations | Large tables can lock writes |
| Prefer additive migrations | Safer deploy/rollback |
| Backfill with management commands or Celery jobs | Avoid request-time or migration-time table scans |
| Backup before risky schema changes | Protect against destructive mistakes |

## 7. Object Storage, CDN, and Media Delivery

### 7.1 Storage Configuration

Static files and uploaded media are served through S3 with CloudFront as the CDN layer. Docker Compose uses persistent volumes for local development.

### 7.2 S3 Bucket Structure

S3 is used for all static and uploaded media. CloudFront sits in front of S3 for public asset delivery.

| Path | Purpose | Access |
| --- | --- | --- |
| static/ | Collected Django static files | Public through CloudFront |
| media/original/ | Original uploads where retained | Private or restricted |
| media/processed/ | Compressed images, thumbnails, public media | Public through CloudFront |
| media/tmp/ | Temporary upload/processing objects | Private with lifecycle expiry |

### 7.3 Django Storage Configuration

The project uses boto3, django-storages, and django-ses. All media and static assets are served through S3-backed storage.

| Asset Type | Storage | Delivery |
| --- | --- | --- |
| Static files | S3 | CloudFront |
| Public media | S3 | CloudFront signed or unsigned URLs |
| Private media | S3 private objects | Signed URLs or authenticated proxy |
| Temporary uploads | S3 or local ephemeral disk | Not public |

### 7.4 Direct Uploads

Large files are uploaded directly to S3, bypassing the application server:

1. Client asks API for upload authorization

2. API validates user and intended object type, returns pre-signed S3 upload URL

3. Client uploads directly to S3

4. Client confirms upload to API

5. Celery processes media and writes database record

| Benefit | Impact |
| --- | --- |
| Lower app bandwidth | Web workers do not stream multi-GB uploads |
| Better reliability | S3 handles upload durability |
| Easier scaling | App instances remain stateless |

## 8. Caching Strategy

### 8.1 Cache Layers

| Layer | Technology | Purpose |
| --- | --- | --- |
| CDN cache | CloudFront | Static assets, media, selected public GET responses |
| Application cache | Redis/Django cache | Short-lived API fragments, permission checks, inbox pages |
| Realtime coordination | Redis Channels | WebSocket group routing |
| Task queue | Redis Celery broker | Async task dispatch |
| Database cache effects | PostgreSQL buffers/RDS | Hot table and index pages |
| Client cache | Mobile/web app | Token/session state, static metadata, downloaded media |

### 8.2 Redis Logical Separation

| Workload | Redis Placement |
| --- | --- |
| Celery broker | Dedicated Redis database or cluster |
| Celery results | Disable where not needed or use separate DB with short TTL |
| Django cache | Separate DB/index with eviction policy |
| Channels layer | Separate DB/cluster for realtime stability |
| Rate limiting / OTP / idempotency | Separate key namespace with explicit TTLs |

### 8.3 Cacheable Data

| Data | Cache Policy |
| --- | --- |
| Public/static settings | Redis and/or CDN; invalidate on admin settings update |
| Product categories/brands | Redis or CDN; invalidate on category/brand update |
| Product listing first pages | Short TTL Redis/CDN for public filters |
| User profile snippets | Short TTL Redis; invalidate on profile update |
| Messaging inbox first page | Very short TTL; invalidate on new message/read/archive |
| Notification unread counts | Short TTL; invalidate on notification create/read |
| Friend suggestions | Short TTL; invalidate on friend/block changes |
| OTP and rate-limit state | Redis TTL keys; never CDN |
| Media URLs | CloudFront cache; object-key versioning preferred |

### 8.4 Non-Cacheable or Sensitive Data

Do NOT CDN-cache the following:

1. Authenticated user profile mutations — user-specific and sensitive

2. JWT token responses — security risk

3. OTP responses — security risk

4. Stripe webhook responses — must process every event

5. Private messages — user-specific and privacy-sensitive

6. Admin pages — sensitive operations

7. Private media without signed URLs — access control risk

## 9. Cache Invalidation Policies

### 9.1 General Rule

Prefer short TTL plus targeted invalidation. Use versioned object keys for media and static files wherever possible.

### 9.2 Invalidation Matrix

| Event | Invalidate |
| --- | --- |
| User profile updated | Profile snippet cache, user detail cache, friend suggestion inputs |
| User blocked/unblocked | Friend lists, suggestions, visibility/permission caches |
| Friend request accepted/removed | Friend list caches, suggestions, profile visibility caches |
| Post created/updated/deleted | Feed fragments, user post list, hashtag listings |
| Comment/like/save changed | Post detail counts, user interaction cache |
| Story created/viewed/reacted/replied | Active story lists, story detail cache |
| Message created | Thread detail, inbox page, unread count, Channels event |
| Message read/archive/delete | Inbox page, unread count, thread state |
| Notification created/read | Notification list and unread count |
| Product/category/brand changed | Product listing, product detail, category/brand cache |
| Product media changed | Product detail cache, CloudFront object if overwritten |
| Site settings changed | Site settings cache |
| Tip status changed | Tip history, balance-related views |

### 9.3 CDN Invalidation

CloudFront invalidations are used only when necessary. The preferred pattern uses versioned asset keys to avoid invalidation entirely.

| Asset Type | Strategy |
| --- | --- |
| Static files | Hashed filenames from collectstatic; no invalidation required |
| User-uploaded images | Immutable object keys; update DB to new URL after replacement |
| Public generated thumbnails | Versioned paths; invalidate only if object key is reused |
| API responses | Short TTL and cache-key versioning, not broad invalidations |

## 10. Performance Optimization

### 10.1 API Performance

| Technique | Use Case |
| --- | --- |
| Cursor pagination | Feeds, messages, product listings, notification lists |
| select_related | Foreign keys such as author, vendor, category |
| prefetch_related | Many-to-many and reverse relations |
| Annotated counts | Like/comment/unread counts when needed |
| Queryset filtering before serialization | Avoid loading unnecessary rows |
| Serializer field discipline | Avoid hidden per-row queries |
| Bulk operations | Notification fan-out, analytics inserts, cleanup jobs |

### 10.2 Database Performance

| Approach | Detail |
| --- | --- |
| RDS monitoring | Track CPU, storage IOPS, slow queries, connections |
| Connection pooling | Add PgBouncer/RDS Proxy if connection pressure grows |
| Read replicas | Use only when read traffic justifies routing complexity |
| Vacuum/autovacuum tuning | Important for high-write tables: messages, events, notifications |
| Partitioning candidates | Product events, notifications, messages, audit logs if very large |

### 10.3 Media Performance

| Approach | Detail |
| --- | --- |
| WebP compression | Existing media utilities compress images where used |
| Thumbnails | Generate thumbnails for videos and smaller image variants |
| Async processing | Use Celery for CPU-heavy transformations |
| CloudFront delivery | Avoid application-serving media |
| Direct upload | Avoid using web workers as upload pipes for large files |

### 10.4 Celery Performance

| Approach | Detail |
| --- | --- |
| Queue separation | otp, notifications, media, default, payments |
| Worker autoscaling | Scale workers by queue depth and task latency |
| Idempotent tasks | Required for retries and duplicate delivery protection |
| Timeouts | External calls must have bounded timeouts |
| Dead-letter/retry policy | Failed tasks should be visible and recoverable |

## 11. Load Balancing and Redundancy

### 11.1 Web Traffic

The application is stateless when media is moved to S3 and sessions/auth use JWT. Multiple web containers can serve the same API traffic behind a load balancer.

| Requirement | Detail |
| --- | --- |
| Shared Redis | Required for cache and Channels across instances |
| Shared DB | RDS is the single durable source of truth |
| Shared object storage | S3 ensures media is available to all instances |
| Health endpoint | Add a lightweight endpoint checking app readiness |
| Graceful shutdown | Preserve in-flight requests during deployment |

### 11.2 WebSocket Traffic

| Requirement | Detail |
| --- | --- |
| Redis Channels layer | Shares events between ASGI workers |
| Load balancer WebSocket support | Upgrade headers and long idle timeout |
| Token refresh strategy | Clients reconnect with valid short-lived access token |
| Connection metrics | Track open sockets, disconnects, send failures |

### 11.3 Worker Redundancy

Run more than one worker for critical queues where possible. For provider-facing tasks (Twilio, Firebase, SES, Stripe), enforce idempotency so retries do not duplicate user-visible effects.

## 12. Security and Authentication Infrastructure

### 12.1 Implemented Application Controls

| Control | Implementation |
| --- | --- |
| JWT authentication | SimpleJWT access/refresh tokens |
| Refresh rotation | Enabled in SIMPLE_JWT |
| Protected-by-default APIs | DRF default permission is IsAuthenticated |
| WebSocket auth | JWT query-token middleware |
| OTP throttles | DRF throttle rates for send/verify/login |
| Action throttles | Per-user rates for messaging, likes, comments, saves |
| Verification enforcement | Custom middleware |
| Firebase verification | Firebase Admin SDK |
| Stripe webhook verification | Stripe signature validation |

### 12.2 Production Security Requirements

| Area | Requirement |
| --- | --- |
| HTTPS | Enforce HTTPS at CloudFront/ALB; redirect HTTP to HTTPS |
| TLS certificate | Use wildcard certificate for PetNabor domains |
| Secrets | Store in Secrets Manager/SSM, not in source control |
| IAM | Prefer IAM roles over static AWS keys |
| S3 | Block public bucket access; expose via CloudFront policy |
| Admin | Restrict admin by IP/VPN/SSO or additional auth control |
| CORS | Restrict to production frontend origins |
| CSRF | Configure only trusted HTTPS origins |
| Database | Private subnet only, encrypted storage, restricted SG |
| Redis | Private subnet only, encryption/auth where supported |
| Firebase JSON | Store as secret or mounted secret file |
| Webhooks | Validate signatures and keep endpoint paths unguessable |
| Logging | Never log OTPs, tokens, passwords, secrets, or payment payloads |

### 12.3 JWT Lifetime Policy

JWT tokens follow these security best practices:

| Token | Policy |
| --- | --- |
| Access token | Short-lived — minutes to a few hours |
| Refresh token | Longer-lived, rotated on every use, revocable |
| WebSocket auth | Uses a valid access token; client reconnects after refresh |

## 13. External Service Infrastructure

### 13.1 Firebase

Firebase is used for:

1. Push notifications — FCM device token registration and push delivery

2. Google Login — client obtains Firebase ID token; backend verifies it

3. Apple Login — client obtains Firebase-backed identity token; backend verifies it

| Requirement | Detail |
| --- | --- |
| Service account | Store securely, not in repository |
| Environments | Separate dev/staging/prod Firebase projects where possible |
| Token lifecycle | Remove invalid FCM tokens when provider reports permanent failure |

### 13.2 Twilio

Twilio sends phone OTPs. Protect OTP endpoints with throttles, identity-based limits, attempt counters, and monitoring for spend anomalies.

### 13.3 AWS SES / SMTP

AWS SES or SMTP sends email OTP and transactional email.

| Requirement | Detail |
| --- | --- |
| Domain verification | Verify sending domain in SES |
| DKIM/SPF/DMARC | Configure DNS records |
| Sandbox removal | Request production access if needed |
| Bounce handling | Add bounce/complaint monitoring for sender health |

### 13.4 Maps

Google Maps API or Mapbox is primarily a client integration. Backend responsibilities: store normalized location fields, enforce privacy controls, and support geospatial queries where needed.

### 13.5 Stripe

Stripe handles tips and Connect onboarding.

| Requirement | Detail |
| --- | --- |
| Webhook endpoint | Public HTTPS endpoint with signature validation |
| Idempotency | Protect against duplicate webhook delivery |
| Secret separation | Separate test/live keys |
| Auditability | Persist payment state transitions |

## 14. Observability and Operations

### 14.1 Monitoring

| Area | Metrics |
| --- | --- |
| Web | Request rate, latency, 4xx/5xx rate, worker restarts |
| WebSocket | Active connections, disconnects, message send failures |
| Celery | Queue depth, task latency, failures, retries |
| RDS | CPU, memory, storage, IOPS, locks, slow queries, connections |
| Redis | Memory, evictions, CPU, connected clients, command latency |
| S3/CloudFront | 4xx/5xx, cache hit ratio, origin latency, bandwidth |
| External APIs | Twilio/FCM/SES/Stripe success and failure rates |

### 14.2 Logging

| Log Source | Destination |
| --- | --- |
| Web containers | CloudWatch Logs or centralized log stack |
| Celery workers | CloudWatch Logs or centralized log stack |
| Nginx/ALB | Access logs to S3/CloudWatch |
| RDS | PostgreSQL logs and slow query logs |
| CloudFront | Access logs where needed |

Logs should include request IDs/correlation IDs so API requests, Celery jobs, and external-provider callbacks can be traced together.

### 14.3 Alerts

| Alert | Trigger |
| --- | --- |
| API error spike | Sustained 5xx increase |
| High latency | p95/p99 above threshold |
| Celery queue backlog | Queue depth or oldest task age above threshold |
| Worker down | No active worker for critical queue |
| RDS storage low | Free storage below threshold |
| RDS CPU/connections high | Sustained saturation |
| Redis memory/evictions | Evictions or high memory pressure |
| OTP provider failures | Twilio/SES failure spike |
| Stripe webhook failures | Non-2xx responses or signature failures |
| Backup failure | RDS backup/PITR issue |

## 15. Backup and Disaster Recovery

| Asset | Backup Strategy | Recovery Objective |
| --- | --- | --- |
| RDS PostgreSQL | Automated backups, PITR, manual snapshots before risky releases | Restore database to known-good point |
| S3 media | Versioning and lifecycle rules; optional cross-region replication | Recover deleted/overwritten objects |
| Environment secrets | Managed secret store with access audit | Recreate runtime safely |
| Container images | ECR image retention | Roll back to previous release |
| Infrastructure config | IaC repository recommended | Rebuild environment consistently |

Disaster recovery runbook:

1. Identify failure scope

2. Freeze risky deployments

3. Restore database or roll forward from latest healthy backup

4. Verify S3/media integrity

5. Redeploy known-good image

6. Reprocess failed Celery tasks where safe

7. Validate login, OTP, feed, media, messaging, notifications, and payments

## 16. Summary

PetNabor runs as a stateless Django ASGI application and Celery worker fleet backed by AWS-managed stateful services.

| Component | Role |
| --- | --- |
| RDS PostgreSQL / PostGIS | Source of truth for all application data |
| Redis | Coordinates cache, tasks, and realtime delivery |
| S3 | Stores media and static assets |
| CloudFront | Delivers assets globally with low latency |
| Firebase | Push notifications, Google Login, Apple Login |
| Twilio | Phone OTP verification |
| AWS SES / SMTP | Email OTP and transactional email |
| Stripe | Tips and Connect onboarding |
| Google Maps / Mapbox | Geospatial features |

Database, media, Redis, secrets, logs, health checks, and deployment orchestration are all managed through cloud-native services, allowing the modular-monolith application to scale horizontally without requiring a microservice migration.
