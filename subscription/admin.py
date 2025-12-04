from django.contrib import admin
from .models import SubscriptionPlan, AnnualDiscount, Subscription, PaymentHistory, UsageTracking
from .forms import SubscriptionPlanAdminForm



@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    form = SubscriptionPlanAdminForm
    list_display = ('name', 'monthly_price', 'annual_price', 'effective_annual_discount', 'is_active')
    list_editable = ('monthly_price', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('annual_price', 'stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id', 'effective_annual_discount')
    ordering = ('monthly_price',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'monthly_price', 'annual_discount_percent', 'is_active')
        }),
        ('Usage Limits - Events', {
            'fields': (('events_limit', 'events_period'),),
            'description': 'Configure event creation limits. Leave limit blank for unlimited.'
        }),
        ('Usage Limits - Tasks', {
            'fields': (('tasks_limit', 'tasks_period'),),
            'description': 'Configure task creation limits. Leave limit blank for unlimited.'
        }),
        ('Usage Limits - Notes', {
            'fields': (('notes_limit', 'notes_period'),),
            'description': 'Configure note creation limits. Leave limit blank for unlimited.'
        }),
        ('Usage Limits - Edits', {
            'fields': (('edits_limit', 'edits_period'),),
            'description': 'Configure edit limits. Leave limit blank for unlimited.'
        }),
        ('Stripe Integration', {
            'fields': ('stripe_product_id', 'stripe_monthly_price_id', 'stripe_annual_price_id'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            print(f"✅ Plan '{obj.name}' updated via admin")
        else:
            print(f"✅ Plan '{obj.name}' created via admin")



@admin.register(AnnualDiscount)
class AnnualDiscountAdmin(admin.ModelAdmin):
    list_display = ('annual_discount_percent', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        if AnnualDiscount.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'billing_interval', 'status', 'current_period_end', 'is_active', 'is_paid')
    list_filter = ('status', 'billing_interval', 'plan')
    search_fields = ('user__email', 'plan__name')
    readonly_fields = ('stripe_customer_id', 'stripe_subscription_id', 'current_period_start', 'current_period_end', 'cancel_at_period_end', 'created_at', 'updated_at')


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'plan', 'billing_interval', 'amount', 'payment_status', 'created_at')
    list_filter = ('transaction_type', 'payment_status', 'billing_interval', 'plan')
    search_fields = ('user__email', 'plan__name', 'stripe_invoice_id', 'stripe_payment_intent_id')
    readonly_fields = ('stripe_invoice_id', 'proration_amount', 'created_at')
    ordering = ('-created_at',)


@admin.register(UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_type', 'period_type', 'count', 'period_start', 'period_end')
    list_filter = ('item_type', 'period_type', 'period_start')
    search_fields = ('user__email',)
    readonly_fields = ('user', 'item_type', 'period_type', 'count', 'period_start', 'period_end', 'created_at', 'updated_at')
    ordering = ('-period_start', 'user__email')
    
    def has_add_permission(self, request):
        # Created automatically
        return False
