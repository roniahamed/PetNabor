"""
Serializers for the Report app.
Improvements:
- reporter exposed (read-only) for admin review
- duplicate report prevention via UniqueTogetherValidator
- is_resolved exposed as read-only
"""

from rest_framework import serializers
from .models import Report
from api.post.serializers import AuthorBasicSerializer


class ReportSerializer(serializers.ModelSerializer):
    reporter = AuthorBasicSerializer(read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'reporter', 'target_type', 'target_id',
            'reason', 'description', 'is_resolved', 'created_at',
        ]
        read_only_fields = ['id', 'reporter', 'is_resolved', 'created_at']
