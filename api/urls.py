from django.urls import path, include


urlpatterns = [
    path("users/", include("api.users.urls")),
    path("notifications/", include("api.notifications.urls")),
    path("pets/", include("api.pet.urls")),
    path("friends/", include("api.friends.urls")),
    path("messaging/", include("api.messaging.urls")),
    path("post/", include("api.post.urls")),
    path("report/", include("api.report.urls")),
    path("story/", include("api.story.urls")),
    path("blog/", include("api.blog.urls")),
    path("vendor/", include("api.vendor.urls")),
    path("meetings/", include("api.meeting.urls")),
    path("referral/", include("api.referral.urls")),
]
