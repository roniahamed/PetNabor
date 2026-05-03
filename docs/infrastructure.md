# PetNabor Backend Infrastructure & Caching

## 1. Purpose

This document defines the production infrastructure, deployment strategy, database topology, caching model, performance approach, redundancy plan, and security infrastructure for PetNabor.

Read it together with [PetNabor Architectural Overview](./architectural-overview-backend-infrastructure.md), which explains the application architecture and domain components.

## 2. Infrastructure Objectives

PetNabor production infrastructure should meet these objectives:

| Objective | Requirement |
| --- | --- |
| Managed durability | Use AWS-managed stateful services for database, object storage, CDN, and preferably Redis |
| Horizontal scale | Run multiple stateless web and worker containers |
| Secure edge | Serve all public traffic through HTTPS with a wildcard SSL certificate |
| Fast media delivery | Store media in S3 and deliver through CloudFront |
| Operational visibility | Centralize logs, metrics, error reporting, and alerts |
| Failure recovery | Use backups, point-in-time restore, redeployable containers, and documented rollback |
| Cost discipline | Start with simple managed services and scale only measured bottlenecks |

## 3. Production AWS Topology

### 3.1 Target Topology Diagram

```text
Internet Clients
  |-- Mobile app
  |-- Web frontend
  |-- Admin browser
  `-- Stripe webhooks
        |
        v
DNS
  |-- api.petnabor.com / backend.petnabor.com
  `-- *.petnabor.com
        |
        v
CloudFront + Wildcard SSL
  |-- Static asset distribution
  |-- Media distribution from S3
  `-- Optional API distribution / WAF policy
        |
        v
Application Load Balancer or Public Reverse Proxy
        |
        v
Private Application Subnets
  |-- Nginx / app gateway containers
  |-- Django ASGI web containers
  |-- Celery worker containers
        |
        |-------------------|-------------------|------------------|
        v                   v                   v                  v
RDS PostgreSQL          ElastiCache Redis     S3 Buckets       External APIs
PostGIS, Multi-AZ       Cache, broker,        media/static     Firebase, Twilio,
backups, PITR           Channels              objects          SES/SMTP, Stripe,
                                                            Google Maps/Mapbox
