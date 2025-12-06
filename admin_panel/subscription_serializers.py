"""
Serializers for admin subscription plan management with usage limits.
"""

from rest_framework import serializers
from subscription.models import SubscriptionPlan
from decimal import Decimal
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


class UsageLimitField(serializers.Serializer):
    """Nested serializer for usage limits"""
    limit = serializers.IntegerField(required=False, allow_null=True, help_text="Leave null for unlimited")
    period = serializers.ChoiceField(
        choices=[
            ('minute', 'Per Minute'),
            ('hour', 'Per Hour'),
            ('day', 'Per Day'),
            ('week', 'Per Week'),
            ('month', 'Per Month'),
        ],
        default='week'
    )


class AdminSubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Admin serializer for full subscription plan management including usage limits.
    Handles Stripe sync automatically when prices are updated.
    """
    # Pricing fields
    annual_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    effective_annual_discount = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    # Usage limits (extracted from features JSONField)
    event_limits = UsageLimitField(required=False, allow_null=True)
    task_limits = UsageLimitField(required=False, allow_null=True)
    note_limits = UsageLimitField(required=False, allow_null=True)
    edit_limits = UsageLimitField(required=False, allow_null=True)
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'monthly_price', 'annual_price',
            'annual_discount_percent', 'effective_annual_discount',
            'event_limits', 'task_limits', 'note_limits', 'edit_limits',
            'stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'annual_price', 'effective_annual_discount',
            'stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id',
            'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        """Extract usage limits from features JSONField for display"""
        representation = super().to_representation(instance)
        
        features = instance.features or {}
        
        # Extract limits from JSONField
        representation['event_limits'] = features.get('event', {'limit': None, 'period': 'week'})
        representation['task_limits'] = features.get('task', {'limit': None, 'period': 'week'})
        representation['note_limits'] = features.get('note', {'limit': None, 'period': 'week'})
        representation['edit_limits'] = features.get('edit', {'limit': None, 'period': 'month'})
        
        return representation
    
    def validate(self, data):
        """Validate plan data and usage limits"""
        plan_name = data.get("name", getattr(self.instance, "name", None))
        
        # Free plan validation
        if plan_name == "free":
            if "monthly_price" in data and data["monthly_price"] not in [0, "0", None, Decimal('0')]:
                raise serializers.ValidationError({"monthly_price": "Free plan cannot have a price."})
            
            if data.get("annual_discount_percent") is not None:
                raise serializers.ValidationError(
                    {"annual_discount_percent": "Free plan cannot have an annual discount."}
                )
        
        # Validate usage limits structure
        for limit_type in ['event_limits', 'task_limits', 'note_limits', 'edit_limits']:
            if limit_type in data and data[limit_type] is not None:
                limit_data = data[limit_type]
                if 'limit' in limit_data and limit_data['limit'] is not None:
                    if limit_data['limit'] < 0:
                        raise serializers.ValidationError({
                            limit_type: "Limit cannot be negative. Use null for unlimited."
                        })
        
        return data
    
    def create(self, validated_data):
        """Create subscription plan and sync with Stripe"""
        # Extract usage limits
        event_limits = validated_data.pop('event_limits', {'limit': None, 'period': 'week'})
        task_limits = validated_data.pop('task_limits', {'limit': None, 'period': 'week'})
        note_limits = validated_data.pop('note_limits', {'limit': None, 'period': 'week'})
        edit_limits = validated_data.pop('edit_limits', {'limit': None, 'period': 'month'})
        
        # Build features JSONField
        validated_data['features'] = {
            'event': event_limits,
            'task': task_limits,
            'note': note_limits,
            'edit': edit_limits,
        }
        
        # Handle free plan
        if validated_data["name"] == "free":
            validated_data["monthly_price"] = 0
            validated_data["annual_discount_percent"] = None
            return super().create(validated_data)
        
        # Create Stripe product and prices for paid plans
        plan = SubscriptionPlan(**validated_data)
        annual_price = int(plan.annual_price * 100)
        
        product = stripe.Product.create(name=validated_data['name'])
        validated_data['stripe_product_id'] = product.id
        
        monthly_price_obj = stripe.Price.create(
            product=product.id,
            currency='usd',
            unit_amount=int(validated_data['monthly_price'] * 100),
            recurring={"interval": "month"},
            metadata={'plan_name': validated_data['name'], 'interval': 'month'}
        )
        validated_data['stripe_monthly_price_id'] = monthly_price_obj.id
        
        annual_price_obj = stripe.Price.create(
            product=product.id,
            currency='usd',
            unit_amount=annual_price,
            recurring={"interval": "year"},
            metadata={'plan_name': validated_data['name'], 'interval': 'year'}
        )
        validated_data['stripe_annual_price_id'] = annual_price_obj.id
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update subscription plan and sync with Stripe"""
        # Extract usage limits
        event_limits = validated_data.pop('event_limits', None)
        task_limits = validated_data.pop('task_limits', None)
        note_limits = validated_data.pop('note_limits', None)
        edit_limits = validated_data.pop('edit_limits', None)
        
        # Update features JSONField if limits are provided
        features = instance.features or {}
        if event_limits is not None:
            features['event'] = event_limits
        if task_limits is not None:
            features['task'] = task_limits
        if note_limits is not None:
            features['note'] = note_limits
        if edit_limits is not None:
            features['edit'] = edit_limits
        
        validated_data['features'] = features
        
        # Free plan restrictions
        if instance.name == "free":
            if "monthly_price" in validated_data:
                raise serializers.ValidationError({"monthly_price": "Free plan price cannot be changed."})
            if "annual_discount_percent" in validated_data:
                raise serializers.ValidationError(
                    {"annual_discount_percent": "Free plan cannot have discounts."}
                )
            if "name" in validated_data and validated_data["name"] != "free":
                raise serializers.ValidationError({"name": "Free plan name cannot be changed."})
            return super().update(instance, validated_data)
        
        # Handle price updates with Stripe sync
        old_monthly_price = instance.monthly_price
        old_annual_price = instance.annual_price
        old_name = instance.name
        
        new_name = validated_data.get('name', old_name)
        new_monthly_price = validated_data.get('monthly_price', old_monthly_price)
        new_discount = validated_data.get('annual_discount_percent', instance.annual_discount_percent)
        
        # Calculate new annual price
        temp = SubscriptionPlan(
            monthly_price=new_monthly_price,
            annual_discount_percent=new_discount
        )
        new_annual_price = temp.annual_price
        
        # Update Stripe product name if changed
        if instance.stripe_product_id and new_name != old_name:
            stripe.Product.modify(instance.stripe_product_id, name=new_name)
        
        # Update monthly price in Stripe if changed
        if instance.stripe_product_id and new_monthly_price != old_monthly_price:
            new_monthly_price_id = self._update_stripe_price(
                instance.stripe_product_id,
                instance.stripe_monthly_price_id,
                new_monthly_price,
                interval='month'
            )
            validated_data['stripe_monthly_price_id'] = new_monthly_price_id
        
        # Update annual price in Stripe if changed
        if instance.stripe_product_id and new_annual_price != old_annual_price:
            new_annual_price_id = self._update_stripe_price(
                instance.stripe_product_id,
                instance.stripe_annual_price_id,
                new_annual_price,
                interval='year'
            )
            validated_data['stripe_annual_price_id'] = new_annual_price_id
        
        return super().update(instance, validated_data)
    
    def _update_stripe_price(self, product_id, old_price_id, new_amount, interval):
        """Create new Stripe price and deactivate old one"""
        if old_price_id:
            try:
                stripe.Price.modify(old_price_id, active=False)
            except stripe.error.StripeError:
                pass
        
        new_price = stripe.Price.create(
            product=product_id,
            currency='usd',
            unit_amount=int(Decimal(str(new_amount)) * 100),
            recurring={"interval": interval},
            metadata={'interval': interval}
        )
        return new_price.id


class SubscriptionPlanBulkUpdateSerializer(serializers.Serializer):
    """Serializer for bulk updating usage limits across multiple plans"""
    plan_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of plan IDs to update"
    )
    event_limits = UsageLimitField(required=False, allow_null=True)
    task_limits = UsageLimitField(required=False, allow_null=True)
    note_limits = UsageLimitField(required=False, allow_null=True)
    edit_limits = UsageLimitField(required=False, allow_null=True)
