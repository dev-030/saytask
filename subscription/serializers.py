from rest_framework import serializers
from .models import SubscriptionPlan, AnnualDiscount, Subscription, PaymentHistory
import stripe
from django.conf import settings
from decimal import Decimal
from django.utils import timezone



stripe.api_key = settings.STRIPE_SECRET_KEY





class SubscriptionPlanSerializer(serializers.ModelSerializer):
    annual_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    annual_discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True, required=False)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'monthly_price', 'annual_price',
            'annual_discount_percent', 'effective_annual_discount',
            'stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id',
            'effective_annual_discount', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        plan_name = data.get("name", getattr(self.instance, "name", None))
        if plan_name == "free":
            if "monthly_price" in data and data["monthly_price"] not in [0, "0", None]:
                raise serializers.ValidationError({"monthly_price": "Free plan cannot have a price."})

            if data.get("annual_discount_percent") is not None:
                raise serializers.ValidationError(
                    {"annual_discount_percent": "Free plan cannot have an annual discount."}
                )

        return data

    def create(self, validated_data):        
        if validated_data["name"] == "free":
            print("hello")
            validated_data["monthly_price"] = 0
            validated_data["annual_discount_percent"] = None
            return super().create(validated_data)
    
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

        old_name = instance.name
        old_monthly_price = instance.monthly_price
        old_annual_price = instance.annual_price  

        new_name = validated_data.get('name', old_name)
        new_monthly_price = validated_data.get('monthly_price', old_monthly_price)
        new_discount = validated_data.get('annual_discount_percent', instance.annual_discount_percent)

        temp = SubscriptionPlan(
            monthly_price=new_monthly_price,
            annual_discount_percent=new_discount
        )
        new_annual_price = temp.annual_price

        if instance.stripe_product_id and new_name != old_name:
            stripe.Product.modify(instance.stripe_product_id, name=new_name)

        monthly_price_changed = False
        annual_price_changed = False
        
        if instance.stripe_product_id and new_monthly_price != old_monthly_price:
            new_monthly_price_id = self._update_stripe_price(
                instance.stripe_product_id,
                instance.stripe_monthly_price_id,
                new_monthly_price,
                interval='month'
            )
            validated_data['stripe_monthly_price_id'] = new_monthly_price_id
            monthly_price_changed = True

        if instance.stripe_product_id and new_annual_price != old_annual_price:
            new_annual_price_id = self._update_stripe_price(
                instance.stripe_product_id,
                instance.stripe_annual_price_id,
                new_annual_price,
                interval='year'
            )
            validated_data['stripe_annual_price_id'] = new_annual_price_id
            annual_price_changed = True

        updated_instance = super().update(instance, validated_data)
        
        return updated_instance

    def _update_stripe_price(self, product_id, old_price_id, new_amount, interval):
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




class AnnualDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnualDiscount
        fields = ['id', 'annual_discount_percent', 'updated_at']
        read_only_fields = ['id', 'updated_at']

    def validate_annual_discount_percent(self, value):
        if value < 0:
            raise serializers.ValidationError("Discount percent cannot be negative.")
        return value

    def update(self, instance, validated_data):
        old_value = instance.annual_discount_percent
        new_value = validated_data.get('annual_discount_percent', old_value)
        instance = super().update(instance, validated_data)
        if new_value != old_value:
            self._update_all_plans(new_value)
        return instance
    

    def _update_all_plans(self, new_discount):
        plans = SubscriptionPlan.objects.filter(annual_discount_percent__isnull=True)
        for plan in plans:
            old_annual_price = plan.annual_price
            yearly = plan.monthly_price * 12
            discount = Decimal(new_discount)
            new_annual_price = (yearly * (Decimal(100) - discount) / 100).quantize(Decimal("0.01"))

            if new_annual_price != old_annual_price:
                if plan.stripe_annual_price_id:
                    try:
                        stripe.Price.modify(plan.stripe_annual_price_id, active=False)
                    except Exception:
                        pass

                new_price = stripe.Price.create(
                    product=plan.stripe_product_id,
                    currency='usd',
                    unit_amount=int(new_annual_price * 100),
                    recurring={"interval": "year"},
                    metadata={'interval': 'year'}
                )
                plan.stripe_annual_price_id = new_price.id
                plan.save(update_fields=['stripe_annual_price_id'])


class PaymentMethodSerializer(serializers.Serializer):
    id = serializers.CharField()
    brand = serializers.CharField()
    last4 = serializers.CharField()
    exp_month = serializers.IntegerField()
    exp_year = serializers.IntegerField()
    is_default = serializers.BooleanField()


class CreateCheckoutSessionSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(queryset=SubscriptionPlan.objects.exclude(name='free'))
    billing_interval = serializers.ChoiceField(choices=Subscription.BILLING_INTERVAL_CHOICES)


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = '__all__'
        read_only_fields = '__all__'
