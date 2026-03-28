"""
PetNabor Admin Dashboard utilities.

Provides:
  - dashboard_callback  → custom Unfold dashboard with KPI cards + charts
  - environment_callback → environment badge (Development / Production)
  - user_count_badge     → live user count shown in sidebar navigation
  - pending_reports_badge → unresolved reports count shown in sidebar
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ──────────────────────────────────────────────
# Sidebar badge callbacks
# ──────────────────────────────────────────────


def user_count_badge(request) -> str:
    """Show total active user count next to 'Users' in the sidebar."""
    from .models import User

    count = User.objects.filter(is_active=True).count()
    return str(count) if count else ""


def pending_reports_badge(request) -> str:
    """Show count of unresolved reports next to 'Reports' in the sidebar."""
    try:
        from api.report.models import Report

        count = Report.objects.filter(is_resolved=False).count()
        return str(count) if count else ""
    except Exception:
        return ""


# ──────────────────────────────────────────────
# Environment label
# ──────────────────────────────────────────────


def environment_callback(request):
    """Return a colored environment badge shown in the admin header."""
    from django.conf import settings

    if settings.DEBUG:
        return _("Development"), "warning"
    return _("Production"), "danger"


# ──────────────────────────────────────────────
# Dashboard callback
# ──────────────────────────────────────────────


def dashboard_callback(request, context: dict) -> dict:
    """
    Populate the Unfold custom dashboard with KPI cards and charts.

    All queries are lightweight aggregates — no N+1 issues.
    """
    from .models import User

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── KPI totals ────────────────────────────────────────────────────────────
    total_users = User.objects.filter(is_active=True).count()
    new_today = User.objects.filter(created_at__gte=today_start).count()
    new_this_week = User.objects.filter(created_at__gte=week_ago).count()

    try:
        from api.post.models import Post

        total_posts = Post.objects.filter(is_deleted=False).count()
    except Exception:
        total_posts = 0

    try:
        from api.pet.models import PetProfile

        total_pets = PetProfile.objects.count()
    except Exception:
        total_pets = 0

    try:
        from api.report.models import Report

        pending_reports = Report.objects.filter(is_resolved=False).count()
        total_reports = Report.objects.count()
    except Exception:
        pending_reports = 0
        total_reports = 0

    try:
        from api.story.models import Story

        active_stories = Story.objects.filter(expires_at__gt=now).count()
    except Exception:
        active_stories = 0

    try:
        from api.blog.models import Blog

        total_blogs = Blog.objects.filter(is_published=True, is_deleted=False).count()
    except Exception:
        total_blogs = 0

    try:
        from api.referral.models import ReferralWallet
        from django.db.models import Sum

        total_referral_points = (
            ReferralWallet.objects.aggregate(total=Sum("balance"))["total"] or 0
        )
    except Exception:
        total_referral_points = 0

    # ── User registrations — last 30 days (for line chart) ────────────────────
    registration_qs = (
        User.objects.filter(created_at__gte=month_ago)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    reg_labels = [str(row["day"]) for row in registration_qs]
    reg_data = [row["count"] for row in registration_qs]

    # ── User type distribution (for donut chart) ───────────────────────────────
    user_type_qs = (
        User.objects.values("user_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    user_type_labels = [row["user_type"].capitalize() for row in user_type_qs]
    user_type_data = [row["count"] for row in user_type_qs]

    # ── Top pet types ──────────────────────────────────────────────────────────
    try:
        from api.pet.models import PetProfile

        pet_type_qs = (
            PetProfile.objects.values("pet_type")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
        pet_labels = [row["pet_type"] for row in pet_type_qs]
        pet_data = [row["count"] for row in pet_type_qs]
    except Exception:
        pet_labels, pet_data = [], []

    # ── Friend request statuses ────────────────────────────────────────────────
    try:
        from api.friends.models import FriendRequest

        fr_qs = (
            FriendRequest.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        fr_labels = [row["status"].capitalize() for row in fr_qs]
        fr_data = [row["count"] for row in fr_qs]
    except Exception:
        fr_labels, fr_data = [], []

    # ── Recent new users (activity feed) ──────────────────────────────────────
    recent_users = User.objects.order_by("-created_at").select_related("profile")[:8]

    # ── Build context ──────────────────────────────────────────────────────────
    context.update(
        {
            # KPI cards
            "kpi_cards": [
                {
                    "title": "Total Users",
                    "metric": f"{total_users:,}",
                    "icon": "people",
                    "color": "purple",
                    "change": f"+{new_this_week} this week",
                    "positive": True,
                },
                {
                    "title": "New Today",
                    "metric": f"{new_today:,}",
                    "icon": "person_add",
                    "color": "blue",
                    "change": f"+{new_this_week} this week",
                    "positive": True,
                },
                {
                    "title": "Total Posts",
                    "metric": f"{total_posts:,}",
                    "icon": "article",
                    "color": "green",
                    "change": "Active posts",
                    "positive": True,
                },
                {
                    "title": "Pet Profiles",
                    "metric": f"{total_pets:,}",
                    "icon": "pets",
                    "color": "orange",
                    "change": "Registered pets",
                    "positive": True,
                },
                {
                    "title": "Active Stories",
                    "metric": f"{active_stories:,}",
                    "icon": "auto_stories",
                    "color": "pink",
                    "change": "Live now",
                    "positive": True,
                },
                {
                    "title": "Published Blogs",
                    "metric": f"{total_blogs:,}",
                    "icon": "rss_feed",
                    "color": "teal",
                    "change": "Published articles",
                    "positive": True,
                },
                {
                    "title": "Pending Reports",
                    "metric": f"{pending_reports:,}",
                    "icon": "flag",
                    "color": "red",
                    "change": f"{total_reports} total reports",
                    "positive": False,
                },
                {
                    "title": "Referral Points",
                    "metric": f"{total_referral_points:,.0f}",
                    "icon": "wallet",
                    "color": "yellow",
                    "change": "Total distributed",
                    "positive": True,
                },
            ],
            # Charts data (consumed by the dashboard template)
            "registration_chart": {
                "labels": reg_labels,
                "data": reg_data,
            },
            "user_type_chart": {
                "labels": user_type_labels,
                "data": user_type_data,
            },
            "pet_type_chart": {
                "labels": pet_labels,
                "data": pet_data,
            },
            "friend_request_chart": {
                "labels": fr_labels,
                "data": fr_data,
            },
            # Activity feed
            "recent_users": recent_users,
        }
    )
    return context
