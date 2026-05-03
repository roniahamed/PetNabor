# PetNabor Architectural Overview and Backend Infrastructure

## 1. Executive Summary

PetNabor is a Django-based backend platform for a pet-focused social network and marketplace ecosystem. The backend exposes REST APIs for mobile/web clients, WebSocket APIs for realtime chat, an admin dashboard for operations, and background workers for media processing, notifications, OTP delivery, and other asynchronous jobs.

The current architecture is a modular monolith: one Django project contains multiple domain apps, each owning a specific business capability. This keeps development and deployment simple while still separating the codebase by domain boundaries such as users, pets, posts, stories, messaging, meetings, notifications, referrals, vendors, products, tips, and moderation.

## 2. High-Level System Architecture

```text
Client Apps
  |-- Mobile app / Web frontend
  |-- Admin users
  `-- External service webhooks
        |
        v
Host Nginx / TLS
        |
        v
Docker Nginx Reverse Proxy
  |-- Serves /static/
  |-- Serves /media/
  |-- Proxies REST/Admin traffic
  `-- Proxies WebSocket traffic
        |
        v
Django ASGI Application
  |-- Django REST Framework APIs
  |-- Django Admin
  |-- Django Channels WebSocket consumer
  `-- Business service layer
        |
        |--------------|--------------|--------------|
        v              v              v              v
