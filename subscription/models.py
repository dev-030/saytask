from django.db import models
from decimal import Decimal
from django.contrib.auth import get_user_model
import uuid
from django.core.exceptions import ValidationError






User = get_user_model()





class AnnualDiscount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    annual_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=22.00)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Annual Discount Setting"
        verbose_name_plural = "Annual Discount Setting"

    def __str__(self):
        return f"Annual discount: {self.annual_discount_percent}%"
    
    def save(self, *args, **kwargs):
        if not self.pk and AnnualDiscount.objects.exists():
            raise ValueError("Only one AnnualDiscount instance allowed.")
        return super().save(*args, **kwargs)




class SubscriptionPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('premium', 'Premium'),
    ]

    name = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free', unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)

    features = models.JSONField(default=dict, blank=True)

    annual_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    stripe_product_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_monthly_price_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_annual_price_id = models.CharField(max_length=100, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['monthly_price']

    def clean(self):
        if self.name == "free":
            if self.monthly_price not in [0, None]:
                raise ValidationError({"monthly_price": "Free plan cannot have a price."})
            if self.annual_discount_percent is not None:
                raise ValidationError({"annual_discount_percent": "Free plan cannot have a discount."})

    def save(self, *args, **kwargs):
        self.full_clean()  
        super().save(*args, **kwargs)

    @property
    def effective_annual_discount(self):
        if self.monthly_price == 0:
            return Decimal("0.00")  
        if self.annual_discount_percent is not None:
            return self.annual_discount_percent
        discount = AnnualDiscount.objects.first()
        return discount.annual_discount_percent if discount else Decimal("0.00")
    
    @property
    def annual_price(self):
        discount = Decimal(self.effective_annual_discount)
        yearly = (self.monthly_price or 0) *12
        discounted = yearly * (Decimal(100) - discount) / 100
        return discounted.quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.name} - ${self.monthly_price}/month"

    class Meta:
        verbose_name = "Subscription Plan"




class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    BILLING_INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Annual'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trialing', 'Trial'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('incomplete', 'Incomplete'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="user_subscriptions")
    billing_interval = models.CharField(
        max_length=10,
        choices=BILLING_INTERVAL_CHOICES,
        default='month'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )

    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self):
        return self.status in ['active', 'trialing']
    
    @property
    def is_paid(self):
        return self.plan.name != 'free' and self.is_active

    @property
    def current_price(self):
        if self.billing_interval == 'year':
            return self.plan.annual_price
        return self.plan.monthly_price

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.billing_interval})"





class PaymentHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    TRANSACTION_TYPE_CHOICES = [
        ('initial', 'Initial Subscription'),
        ('renewal', 'Subscription Renewal'),
        ('upgrade', 'Plan Upgrade'),
        ('downgrade', 'Plan Downgrade'),
        ('interval_change', 'Billing Interval Change'),
        ('cancellation', 'Cancellation'),
        ('refund', 'Refund'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_history')

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    billing_interval = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)    
    proration_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    hosted_invoice_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['stripe_invoice_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - ${self.amount}"





class UsageTracking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usage_tracking')    
    ITEM_TYPE_CHOICES = [
        ('event', 'Event'),
        ('task', 'Task'),
        ('note', 'Note'),
        ('edit', 'Edit'),
    ]
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)    
    PERIOD_TYPE_CHOICES = [
        ('minute', 'Per Minute'),
        ('hour', 'Per Hour'),
        ('day', 'Per Day'),
        ('week', 'Per Week'),
        ('month', 'Per Month'),
    ]
    period_type = models.CharField(max_length=10, choices=PERIOD_TYPE_CHOICES)
    count = models.IntegerField(default=0)
    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Usage Tracking"
        unique_together = ['user', 'item_type', 'period_type', 'period_start']
        indexes = [
            models.Index(fields=['user', 'item_type', 'period_start']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        ordering = ['-period_start', 'user__email']
    
    def __str__(self):
        return f"{self.user.email} - {self.item_type} ({self.count}/{self.period_type})"
