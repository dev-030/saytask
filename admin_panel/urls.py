from django.urls import path
from .views import (
    AdminDashboardView,
    TotalUsersView,
    LastMonthUsersView,
    ActiveSubscriptionsView,
    LastMonthActiveSubscriptionsView,
    TotalPaymentsView,
    LastMonthPaymentsView,
    UserListView
)



urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('users/total/', TotalUsersView.as_view(), name='total-users'),
    path('users/last-month/', LastMonthUsersView.as_view(), name='last-month-users'),
    path('users/list/', UserListView.as_view(), name='user-list'),
    path('subscriptions/active/', ActiveSubscriptionsView.as_view(), name='active-subscriptions'),
    path('subscriptions/last-month/', LastMonthActiveSubscriptionsView.as_view(), name='last-month-subscriptions'),
    path('payments/total/', TotalPaymentsView.as_view(), name='total-payments'),
    path('payments/last-month/', LastMonthPaymentsView.as_view(), name='last-month-payments'),
]