PostgreSQL/PostGIS   Redis          Celery Worker   External Services
Source of truth      Cache, broker  Async jobs      Firebase, Twilio,
GIS queries          channel layer  media/tasks     SMTP, Stripe, Sentry
```

## 3. Backend Technology Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Backend framework | Django 5.x | Main application framework |
| API framework | Django REST Framework | REST API views, serializers, permissions, pagination |
| API documentation | drf-spectacular | OpenAPI schema, Swagger UI, Redoc |
| Runtime protocol | ASGI | Supports both HTTP and WebSocket traffic |
| HTTP app server | Gunicorn + Uvicorn worker | Production ASGI process |
| Realtime | Django Channels + channels-redis | WebSocket chat and realtime event delivery |
| Database | PostgreSQL 16 + PostGIS | Relational data and geolocation support |
| Cache / broker | Redis 7 | Django cache, Celery broker/result backend, Channels layer |
| Background jobs | Celery | OTP, notifications, media processing, referral jobs |
| Authentication | SimpleJWT + Firebase Admin | JWT auth, refresh tokens, Firebase login verification |
| Push notifications | Firebase Cloud Messaging | Device push notification delivery |
| SMS | Twilio | Phone OTP delivery |
| Email | SMTP via Django email backend | Email OTP and password reset delivery |
| Payments | Stripe / Stripe Connect | Tip payments, recipient onboarding, payouts, webhooks |
| Admin UI | Django Admin + django-unfold | Internal operations dashboard |
| Deployment | Docker Compose + Nginx | Single-host containerized deployment |
| Monitoring | Sentry SDK | Error and trace reporting when configured |

## 4. Application Boundaries

| App | Responsibility |
| --- | --- |
| `api.users` | Custom user model, signup, login, Firebase login, JWT refresh, OTP verification, password reset, profile media |
| `api.pet` | Pet profiles, pet metadata, pet image processing |
| `api.friends` | Friend requests, friendships, blocking, public user details, friend suggestions |
| `api.post` | Posts, privacy, media, hashtags, likes, comments, replies, saved posts |
| `api.story` | 24-hour stories, story views, reactions, replies, story media |
| `api.blog` | Blog categories, blog posts, likes, comments, view tracking, blog media |
| `api.messaging` | Direct/group chat threads, participants, messages, WebSocket chat, message notifications |
| `api.meeting` | Meeting requests and meeting feedback |
| `api.notifications` | Notification settings, FCM devices, persisted notifications, push fan-out |
| `api.report` | User/content reporting and moderation workflow |
| `api.referral` | Referral settings, wallet, transaction ledger, reward awarding, redemption |
| `api.vendor` | Vendor profiles, vendor plans, subscriptions |
| `api.product` | Product categories, brands, products, product media, product analytics/events |
| `api.wishlist` | Product wishlist model |
| `api.tip` | Stripe Connect onboarding, tips, held transfers, withdrawals, Stripe webhooks |
| `api.site_settings` | Global site/admin configuration |

## 5. API Surface

The root API router is mounted at `/api/`.

| Base Path | Module |
| --- | --- |
| `/api/users/` | Signup, login, OTP, Firebase login, token refresh, user/profile |
| `/api/notifications/` | Notifications, settings, FCM devices |
| `/api/pets/` | Pet profile APIs |
| `/api/friends/` | Friend request, search, suggestions, block/unfriend |
| `/api/messaging/` | Inbox, threads, messages, read/delete/archive flows |
| `/api/post/` | Posts, comments, saved posts, user posts |
| `/api/report/` | Reports |
| `/api/story/` | Stories and story actions |
| `/api/blog/` | Blogs and blog comments |
| `/api/vendor/` | Vendor APIs |
| `/api/referral/` | Referral dashboard, transactions, verify, redeem |
| `/api/settings/` | Global settings |
| `/api/tip/` | Stripe Connect, send tip, history, balance, withdraw, webhook |
| `/api/meetings/` | Meeting requests and feedback |

API documentation is available from:

| Path | Purpose |
| --- | --- |
| `/api/schema/` | OpenAPI schema |
| `/api/swagger/` | Swagger UI |
| `/api/docs/` | Redoc documentation |

Note: `api.product` and `api.wishlist` are installed and represented in the admin/model layer. In the current root router, dedicated public `/api/product/` and `/api/wishlist/` routes are not mounted.

## 6. Data Architecture

PostgreSQL with PostGIS is the primary database. Django ORM models define the schema and relationships.

Main data groups:

| Data Group | Primary Models |
| --- | --- |
| Identity | `User`, `Profile`, `OTPVerification` |
| Pets | `PetProfile` |
| Social graph | `FriendRequest`, `Friendship`, `UserBlock` |
| Posts | `Post`, `PostMedia`, `PostLike`, `PostComment`, `SavedPost`, `Hashtag` |
| Stories | `Story`, `StoryView`, `StoryReaction`, `StoryReply` |
| Blogs | `BlogCategory`, `Blog`, `BlogLike`, `BlogComment`, `BlogViewTracker` |
| Messaging | `ChatThread`, `ThreadParticipant`, `Message` |
| Meetings | `Meeting`, `MeetingFeedback` |
| Notifications | `NotificationSettings`, `FCMDevice`, `Notifications` |
| Referrals | `ReferralSettings`, `ReferralWallet`, `ReferralTransaction` |
| Vendors/products | `VendorPlan`, `Vendor`, `VendorSubscription`, `Categories`, `Brand`, `Product`, `ProductMedia`, `ProductEvent`, `ProductWishlist` |
| Tips/payments | `TipSettings`, `StripeConnectAccount`, `Tip`, `TipWithdrawal` |
| Moderation | `Report` |
| Site configuration | `SiteSettings` |

PostGIS support is enabled through `django.contrib.gis` and the PostGIS database backend, allowing profile/location-aware features and future nearby-user or nearby-pet discovery.

## 7. Authentication and Authorization

The backend uses a custom Django user model: `AUTH_USER_MODEL = "users.User"`.

Authentication paths:

| Flow | Description |
| --- | --- |
| Email/phone signup | Creates user and sends OTP verification |
| Email/phone login | Issues JWT access/refresh tokens |
| Firebase login | Verifies Firebase ID token through Firebase Admin SDK |
| OTP verification | Supports phone and email verification |
| Password reset | OTP-based password reset workflow |
| Token refresh | SimpleJWT refresh endpoint |

REST APIs are authenticated by default through `JWTAuthentication`. Most endpoints require authentication unless a view explicitly opens access.

The WebSocket layer uses custom JWT middleware. Clients connect to:

```text
/ws/chat/?token=<access_token>
```

The middleware validates the access token and attaches the authenticated user to the WebSocket scope.

## 8. Realtime Messaging Architecture

Realtime chat is implemented with Django Channels.

Flow:

1. Client opens a WebSocket connection to `/ws/chat/?token=<access_token>`.
2. Nginx upgrades the request and proxies it to the ASGI app.
3. `JWTAuthMiddleware` authenticates the token.
4. `ChatConsumer` handles socket events and thread/message interactions.
5. Redis Channels layer coordinates realtime delivery between app workers.
6. New message push notifications are delegated to Celery through `notify_new_message`.

Redis is also used for messaging-related caches such as inbox first page, message permission checks, and short-lived thread lists.

## 9. Background Job Architecture

Celery workers run alongside the web process. Redis is configured as both broker and result backend.

Configured Redis URLs:

```text
CELERY_BROKER_URL = redis://redis:6379/0
CELERY_RESULT_BACKEND = redis://redis:6379/0
REDIS_URL = redis://redis:6379/1
```

Main background jobs:

| App | Jobs |
| --- | --- |
| `api.users` | Email OTP, SMS OTP, profile media processing |
| `api.pet` | Pet image processing |
| `api.post` | Post media processing, comment media processing |
| `api.story` | Story media processing |
| `api.blog` | Blog view tracking, blog cover processing, blog comment media processing |
| `api.messaging` | New message push notifications |
| `api.notifications` | Notification fan-out, FCM delivery, idempotent notification persistence |
| `api.referral` | Referral points awarding |

This keeps user-facing requests responsive by moving slow or retryable work out of the HTTP request lifecycle.

## 10. Media and File Upload Architecture

Current media handling is local-volume based:

| Setting | Role |
| --- | --- |
| `MEDIA_ROOT=/app/media` | Runtime uploaded media |
| `STATIC_ROOT=/app/staticfiles` | Collected static files |
| `FILE_UPLOAD_TEMP_DIR=/app/tmp_uploads` | Temporary upload location |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | Configurable up to 5GB by environment |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | Configurable request body limit |

Docker volumes persist media, static files, and temporary uploads:

```text
media_volume       -> /app/media
static_volume      -> /app/staticfiles
tmp_uploads_volume -> /app/tmp_uploads
```

Nginx is configured with `client_max_body_size 5000M`, long proxy timeouts, and disabled request buffering for large uploads.

The requirements include AWS/S3-related packages (`boto3`, `django-storages`, `django-ses`), but current settings do not actively configure S3 storage. The active deployment uses local Docker volumes for media.

## 11. Notification Architecture

Notification capabilities include:

| Component | Purpose |
| --- | --- |
| `NotificationSettings` | User-level notification preferences |
| `FCMDevice` | Registered Firebase device token records |
| `Notifications` | Persisted in-app notifications |
| Firebase Admin SDK | Push delivery through FCM |
| Celery | Async fan-out and retry |
| Redis cache | Idempotency and duplicate prevention |

Message notifications are designed as transient push notifications in the messaging task and do not always create database notification rows.

## 12. Payment and Tip Infrastructure

The tip system uses Stripe and Stripe Connect.

Main capabilities:

| Capability | Description |
| --- | --- |
| Connect onboarding | Creates or resumes recipient Stripe Connect onboarding |
| Connect status | Syncs account capability and payout readiness |
| Send tip | Creates PaymentIntent and records tip state |
| Held tips | Holds recipient transfer when recipient has not completed Connect onboarding |
| Transfer release | Releases held funds after recipient account becomes valid |
| Withdraw | Creates Stripe payout from connected account balance |
| Webhook | Receives Stripe payment, refund, account, and payout events |
| Admin settings | Stores tip commission/minimum/currency style settings |

Sensitive Stripe operations are centralized in `api.tip.services`; views call service functions instead of talking to Stripe directly.

## 13. Deployment Infrastructure

The project includes a Docker Compose deployment stack.

Services:

| Service | Image/Command | Responsibility |
| --- | --- | --- |
| `db` | `postgis/postgis:16-3.4-alpine` | PostgreSQL + PostGIS database |
| `redis` | `redis:7-alpine` | Cache, Channels layer, Celery broker/result backend |
| `web` | Built from `Dockerfile` | Django ASGI app via Gunicorn/Uvicorn |
| `celery` | Built from `Dockerfile` | Background task worker |
| `nginx` | `nginx:1.25-alpine` | Reverse proxy and static/media serving |

The web command:

```bash
gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers 4
```

The entrypoint performs:

1. Create `/app/tmp_uploads`.
2. Run `python manage.py collectstatic --no-input`.
3. Run `python manage.py migrate`.
4. Execute the service command.

Host-level Nginx is also documented for `backend.petnabor.com`. It terminates TLS with Let's Encrypt certificates and proxies traffic to the Docker Nginx port.

## 14. Request Lifecycle

Typical REST request:

```text
Client
  -> Host Nginx HTTPS
  -> Docker Nginx
  -> Gunicorn/Uvicorn ASGI worker
  -> Django middleware
  -> DRF view/viewset
  -> Serializer/service layer
  -> PostgreSQL/Redis/external service
  -> JSON response