```

### 3.2 Required Production Accounts and Services

| Area | Required Access or Service |
| --- | --- |
| Cloud provider | AWS account access |
| Object storage | AWS S3 |
| Database | AWS RDS PostgreSQL with PostGIS extension support |
| Domain | DNS access, preferably Route 53 if AWS-managed DNS is desired |
| CDN | AWS CloudFront |
| TLS | Wildcard SSL certificate, preferably AWS Certificate Manager for CloudFront/ALB |
| Push/social login | Firebase project for push notifications, Google Login, and Apple Login |
| Maps | Google Maps API or Mapbox account |
| SMS | Twilio account for phone OTP verification |
| Email | AWS SES or SMTP provider for email OTP verification |
| Payments | Stripe and Stripe Connect |


## 4. Runtime Architecture

### 4.1 Application Processes

| Process | Runtime | Responsibility |
| --- | --- | --- |
| Web/API | Gunicorn with Uvicorn worker | Django REST API, admin, WebSocket entrypoint |
| Nginx | Nginx container or host/service proxy | Reverse proxy, WebSocket upgrade, upload limits |
| Celery worker | Celery | OTP, notifications, media processing, referrals, async jobs |
| Optional Celery Beat | Celery Beat | Scheduled cleanup, reconciliation, expiry jobs |

Recommended production process separation:

| Workload | Deployment Unit |
| --- | --- |
| HTTP REST/Admin | `web` service |
| WebSocket traffic | Either same ASGI `web` service or a separately scaled ASGI service |
| Media jobs | Dedicated Celery queue/worker |
| Notification jobs | Dedicated Celery queue/worker |
| OTP jobs | Dedicated high-priority Celery queue/worker |
| Payment/webhook jobs | Dedicated queue if throughput increases |

### 4.2 Deployment Strategy

The current repository uses Docker Compose with `db`, `redis`, `web`, `nginx`, and `celery`. In AWS production, the same Docker image should be deployed while stateful dependencies move to managed services.

Recommended deployment sequence:

1. Build and tag an application Docker image.
2. Push the image to a registry such as Amazon ECR.
3. Run migrations as a controlled one-off task before or during release.
4. Roll out web containers.
5. Roll out Celery workers.
6. Verify health checks, logs, queue depth, and error rates.
7. Invalidate CloudFront paths only when static assets or cache-sensitive public content require it.

Avoid relying on every web container startup to run migrations in production. Automatic migrations in an entrypoint are acceptable for simple single-host deployment, but controlled migration jobs are safer once multiple instances are running.

### 4.3 Environment Configuration

Important production variables:

| Variable | Purpose |
| --- | --- |
| `DEBUG` | Must be `False` in production |
| `SECRET_KEY` | Django cryptographic secret |
| `DJANGO_ALLOWED_HOSTS` | API/admin hostnames |
| `CSRF_TRUSTED_ORIGINS` | Trusted HTTPS origins |
| `CORS_ALLOWED_ORIGINS` | Frontend app origins |
| `POSTGRES_DB` | RDS database name |
| `POSTGRES_USER` | RDS username |
| `POSTGRES_PASSWORD` | RDS password |
| `POSTGRES_HOST` | RDS endpoint |
| `POSTGRES_PORT` | Usually `5432` |
| `REDIS_URL` | Redis endpoint for cache/Channels |
| `CELERY_BROKER_URL` | Redis broker URL |
| `CELERY_RESULT_BACKEND` | Celery result backend URL |
| `AWS_ACCESS_KEY_ID` / IAM role | S3/SES access where role-based access is unavailable |
| `AWS_SECRET_ACCESS_KEY` | S3/SES secret if static keys are used |
| `AWS_STORAGE_BUCKET_NAME` | S3 media/static bucket |
| `AWS_S3_REGION_NAME` | S3 bucket region |
| `AWS_CLOUDFRONT_DOMAIN` | CDN asset domain |
| `TWILIO_ACCOUNT_SID` | Twilio account |
| `TWILIO_AUTH_TOKEN` | Twilio secret |
| `TWILIO_PHONE_NUMBER` | OTP sender number |
| `EMAIL_HOST` | SMTP or SES endpoint |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USE_TLS` | SMTP TLS flag |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature secret |
| `FRONTEND_BASE_URL` | Stripe redirect and frontend link base |


Use AWS Secrets Manager or SSM Parameter Store for production secrets. Do not commit `.env`, Firebase service account JSON, Stripe secrets, Twilio secrets, or SMTP credentials.

## 5. Server Architecture

### 5.1 Network Layout

Recommended VPC layout:

| Layer | Placement |
| --- | --- |
| Public subnets | Load balancer, NAT gateway if needed |
| Private app subnets | Django/Nginx containers and Celery workers |
| Private data subnets | RDS and Redis |
| S3 | Access via public AWS endpoint or VPC endpoint |

Security group model:

| Source | Destination | Ports |
| --- | --- | --- |
| Internet | CloudFront/ALB | 443 |
| ALB | Nginx/app service | 80 or app port |
| App service | RDS | 5432 |
| App service | Redis | 6379 |
| App/worker | S3 | HTTPS 443 |
| App/worker | Firebase/Twilio/Stripe/Maps/SMTP | HTTPS/SMTP provider ports |

### 5.2 Load Balancing

Use an Application Load Balancer when running multiple app instances. Requirements:

| Requirement | Reason |
| --- | --- |
| WebSocket support | Chat uses `/ws/` connections |
| Long idle timeout | WebSocket connections need a longer timeout than normal REST requests |
| Health checks | Remove unhealthy app containers from rotation |
| TLS termination | Terminate HTTPS at ALB or CloudFront using wildcard certificate |
| Forwarded headers | Preserve scheme/host/IP for Django settings and audit logs |

