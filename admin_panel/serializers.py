from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import LegalDocument, ActivityLog
from subscription.models import Subscription, SubscriptionPlan, PaymentHistory
from subscription.serializers import SubscriptionPlanSerializer

User = get_user_model()


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'user_email', 'user_name', 'action', 'action_display', 
                  'description', 'amount', 'created_at']
        read_only_fields = ['id', 'created_at']


class LegalDocumentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    
    class Meta:
        model = LegalDocument
        fields = ['id', 'document_type', 'content', 'version', 'created_by', 
                  'created_by_email', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Subscription
        fields = ['id', 'plan', 'plan_name', 'billing_interval', 'status', 
                  'current_period_start', 'current_period_end', 'cancel_at_period_end',
                  'current_price', 'created_at', 'updated_at']


class UserManagementSerializer(serializers.ModelSerializer):
    subscription = UserSubscriptionSerializer(source='subscriptions', read_only=True)
    subscription_plan = serializers.CharField(source='subscriptions.plan.name', read_only=True)
    subscription_status = serializers.CharField(source='subscriptions.status', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'username', 'is_active', 'date_joined',
                  'subscription', 'subscription_plan', 'subscription_status', 
                  'is_google_auth', 'is_apple_auth']
        read_only_fields = ['id', 'date_joined', 'is_google_auth', 'is_apple_auth']


class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'username']
        read_only_fields = ['id']


class AdminPasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value


class SubscriptionUpdateSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField(required=True)
    billing_interval = serializers.ChoiceField(choices=['month', 'year'], required=False)
    
    def validate_plan_id(self, value):
        try:
            SubscriptionPlan.objects.get(id=value)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid plan ID")
        return value


class UserStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)
