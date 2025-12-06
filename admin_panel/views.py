from rest_framework import permissions, views, response, status, viewsets
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import timedelta
from decimal import Decimal
import stripe
from django.conf import settings

from subscription.models import Subscription, PaymentHistory, SubscriptionPlan, UsageTracking
from actions.models import Event, Task, Note
from .models import ActivityLog, LegalDocument
from .serializers import (
    ActivityLogSerializer, LegalDocumentSerializer, UserManagementSerializer,
    AdminProfileSerializer, AdminPasswordChangeSerializer, SubscriptionUpdateSerializer,
    UserStatusUpdateSerializer, UserSubscriptionSerializer
)

User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY


# ==================== UNIFIED DASHBOARD API ====================

class UnifiedDashboardView(views.APIView):
    """
    Single endpoint that returns all dashboard data:
    - User statistics
    - Subscription statistics  
    - Payment statistics
    - Monthly active users chart data
    - Subscription growth chart data
    - Recent activities
    """
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        now = timezone.now()
        last_month_start = now - timedelta(days=30)
        
        # === USER STATISTICS ===
        total_users = User.objects.count()
        last_month_users = User.objects.filter(date_joined__gte=last_month_start).count()
        prev_month_start = last_month_start - timedelta(days=30)
        prev_month_users = User.objects.filter(
            date_joined__gte=prev_month_start, 
            date_joined__lt=last_month_start
        ).count()
        users_growth = self._calculate_growth(last_month_users, prev_month_users)
        
        # === SUBSCRIPTION STATISTICS ===
        active_subscriptions = Subscription.objects.filter(
            status__in=['active', 'trialing']
        ).count()
        last_month_active_subs = Subscription.objects.filter(
            status__in=['active', 'trialing'],
            created_at__gte=last_month_start
        ).count()
        prev_month_active_subs = Subscription.objects.filter(
            status__in=['active', 'trialing'],
            created_at__gte=prev_month_start,
            created_at__lt=last_month_start
        ).count()
        subs_growth = self._calculate_growth(last_month_active_subs, prev_month_active_subs)
        
        # === PAYMENT STATISTICS ===
        total_payments = PaymentHistory.objects.filter(
            payment_status='succeeded'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        last_month_payments = PaymentHistory.objects.filter(
            payment_status='succeeded',
            created_at__gte=last_month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        prev_month_payments = PaymentHistory.objects.filter(
            payment_status='succeeded',
            created_at__gte=prev_month_start,
            created_at__lt=last_month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        payments_growth = self._calculate_growth(
            float(last_month_payments or 0), 
            float(prev_month_payments or 0)
        )
        
        # === MONTHLY ACTIVE USERS (12 months chart data) ===
        monthly_active_users = self._get_monthly_active_users(12)
        
        # === SUBSCRIPTION GROWTH (12 months chart data) ===
        subscription_growth_data = self._get_subscription_growth(12)
        
        # === RECENT ACTIVITIES ===
        recent_activities = ActivityLog.objects.select_related('user').all()[:10]
        activities_data = ActivityLogSerializer(recent_activities, many=True).data
        
        return response.Response({
            'overview': {
                'total_users': {
                    'value': total_users,
                    'growth': users_growth,
                    'last_month': last_month_users
                },
                'active_subscriptions': {
                    'value': active_subscriptions,
                    'growth': subs_growth,
                    'last_month': last_month_active_subs
                },
                'total_payments': {
                    'value': float(total_payments),
                    'growth': payments_growth,
                    'last_month': float(last_month_payments)
                }
            },
            'charts': {
                'monthly_active_users': monthly_active_users,
                'subscription_growth': subscription_growth_data
            },
            'recent_activities': activities_data
        }, status=status.HTTP_200_OK)
    
    def _calculate_growth(self, current, previous):
        """Calculate percentage growth"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)
    
    def _get_monthly_active_users(self, months=12):
        """Get monthly active users for the last N months"""
        data = []
        now = timezone.now()
        
        for i in range(months):
            month_start = (now - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            count = User.objects.filter(
                date_joined__gte=month_start,
                date_joined__lte=month_end
            ).count()
            
            data.insert(0, {
                'month': month_start.strftime('%b'),
                'year': month_start.year,
                'count': count
            })
        
        return data
    
    def _get_subscription_growth(self, months=12):
        """Get subscription growth by plan for the last N months"""
        data = []
        now = timezone.now()
        
        for i in range(months):
            month_start = (now - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            premium_count = Subscription.objects.filter(
                plan__name='premium',
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            
            unlimited_count = Subscription.objects.filter(
                plan__name='unlimited',
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            
            data.insert(0, {
                'month': month_start.strftime('%b'),
                'year': month_start.year,
                'premium': premium_count,
                'unlimited': unlimited_count
            })
        
        return data


# ==================== SUBSCRIPTION ANALYTICS API ====================

class SubscriptionAnalyticsView(views.APIView):
    """
    Subscription breakdown by tier with user counts, revenue, and task limits
    """
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        analytics = []
        plans = SubscriptionPlan.objects.all()
        
        for plan in plans:
            # Get subscriptions for this plan
            subs = Subscription.objects.filter(plan=plan, status__in=['active', 'trialing'])
            user_count = subs.count()
            
            # Calculate monthly revenue (only for active paid plans)
            monthly_revenue = 0
            if plan.name != 'free':
                for sub in subs:
                    if sub.billing_interval == 'month':
                        monthly_revenue += float(plan.monthly_price)
                    else:  # annual
                        monthly_revenue += float(plan.annual_price / 12)
            
            # Get task limits from plan features
            task_limit = plan.features.get('limits', {}).get('tasks_per_week', 'Unlimited')
            
            # Calculate growth
            last_month_start = timezone.now() - timedelta(days=30)
            last_month_count = Subscription.objects.filter(
                plan=plan,
                status__in=['active', 'trialing'],
                created_at__gte=last_month_start
            ).count()
            prev_month_start = last_month_start - timedelta(days=30)
            prev_month_count = Subscription.objects.filter(
                plan=plan,
                status__in=['active', 'trialing'],
                created_at__gte=prev_month_start,
                created_at__lt=last_month_start
            ).count()
            
            growth = 0
            if prev_month_count > 0:
                growth = round(((last_month_count - prev_month_count) / prev_month_count) * 100, 2)
            elif last_month_count > 0:
                growth = 100.0
            
            analytics.append({
                'tier': plan.name.capitalize(),
                'users': user_count,
                'monthly_revenue': round(monthly_revenue, 2),
                'task_limit': task_limit,
                'growth': growth
            })
        
        return response.Response({'analytics': analytics}, status=status.HTTP_200_OK)


# ==================== USER MANAGEMENT APIs ====================

class UserManagementViewSet(viewsets.ModelViewSet):
    """
    Complete user management with search, filtering, and CRUD operations
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = UserManagementSerializer
    
    def get_queryset(self):
        queryset = User.objects.select_related('subscriptions', 'subscriptions__plan').all()
        
        # Search by name or email
        search = self.request.query_params.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) | 
                Q(full_name__icontains=search) |
                Q(username__icontains=search)
            )
        
        # Filter by status
        status_filter = self.request.query_params.get('status', '')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'suspended':
            queryset = queryset.filter(is_active=False)
        
        # Filter by subscription plan
        subscription_filter = self.request.query_params.get('subscription', '')
        if subscription_filter:
            queryset = queryset.filter(subscriptions__plan__name=subscription_filter)
        
        return queryset.order_by('-date_joined')
    
    @action(detail=True, methods=['patch'], url_path='subscription')
    def update_subscription(self, request, pk=None):
        """Update user's subscription plan and sync with Stripe"""
        user = self.get_object()
        serializer = SubscriptionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_id = serializer.validated_data['plan_id']
        billing_interval = serializer.validated_data.get('billing_interval', 'month')
        
        new_plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        subscription = get_object_or_404(Subscription, user=user)
        
        old_plan = subscription.plan
        
        # If same plan, return early
        if subscription.plan == new_plan and subscription.billing_interval == billing_interval:
            return response.Response(
                {'detail': 'User is already on this plan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Update Stripe subscription if it exists
            if subscription.stripe_subscription_id:
                price_id = new_plan.stripe_monthly_price_id if billing_interval == 'month' else new_plan.stripe_annual_price_id
                
                if not price_id:
                    return response.Response(
                        {'detail': f'Plan {new_plan.name} is missing Stripe price ID'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                    items=[{
                        'id': stripe_sub['items']['data'][0].id,
                        'price': price_id
                    }],
                    proration_behavior='always_invoice'
                )
            
            # Update local database
            subscription.plan = new_plan
            subscription.billing_interval = billing_interval
            subscription.save()
            
            # Log activity
            ActivityLog.objects.create(
                user=user,
                action='subscription_updated',
                description=f'Subscription changed from {old_plan.name} to {new_plan.name} by admin {request.user.email}'
            )
            
            return response.Response({
                'detail': 'Subscription updated successfully',
                'old_plan': old_plan.name,
                'new_plan': new_plan.name
            }, status=status.HTTP_200_OK)
            
        except stripe.error.StripeError as e:
            return response.Response(
                {'detail': f'Stripe error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['patch'], url_path='update')
    def unified_update(self, request, pk=None):
        """
        Unified endpoint to update user's subscription plan and/or active status.
        All fields are optional - send only what you want to update.
        """
        from .user_serializers import UnifiedUserUpdateSerializer
        
        user = self.get_object()
        serializer = UnifiedUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = {'changes': []}
        
        # Handle subscription plan change
        if 'plan_id' in serializer.validated_data:
            plan_id = serializer.validated_data['plan_id']
            billing_interval = serializer.validated_data.get('billing_interval', 'month')
            
            new_plan = get_object_or_404(SubscriptionPlan, id=plan_id)
            subscription = get_object_or_404(Subscription, user=user)
            old_plan = subscription.plan
            
            # Check if already on this plan
            if subscription.plan != new_plan or subscription.billing_interval != billing_interval:
                try:
                    # Update Stripe subscription if it exists
                    if subscription.stripe_subscription_id:
                        price_id = new_plan.stripe_monthly_price_id if billing_interval == 'month' else new_plan.stripe_annual_price_id
                        
                        if not price_id:
                            return response.Response(
                                {'detail': f'Plan {new_plan.name} is missing Stripe price ID'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        
                        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                        stripe.Subscription.modify(
                            subscription.stripe_subscription_id,
                            cancel_at_period_end=False,
                            items=[{
                                'id': stripe_sub['items']['data'][0].id,
                                'price': price_id
                            }],
                            proration_behavior='always_invoice'
                        )
                    
                    # Update local database
                    subscription.plan = new_plan
                    subscription.billing_interval = billing_interval
                    subscription.save()
                    
                    # Log activity
                    ActivityLog.objects.create(
                        user=user,
                        action='subscription_updated',
                        description=f'Subscription changed from {old_plan.name} to {new_plan.name} by admin {request.user.email}'
                    )
                    
                    result['changes'].append(f'Subscription updated: {old_plan.name} → {new_plan.name}')
                    
                except stripe.error.StripeError as e:
                    return response.Response(
                        {'detail': f'Stripe error: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # Handle status change
        if 'is_active' in serializer.validated_data:
            is_active = serializer.validated_data['is_active']
            reason = serializer.validated_data.get('reason', '')
            
            if user.is_active != is_active:
                try:
                    subscription = Subscription.objects.get(user=user)
                    
                    if not is_active:  # Banning user
                        # Cancel Stripe subscription immediately
                        if subscription.stripe_subscription_id:
                            stripe.Subscription.cancel(subscription.stripe_subscription_id)
                        
                        # Update local subscription
                        subscription.status = 'canceled'
                        subscription.stripe_subscription_id = None
                        subscription.save()
                        
                        # Deactivate user
                        user.is_active = False
                        user.save()
                        
                        # Log activity
                        ActivityLog.objects.create(
                            user=user,
                            action='user_suspended',
                            description=f'User suspended by admin {request.user.email}. Reason: {reason or "No reason provided"}'
                        )
                        
                        result['changes'].append(f'User banned. Reason: {reason or "No reason provided"}')
                    
                    else:  # Reactivating user
                        user.is_active = True
                        user.save()
                        
                        # Log activity
                        ActivityLog.objects.create(
                            user=user,
                            action='user_reactivated',
                            description=f'User reactivated by admin {request.user.email}'
                        )
                        
                        result['changes'].append('User reactivated')
                
                except Subscription.DoesNotExist:
                    # If no subscription exists, just update user status
                    user.is_active = is_active
                    user.save()
                    
                    action_type = 'user_reactivated' if is_active else 'user_suspended'
                    ActivityLog.objects.create(
                        user=user,
                        action=action_type,
                        description=f'User {"reactivated" if is_active else "suspended"} by admin {request.user.email}'
                    )
                    
                    result['changes'].append(f'User {"reactivated" if is_active else "banned"}')
                
                except stripe.error.StripeError as e:
                    return response.Response(
                        {'detail': f'Stripe error: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        if not result['changes']:
            return response.Response(
                {'detail': 'No changes were made (already in requested state)'},
                status=status.HTTP_200_OK
            )
        
        return response.Response({
            'detail': 'User updated successfully',
            'changes': result['changes']
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """Suspend or reactivate user account"""
        user = self.get_object()
        serializer = UserStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        is_active = serializer.validated_data['is_active']
        reason = serializer.validated_data.get('reason', '')
        
        if user.is_active == is_active:
            return response.Response(
                {'detail': f'User is already {"active" if is_active else "suspended"}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            subscription = Subscription.objects.get(user=user)
            
            if not is_active:  # Suspending user
                # Cancel Stripe subscription immediately
                if subscription.stripe_subscription_id:
                    stripe.Subscription.cancel(subscription.stripe_subscription_id)
                
                # Update local subscription
                subscription.status = 'canceled'
                subscription.stripe_subscription_id = None
                subscription.save()
                
                # Deactivate user
                user.is_active = False
                user.save()
                
                # Log activity
                ActivityLog.objects.create(
                    user=user,
                    action='user_suspended',
                    description=f'User suspended by admin {request.user.email}. Reason: {reason or "No reason provided"}'
                )
                
                return response.Response({
                    'detail': 'User suspended successfully. Stripe subscription canceled.',
                    'reason': reason
                }, status=status.HTTP_200_OK)
            
            else:  # Reactivating user
                user.is_active = True
                user.save()
                
                # Log activity
                ActivityLog.objects.create(
                    user=user,
                    action='user_reactivated',
                    description=f'User reactivated by admin {request.user.email}'
                )
                
                return response.Response({
                    'detail': 'User reactivated successfully. User can now create new subscription.'
                }, status=status.HTTP_200_OK)
        
        except Subscription.DoesNotExist:
            # If no subscription exists, just update user status
            user.is_active = is_active
            user.save()
            
            action_type = 'user_reactivated' if is_active else 'user_suspended'
            ActivityLog.objects.create(
                user=user,
                action=action_type,
                description=f'User {"reactivated" if is_active else "suspended"} by admin {request.user.email}'
            )
            
            return response.Response({
                'detail': f'User {"reactivated" if is_active else "suspended"} successfully'
            }, status=status.HTTP_200_OK)
        
        except stripe.error.StripeError as e:
            return response.Response(
                {'detail': f'Stripe error: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )



# ==================== ADMIN PROFILE APIs ====================

class AdminProfileView(views.APIView):
    """Get and update admin profile information"""
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        serializer = AdminProfileSerializer(request.user)
        return response.Response(serializer.data, status=status.HTTP_200_OK)
    
    def patch(self, request):
        user = request.user
        serializer = AdminProfileSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return response.Response({
            'detail': 'Profile updated successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)


class AdminPasswordChangeView(views.APIView):
    """Change admin password"""
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        serializer = AdminPasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        new_password = serializer.validated_data['new_password']
        
        user.set_password(new_password)
        user.save()
        
        return response.Response({
            'detail': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


# ==================== LEGAL DOCUMENTS APIs ====================

class LegalDocumentView(views.APIView):
    """
    Manage Terms & Conditions and Privacy Policy
    Admin can POST/PUT, Anyone can GET
    """
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    
    def get(self, request):
        """Get all legal documents"""
        documents = LegalDocument.objects.all()
        serializer = LegalDocumentSerializer(documents, many=True)
        return response.Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create or update a legal document"""
        document_type = request.data.get('document_type')
        
        if not document_type:
            return response.Response(
                {'detail': 'document_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if document already exists
        try:
            document = LegalDocument.objects.get(document_type=document_type)
            # Update existing
            serializer = LegalDocumentSerializer(document, data=request.data, partial=True)
        except LegalDocument.DoesNotExist:
            # Create new
            serializer = LegalDocumentSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        
        return response.Response({
            'detail': f'{document_type.capitalize()} document saved successfully',
            'document': serializer.data
        }, status=status.HTTP_200_OK)


class TermsAndConditionsView(views.APIView):
    """Specific endpoint for Terms & Conditions"""
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    
    def get(self, request):
        try:
            document = LegalDocument.objects.get(document_type='terms')
            serializer = LegalDocumentSerializer(document)
            return response.Response(serializer.data, status=status.HTTP_200_OK)
        except LegalDocument.DoesNotExist:
            return response.Response(
                {'detail': 'Terms and Conditions not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
        try:
            document = LegalDocument.objects.get(document_type='terms')
            serializer = LegalDocumentSerializer(document, data=request.data, partial=True)
        except LegalDocument.DoesNotExist:
            serializer = LegalDocumentSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save(document_type='terms', created_by=request.user)
        
        return response.Response({
            'detail': 'Terms and Conditions saved successfully',
            'document': serializer.data
        }, status=status.HTTP_200_OK)


class PrivacyPolicyView(views.APIView):
    """Specific endpoint for Privacy Policy"""
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    
    def get(self, request):
        try:
            document = LegalDocument.objects.get(document_type='privacy')
            serializer = LegalDocumentSerializer(document)
            return response.Response(serializer.data, status=status.HTTP_200_OK)
        except LegalDocument.DoesNotExist:
            return response.Response(
                {'detail': 'Privacy Policy not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
        try:
            document = LegalDocument.objects.get(document_type='privacy')
            serializer = LegalDocumentSerializer(document, data=request.data, partial=True)
        except LegalDocument.DoesNotExist:
            serializer = LegalDocumentSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save(document_type='privacy', created_by=request.user)
        
        return response.Response({
            'detail': 'Privacy Policy saved successfully',
            'document': serializer.data
        }, status=status.HTTP_200_OK)


# === KEEP EXISTING VIEWS (for backward compatibility) ===

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