Django already has:

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
```

Ensure the load balancer and proxy set `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-For` correctly.

### 5.3 Redundancy

| Component | Redundancy Strategy |
| --- | --- |
| Web containers | Minimum two instances across availability zones |
| Celery workers | Minimum two workers for critical queues where budget allows |
| RDS | Multi-AZ, automated backups, point-in-time restore |
| Redis | Managed Redis with automatic failover if available |
| S3 | Native multi-AZ durability |
| CloudFront | Global edge network |
| DNS | Managed DNS with low-risk TTLs during migration |

## 6. Database Design and Schema Overview

### 6.1 Database Engine

Production database:

| Setting | Value |
| --- | --- |
| Engine | AWS RDS PostgreSQL |
| Extension | PostGIS |
| Django backend | `django.contrib.gis.db.backends.postgis` |
| Primary access pattern | Django ORM |
| Backup | Automated backups with PITR |
| Availability | Multi-AZ recommended |

### 6.2 Schema Domains

| Domain | Key Tables / Models |
| --- | --- |
| Users | `users.User`, `users.Profile`, `users.OTPVerification` |
| Pets | `pet.PetProfile` |
| Social graph | `friends.FriendRequest`, `friends.Friendship`, `friends.UserBlock` |
| Posts | `post.Post`, `post.PostMedia`, `post.PostLike`, `post.PostComment`, `post.SavedPost`, `post.Hashtag` |
| Stories | `story.Story`, `story.StoryView`, `story.StoryReaction`, `story.StoryReply` |
| Blogs | `blog.BlogCategory`, `blog.Blog`, `blog.BlogLike`, `blog.BlogComment`, `blog.BlogViewTracker` |
| Messaging | `messaging.ChatThread`, `messaging.ThreadParticipant`, `messaging.Message` |
| Meetings | `meeting.Meeting`, `meeting.MeetingFeedback` |
| Notifications | `notifications.NotificationSettings`, `notifications.FCMDevice`, `notifications.Notifications` |
| Referrals | `referral.ReferralSettings`, `referral.ReferralWallet`, `referral.ReferralTransaction` |
| Vendor/product | `vendor.VendorPlan`, `vendor.Vendor`, `vendor.VendorSubscription`, `product.Categories`, `product.Brand`, `product.Product`, `product.ProductMedia`, `product.ProductEvent`, `wishlist.ProductWishlist` |
| Tips | `tip.TipSettings`, `tip.StripeConnectAccount`, `tip.Tip`, `tip.TipWithdrawal` |
| Moderation | `report.Report` |
| Settings | `site_settings.SiteSettings` |

### 6.3 Indexing Principles

Use indexes for:

| Query Pattern | Index Strategy |
| --- | --- |
| Feed ordering | Composite indexes on owner/privacy/status/time where applicable |
| Messaging inbox | Thread participant, last message timestamp, unread state |
| Product listings | Category, vendor, active state, brand, created time |
| Product analytics | Product, event type, created time |
| OTP verification | User/identity, OTP type, expiry, consumed status |
| Notifications | Recipient, read state, created time |
| Geospatial discovery | PostGIS GiST/SP-GiST indexes for location fields |

Avoid adding broad indexes without matching a real query. Every index improves reads but adds write cost and storage.

### 6.4 Migration Policy

Production migration rules:

| Rule | Reason |
| --- | --- |
| Run migrations as a release step | Avoid multiple app containers racing migrations |
| Review long-running migrations | Large tables can lock writes |
| Prefer additive migrations | Safer deploy/rollback |
| Backfill with management commands or Celery jobs | Avoid request-time or migration-time table scans |
| Backup before risky schema changes | Protect against destructive mistakes |

## 7. Object Storage, CDN, and Media Delivery

### 7.1 Current State

The current settings use local media and static paths:

```python
MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
```

Docker Compose mounts persistent volumes for media, static files, and temporary uploads.

### 7.2 Production Target

Use S3 for static and uploaded media. Use CloudFront in front of S3 for public asset delivery.

Recommended buckets or prefixes:

| Path | Purpose | Access |
| --- | --- | --- |
| `static/` | Collected Django static files | Public through CloudFront |
| `media/original/` | Original uploads where retained | Private or restricted |
| `media/processed/` | Compressed images, thumbnails, public media | Public through CloudFront where product allows |
| `media/tmp/` | Temporary upload/processing objects | Private with lifecycle expiry |

### 7.3 Recommended Django Storage Setup

The project already includes AWS-related dependencies such as `boto3`, `django-storages`, and `django-ses` in the dependency set. Production settings should add S3-backed storage before launch.

Expected production behavior:

| Asset Type | Storage | Delivery |
| --- | --- | --- |
| Static files | S3 | CloudFront |
| Public media | S3 | CloudFront signed or unsigned URLs depending on privacy |
| Private media | S3 private objects | Signed URLs or authenticated proxy |
| Temporary uploads | S3 or local ephemeral disk | Not public |

### 7.4 Direct Uploads

For large files, direct-to-S3 upload is preferred:

```text
Client asks API for upload authorization
  -> API validates user and intended object type
  -> API returns pre-signed S3 upload URL
  -> Client uploads directly to S3
  -> Client confirms upload to API
  -> Celery processes media and writes database record
