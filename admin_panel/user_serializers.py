from rest_framework import serializers
from django.contrib.auth import get_user_model
from subscription.models import SubscriptionPlan

User = get_user_model()


class UnifiedUserUpdateSerializer(serializers.Serializer):
    """
    Unified serializer for updating user's subscription plan and status.
    All fields are optional - send only what you want to update.
    """
    # Subscription change fields
    plan_id = serializers.UUIDField(required=False, help_text="New subscription plan UUID")
    billing_interval = serializers.ChoiceField(
        choices=['month', 'year'],
        required=False,
        help_text="Billing interval for subscription"
    )
    
    # Status change fields
    is_active = serializers.BooleanField(required=False, help_text="User active status (false = ban)")
    reason = serializers.CharField(required=False, allow_blank=True, help_text="Reason for status change")
    
    def validate_plan_id(self, value):
        """Validate that the plan exists"""
        try:
            SubscriptionPlan.objects.get(id=value)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid plan ID")
        return value
    
    def validate(self, data):
        """Ensure at least one field is provided"""
        if not any(key in data for key in ['plan_id', 'is_active']):
            raise serializers.ValidationError(
                "At least one of 'plan_id' or 'is_active' must be provided"
            )
        return data
