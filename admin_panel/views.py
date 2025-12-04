from rest_framework import permissions, views, response, status
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from subscription.models import Subscription, PaymentHistory


User = get_user_model()


class AdminDashboardView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        now = timezone.now()
        last_month_start = now - timedelta(days=30)
        
        total_users = User.objects.count()
        last_month_users = User.objects.filter(date_joined__gte=last_month_start).count()
        
        active_subscriptions = Subscription.objects.filter(
            status__in=['active', 'trialing']
        ).count()
        
        last_month_active_subs = Subscription.objects.filter(
            status__in=['active', 'trialing'],
            created_at__gte=last_month_start
        ).count()
        
        total_payments = PaymentHistory.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        last_month_payments = PaymentHistory.objects.filter(
            created_at__gte=last_month_start
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return response.Response({
            'users': {
                'total': total_users,
                'last_month': last_month_users
            },
            'subscriptions': {
                'active': active_subscriptions,
                'last_month_active': last_month_active_subs
            },
            'payments': {
                'total': float(total_payments),
                'last_month': float(last_month_payments)
            }
        }, status=status.HTTP_200_OK)


class TotalUsersView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        total = User.objects.count()
        return response.Response({'total_users': total}, status=status.HTTP_200_OK)


class LastMonthUsersView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        last_month_start = timezone.now() - timedelta(days=30)
        count = User.objects.filter(date_joined__gte=last_month_start).count()
        return response.Response({'last_month_users': count}, status=status.HTTP_200_OK)


class ActiveSubscriptionsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        count = Subscription.objects.filter(
            status__in=['active', 'trialing']
        ).count()
        return response.Response({'active_subscriptions': count}, status=status.HTTP_200_OK)


class LastMonthActiveSubscriptionsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        last_month_start = timezone.now() - timedelta(days=30)
        count = Subscription.objects.filter(
            status__in=['active', 'trialing'],
            created_at__gte=last_month_start
        ).count()
        return response.Response({'last_month_active_subscriptions': count}, status=status.HTTP_200_OK)


class TotalPaymentsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        total = PaymentHistory.objects.aggregate(total=Sum('amount'))['total'] or 0
        return response.Response({'total_payments': float(total)}, status=status.HTTP_200_OK)


class LastMonthPaymentsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        last_month_start = timezone.now() - timedelta(days=30)
        total = PaymentHistory.objects.filter(
            created_at__gte=last_month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        return response.Response({'last_month_payments': float(total)}, status=status.HTTP_200_OK)


class UserListView(views.APIView):
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        users = User.objects.all().values(
            'id', 'email', 'username', 'full_name', 'is_active', 
            'date_joined', 'is_google_auth', 'is_apple_auth'
        ).order_by('-date_joined')
        
        return response.Response({'users': list(users)}, status=status.HTTP_200_OK)
