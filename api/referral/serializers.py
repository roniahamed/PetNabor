"""
Referral serializers.
"""
from rest_framework import serializers

from .models import ReferralTransaction, ReferralWallet


class ReferralTransactionSerializer(serializers.ModelSerializer):
    related_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ReferralTransaction
        fields = [
            "id",
            "transaction_type",
            "status",
            "amount",
            "note",
            "related_user_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_related_user_name(self, obj):
        if obj.related_user:
            return (
                f"{obj.related_user.first_name or ''} {obj.related_user.last_name or ''}".strip()
                or obj.related_user.email
                or str(obj.related_user.phone)
            )
        return None


class ReferralWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralWallet
        fields = ["balance"]
        read_only_fields = fields


class ReferralMemberSerializer(serializers.Serializer):
    """A single referred member (for the dashboard members list)."""
    id = serializers.UUIDField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    profile_picture = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        request = self.context.get("request")
        try:
            pic = obj.profile.profile_picture
            if pic and request:
                return request.build_absolute_uri(pic.url)
            return None
        except Exception:
            return None


class ReferralDashboardSerializer(serializers.Serializer):
    """Full dashboard payload."""
    referral_code = serializers.CharField()
    total_earned = serializers.DecimalField(max_digits=12, decimal_places=2)
    joined_count = serializers.IntegerField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    members = ReferralMemberSerializer(many=True)
