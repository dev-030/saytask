from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import subscription_views

# Router for viewsets
router = DefaultRouter()
router.register(r'users', views.UserManagementViewSet, basename='user-management')
router.register(r'subscription-plans', subscription_views.AdminSubscriptionPlanViewSet, basename='admin-subscription-plan')

urlpatterns = [
    # === NEW UNIFIED APIS ===
    # Dashboard
    path('dashboard/', views.UnifiedDashboardView.as_view(), name='admin-dashboard'),
    path('subscriptions/analytics/', views.SubscriptionAnalyticsView.as_view(), name='subscription-analytics'),
    
    # User Management (includes viewset routes via router)
    path('', include(router.urls)),
    
    # Admin Profile
    path('profile/', views.AdminProfileView.as_view(), name='admin-profile'),
    path('profile/password/', views.AdminPasswordChangeView.as_view(), name='admin-password-change'),
    
    # Legal Documents
    path('legal/terms/', views.TermsAndConditionsView.as_view(), name='terms-and-conditions'),
    path('legal/privacy/', views.PrivacyPolicyView.as_view(), name='privacy-policy'),
    
    # === LEGACY ENDPOINTS (for backward compatibility) ===
    path('total-users/', views.TotalUsersView.as_view(), name='total-users'),
    path('last-month-users/', views.LastMonthUsersView.as_view(), name='last-month-users'),
    path('active-subscriptions/', views.ActiveSubscriptionsView.as_view(), name='active-subscriptions'),
    path('last-month-active-subscriptions/', views.LastMonthActiveSubscriptionsView.as_view(), name='last-month-active-subscriptions'),
    path('total-payments/', views.TotalPaymentsView.as_view(), name='total-payments'),
    path('last-month-payments/', views.LastMonthPaymentsView.as_view(), name='last-month-payments'),
    path('user-list/', views.UserListView.as_view(), name='user-list'),
]
