from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet, AnnualDiscountViewSet, CheckoutSessionViewSet,
    PaymentHistoryViewSet, PaymentMethodViewSet, CancelSubscriptionViewSet, CustomerPortalViewSet, stripe_webhook
)

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='plan')
router.register(r"annual-discount", AnnualDiscountViewSet, basename="annual-discount")
router.register(r'checkout', CheckoutSessionViewSet, basename='create-checkout-session')
router.register(r'payment-history', PaymentHistoryViewSet, basename='payment-history')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'cancel', CancelSubscriptionViewSet, basename='cancel-subscription')
router.register(r'customer-portal', CustomerPortalViewSet, basename='customer-portal')



urlpatterns = [
    path('', include(router.urls)),
    path("stripe/webhook/", stripe_webhook, name="stripe-webhook"),
]