```

Typical WebSocket message:

```text
Client
  -> /ws/chat/?token=<JWT>
  -> Nginx WebSocket upgrade
  -> Django Channels JWT middleware
  -> ChatConsumer
  -> Database write/read
  -> Redis channel layer broadcast
  -> Recipient clients
  -> Celery push notification task when needed
```

Typical async task:

```text
DRF view/service
  -> task.delay(...)
  -> Redis broker
  -> Celery worker
  -> Database/media/external service
  -> retry or persist result as needed
```

## 15. Security Controls

Implemented controls:

| Control | Implementation |
| --- | --- |
| JWT API authentication | SimpleJWT access/refresh tokens |
| Refresh token rotation | Enabled in settings |
| Protected-by-default APIs | DRF default permission is `IsAuthenticated` |
| WebSocket authentication | JWT query-token middleware |
| OTP rate limits | DRF throttle rates for OTP send/verify and login |
| Action-level throttles | Per-user limits for messaging, likes, comments, saves |
| CSRF trusted origins | Environment-driven plus production host |
| Reverse proxy SSL awareness | `SECURE_PROXY_SSL_HEADER` and forwarded host/port support |
| Firebase token verification | Firebase Admin SDK |
| Stripe webhook validation | Stripe signature verification in tip services |
| Sentry data filtering | Authorization headers are scrubbed before sending events |
| User verification middleware | Verification enforcement middleware in request stack |

Production recommendations:

| Area | Recommendation |
| --- | --- |
| `DEBUG` | Must be `False` in production |
| Secrets | Store `.env` outside source control and rotate leaked credentials |
| Allowed hosts/CORS | Restrict to production frontend/admin domains |
| Cookies/HTTPS | Add strict secure cookie/HSTS settings if browser session auth is used |
| WebSocket token | Prefer short-lived access tokens and reconnect refresh handling |
| Uploads | Consider virus scanning and object storage for large-scale production media |
| Admin | Restrict admin access by VPN/IP allowlist or additional authentication |

## 16. Observability and Operations

Current operational features:

| Feature | Description |
| --- | --- |
| Sentry | Optional error reporting for Django, Celery, Redis integrations |
| Django Admin | Operational dashboard for users, content, reports, referrals, tips, vendors, products |
| OpenAPI docs | API inspection and integration testing |
| Docker restart policies | Services use `restart: always` |
| Persistent volumes | Database, static, media, temporary upload directories |

Recommended operational additions:

| Area | Addition |
| --- | --- |
| Logs | Centralized container logs with retention |
| Metrics | CPU, memory, request latency, DB connections, Redis memory, Celery queue length |
| Health checks | `/health/` endpoint plus Docker health checks |
| Backups | Automated PostgreSQL and media backups |
| Alerting | Error-rate, worker-down, disk-space, database backup failure alerts |
| CI/CD | Automated tests, migrations, image build, and controlled deployment |

## 17. Environment Configuration

Important environment variables:

| Variable | Purpose |
| --- | --- |
| `DEBUG` | Enables/disables debug mode |
| `SECRET_KEY` | Django cryptographic secret |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `CSRF_TRUSTED_ORIGINS` | Trusted CSRF origins |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed for browser calls |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | Database host, `db` in Docker |
| `POSTGRES_PORT` | Database port |
| `REDIS_URL` | Redis cache and Channels URL |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Twilio sender phone number |
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USE_TLS` | SMTP TLS flag |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `OTP_LENGTH` | OTP length |
| `OTP_EXPIRY_MINUTES` | OTP validity window |
| `OTP_MAX_ATTEMPTS` | OTP verification attempt limit |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature secret |
| `FRONTEND_BASE_URL` | Frontend redirect base URL for Stripe Connect |
| `SENTRY_DSN` | Sentry project DSN |
| `SENTRY_ENVIRONMENT` | Sentry environment name |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sampling rate |

