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
        read_only_fields = ['id', 'document_type', 'created_by', 'created_at', 'updated_at']


class SimplePlanSerializer(serializers.ModelSerializer):
    """Minimal serializer for subscription plan in user list"""
    class Meta:
        model = SubscriptionPlan
        fields = ['name', 'monthly_price']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SimplePlanSerializer(read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Subscription
        fields = ['id', 'plan', 'plan_name', 'billing_interval', 'status', 
                  'stripe_subscription_id', 'current_period_start', 'current_period_end', 
                  'cancel_at_period_end', 'current_price', 'created_at']


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
    # Optional password fields
    old_password = serializers.CharField(required=False, write_only=True)
    new_password = serializers.CharField(required=False, write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'username', 'old_password', 'new_password']
        read_only_fields = ['id']
        extra_kwargs = {
            'email': {'required': False},
            'full_name': {'required': False},
            'username': {'required': False},
        }
    
    def validate_email(self, value):
        """Ensure email is unique across all users"""
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email address is already in use by another user.")
        return value
    
    def validate_username(self, value):
        """Ensure username is unique across all users"""
        user = self.instance
        if value and User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This username is already in use by another user.")
        return value
    
    def validate(self, data):
        """Validate password change logic"""
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        # If either password field is provided, both must be provided
        if old_password and not new_password:
            raise serializers.ValidationError({
                'new_password': 'New password is required when changing password.'
            })
        
        if new_password and not old_password:
            raise serializers.ValidationError({
                'old_password': 'Old password is required to change password.'
            })
        
        # If both provided, validate old password
        if old_password and new_password:
            user = self.instance
            if not user.check_password(old_password):
                raise serializers.ValidationError({
                    'old_password': 'Old password is incorrect.'
                })
        
        return data
    
    def update(self, instance, validated_data):
        """Update profile and optionally password"""
        # Extract password fields
        old_password = validated_data.pop('old_password', None)
        new_password = validated_data.pop('new_password', None)
        
        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update password if both were provided and validated
        if old_password and new_password:
            instance.set_password(new_password)
        
        instance.save()
        return instance


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