```

Benefits:

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

Current settings:

```text
CELERY_BROKER_URL = redis://redis:6379/0
CELERY_RESULT_BACKEND = redis://redis:6379/0
REDIS_URL = redis://redis:6379/1
```

Recommended production separation:

| Workload | Redis Placement |
| --- | --- |
| Celery broker | Dedicated Redis database or cluster |
| Celery results | Disable where not needed or use separate DB with short TTL |
| Django cache | Separate DB/index with eviction policy |
| Channels layer | Separate DB/cluster for realtime stability |
| Rate limiting / OTP/idempotency | Separate key namespace with explicit TTLs |

At low traffic, one managed Redis instance with separate DB indexes is acceptable. At higher traffic, split Celery broker and WebSocket channel layer onto separate Redis instances to avoid queue pressure affecting realtime messaging.

### 8.3 Cacheable Data

| Data | Cache Policy |
| --- | --- |
| Public/static settings | Redis and/or CDN; invalidate on admin settings update |
| Product categories/brands | Redis or CDN; invalidate on category/brand update |
| Product listing first pages | Short TTL Redis/CDN for public filters |
| User profile snippets | Short TTL Redis; invalidate on profile update |
| Messaging inbox first page | Very short TTL; invalidate on new message/read/archive/delete |
| Notification unread counts | Short TTL; invalidate on notification create/read |
| Friend suggestions | Short TTL; invalidate on friend/block changes |
| OTP and rate-limit state | Redis TTL keys; never CDN |
| Media URLs | CloudFront cache; object-key versioning preferred |

### 8.4 Non-Cacheable or Sensitive Data

Do not CDN-cache:

| Data | Reason |
| --- | --- |
| Authenticated user profile mutations | User-specific and sensitive |
| JWT token responses | Security risk |
| OTP responses | Security risk |
| Stripe webhook responses | Must process every event |
| Private messages | User-specific and privacy-sensitive |
| Admin pages | Sensitive operations |
| Private media without signed URLs | Access control risk |

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

Use CloudFront invalidations sparingly because they add operational overhead and may cost money. Preferred pattern:

| Asset Type | Strategy |
| --- | --- |
| Static files | Hashed filenames from `collectstatic`; no invalidation required for normal releases |
| User-uploaded images | Immutable object keys; update DB to new URL after replacement |
| Public generated thumbnails | Versioned paths; invalidate only if object key is reused |
| API responses | Short TTL and cache-key versioning, not broad invalidations |

## 10. Performance Optimization

### 10.1 API Performance

| Technique | Use Case |
| --- | --- |
| Cursor pagination | Feeds, messages, product listings, notification lists |
| `select_related` | Foreign keys such as author, vendor, category |
| `prefetch_related` | Many-to-many and reverse relations |
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
| Vacuum/autovacuum tuning | Important for high-write tables such as messages, events, notifications |
| Partitioning candidates | Product events, notifications, messages, audit-style logs if they become very large |

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
| Queue separation | `otp`, `notifications`, `media`, `default`, `payments` |
| Worker autoscaling | Scale workers by queue depth and task latency |
| Idempotent tasks | Required for retries and duplicate delivery protection |
| Timeouts | External calls must have bounded timeouts |
| Dead-letter/retry policy | Failed tasks should be visible and recoverable |

## 11. Load Balancing and Redundancy

### 11.1 Web Traffic

The application is stateless when media is moved to S3 and sessions/auth use JWT. Multiple web containers can serve the same API traffic behind a load balancer.

Requirements:

| Requirement | Detail |
| --- | --- |
| Shared Redis | Required for cache and Channels across instances |
| Shared DB | RDS is the single durable source of truth |
| Shared object storage | S3 ensures media is available to all instances |
| Health endpoint | Add a lightweight endpoint checking app readiness |
| Graceful shutdown | Preserve in-flight requests during deployment |

### 11.2 WebSocket Traffic

WebSocket scaling requires:

| Requirement | Detail |
| --- | --- |
| Redis Channels layer | Shares events between ASGI workers |
| Load balancer WebSocket support | Upgrade headers and long idle timeout |
| Token refresh strategy | Clients reconnect with valid short-lived access token |
| Connection metrics | Track open sockets, disconnects, send failures |

Sticky sessions are not required when Channels and Redis are correctly configured, but they can reduce reconnect churn in some deployments.

### 11.3 Worker Redundancy

Run more than one worker for critical queues where possible. For provider-facing tasks such as Twilio, Firebase, SES, and Stripe-related processing, enforce idempotency so retries do not duplicate user-visible effects.

## 12. Security and Authentication Infrastructure

### 12.1 Implemented Application Controls

| Control | Implementation |
| --- | --- |
| JWT authentication | SimpleJWT access/refresh tokens |
| Refresh rotation | Enabled in `SIMPLE_JWT` |
| Protected-by-default APIs | DRF default permission is `IsAuthenticated` |
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
| S3 | Block public bucket access; expose public assets through CloudFront policy where possible |
| Admin | Restrict admin by IP/VPN/SSO or additional auth control |
| CORS | Restrict to production frontend origins |
| CSRF | Configure only trusted HTTPS origins |
| Database | Private subnet only, encrypted storage, restricted security group |
| Redis | Private subnet only, encryption/auth where supported |
| Firebase JSON | Store as secret or mounted secret file |
| Webhooks | Validate signatures and keep endpoint paths unguessable where feasible |
| Logging | Do not log OTPs, tokens, passwords, provider secrets, or full payment payloads |

### 12.3 JWT Lifetime Note

The current access token lifetime is configured as 30 days and refresh token lifetime as 7 days. This is unusual because access tokens are typically shorter lived than refresh tokens. Before production launch, review this policy and align it with the mobile app session strategy and risk tolerance.

Recommended baseline:

| Token | Suggested Direction |
| --- | --- |
| Access token | Short-lived, for example minutes to hours |
| Refresh token | Longer-lived, rotated, revocable |
| WebSocket auth | Use valid access token and reconnect after refresh |

## 13. External Service Infrastructure

### 13.1 Firebase

Firebase is used for:

| Feature | Usage |
| --- | --- |
| Push notifications | FCM device token registration and push delivery |
| Google Login | Client obtains Firebase ID token; backend verifies it |
| Apple Login | Client obtains Firebase-backed identity token; backend verifies it |

Production requirements:

| Requirement | Detail |
| --- | --- |
| Service account | Store securely, not in repository |
| Environments | Separate dev/staging/prod Firebase projects where possible |
| Token lifecycle | Remove invalid FCM tokens when provider reports permanent failure |

### 13.2 Twilio

Twilio sends phone OTPs. Protect OTP endpoints with throttles, identity-based limits, attempt counters, and monitoring for spend anomalies.

### 13.3 AWS SES / SMTP

AWS SES or SMTP sends email OTP and transactional email. For SES production:

| Requirement | Detail |
| --- | --- |
| Domain verification | Verify sending domain |
| DKIM/SPF/DMARC | Configure DNS records |
| Sandbox removal | Request production access if needed |
| Bounce handling | Add bounce/complaint monitoring for sender health |

### 13.4 Maps

Google Maps API or Mapbox is primarily a client integration. Backend responsibilities are to store normalized location fields, enforce privacy controls, and support geospatial queries where needed.

### 13.5 Stripe

Stripe handles tips and Connect onboarding. Production requirements:

| Requirement | Detail |
| --- | --- |
| Webhook endpoint | Public HTTPS endpoint with signature validation |
| Idempotency | Protect against duplicate webhook delivery |
| Secret separation | Separate test/live keys |
| Auditability | Persist payment state transitions |

## 14. Observability and Operations

### 14.1 Monitoring

Track:

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

Recommended log policy:

| Log Source | Destination |
| --- | --- |
| Web containers | CloudWatch Logs or centralized log stack |
| Celery workers | CloudWatch Logs or centralized log stack |
| Nginx/ALB | Access logs to S3/CloudWatch |
| RDS | PostgreSQL logs and slow query logs |
| CloudFront | Access logs where needed |

Logs should include request IDs/correlation IDs so API requests, Celery jobs, and external-provider callbacks can be traced together.

### 14.3 Alerts

Minimum production alerts:

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
| RDS PostgreSQL | Automated backups, point-in-time restore, manual snapshots before risky releases | Restore database to known-good point |
| S3 media | Versioning and lifecycle rules; optional cross-region replication for higher durability | Recover deleted/overwritten objects |
| Environment secrets | Managed secret store with access audit | Recreate runtime safely |
| Container images | ECR image retention | Roll back to previous release |
| Infrastructure config | IaC repository recommended | Rebuild environment consistently |

Disaster recovery runbook should include:

1. Identify failure scope.
2. Freeze risky deployments.
3. Restore database or roll forward from latest healthy backup.
4. Verify S3/media integrity.
5. Redeploy known-good image.
6. Reprocess failed Celery tasks where safe.
7. Validate login, OTP, feed, media, messaging, notifications, and payments.

## 16. Production Readiness Checklist

| Item | Status |
| --- | --- |
| AWS account access confirmed | Required |
| Domain DNS access confirmed | Required |
| Wildcard certificate issued | Required |
| RDS PostgreSQL/PostGIS created | Required |
| Redis managed service created | Recommended |
| S3 buckets created with lifecycle policies | Required |
| CloudFront distribution configured | Required |
| Django S3 storage configured | Required before media production scale |
| Firebase project and service account configured | Required |
| Twilio configured and OTP tested | Required |
| SES/SMTP configured and email OTP tested | Required |
| Stripe live/test separation configured | Required for tips |
| Production secrets moved out of repository | Required |
| Health endpoint added | Recommended before load-balanced deployment |
| Database backup and restore tested | Required |
| Celery queues monitored | Recommended |
| Admin access restricted | Required |

## 17. Current Gaps to Close

| Gap | Impact | Recommended Action |
| --- | --- | --- |
| Local media storage in settings | App instances cannot scale cleanly with uploaded media | Configure S3 storage and CloudFront asset URLs |
| Single Redis for all workloads | Cache/queue/WebSocket contention under load | Separate Redis DBs now; split instances later |
| No visible health endpoint | Load balancer cannot perform application-aware checks | Add `/health/` or `/api/health/` |
| Migrations run in entrypoint | Multiple production instances can race migrations | Use one-off migration job in deployment pipeline |
| Celery Beat absent | Scheduled cleanup/reconciliation not managed | Add Beat if periodic tasks are required |
| Product/wishlist routes not mounted | Product APIs may not be publicly accessible | Mount URLs if marketplace API is required |
| Access token lifetime review needed | Long-lived access tokens increase exposure window | Revisit JWT lifetime policy before production |

## 18. Summary

PetNabor should run as a stateless Django ASGI application and Celery worker fleet backed by AWS-managed stateful services. RDS PostgreSQL/PostGIS is the source of truth, Redis coordinates cache/tasks/realtime delivery, S3 stores media/static assets, and CloudFront delivers assets globally. Firebase, Twilio, AWS SES/SMTP, Maps, and Stripe provide specialized external capabilities.

The most important production infrastructure shift is moving away from single-host local state. Once database, media, Redis, secrets, logs, health checks, and deployment orchestration are managed cleanly, the current modular-monolith application can scale horizontally without a premature microservice migration.