## 18. Scalability Path

The current modular-monolith architecture can scale vertically and horizontally before requiring service extraction.

Near-term scaling:

| Area | Scaling Approach |
| --- | --- |
| Web traffic | Increase Gunicorn workers and run multiple web containers |
| WebSockets | Keep Redis Channels as shared layer and run multiple ASGI workers/containers |
| Background jobs | Run multiple Celery workers and split queues by workload |
| Database | Add indexes, query optimization, backups, read replica if needed |
| Media | Move from local volume to S3-compatible object storage/CDN |
| Cache | Tune Redis memory policy and separate broker/cache/Channels Redis if load grows |
| Uploads | Direct-to-object-storage uploads for large media |

Possible future service extraction candidates:

| Candidate | Reason |
| --- | --- |
| Media processing | CPU and storage intensive |
| Notifications | High fan-out and external dependency latency |
| Messaging | Realtime scale and low-latency requirements |
| Payments/tips | Strong isolation and audit requirements |

## 19. Current Infrastructure Notes and Gaps

| Item | Current State |
| --- | --- |
| Database | Dockerized PostGIS with persistent volume |
| Redis | Single Redis instance shared by cache, Channels, and Celery |
| Static/media | Served by Docker Nginx from shared volumes |
| TLS | Host-level Nginx config supports Let's Encrypt cert paths |
| Migrations | Run automatically at container startup |
| Product API | Product models/admin exist, but root API router does not mount product URLs |
| Wishlist API | Wishlist model exists, but root API router does not mount wishlist URLs |
| S3 | Dependencies exist, but current settings use local storage |
| Health endpoint | No dedicated health endpoint found in current URL config |
| Scheduled jobs | Celery worker exists; Celery Beat is not configured in Docker Compose |

## 20. Client-Facing Summary

PetNabor is built as a production-ready Django REST and WebSocket backend. It uses PostgreSQL/PostGIS for durable relational and geolocation data, Redis for cache/realtime/task infrastructure, Celery for asynchronous processing, and Nginx/Gunicorn/Uvicorn for production traffic handling. The project is organized into clear domain modules, which allows the team to maintain one deployable backend while keeping business logic separated by feature area.

The backend already supports the key infrastructure expected for a social app: secure JWT authentication, OTP and Firebase login, pet/user profiles, posts/stories/blogs, realtime messaging, push notifications, referrals, moderation, vendor/product data, Stripe-powered tips, admin management, OpenAPI documentation, Docker deployment, and production reverse-proxy configuration.
