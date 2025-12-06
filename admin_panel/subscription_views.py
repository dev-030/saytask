"""
Admin viewset for subscription plan management.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from subscription.models import SubscriptionPlan
from .subscription_serializers import AdminSubscriptionPlanSerializer, SubscriptionPlanBulkUpdateSerializer


class AdminSubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Admin-only viewset for comprehensive subscription plan management.
    
    Features:
    - Full CRUD operations on subscription plans
    - Manage pricing (monthly, annual, discounts)
    - Configure usage limits for events, tasks, notes, and edits
    - Automatic Stripe synchronization for price changes
    - Bulk update capabilities for usage limits
    
    Endpoints:
    - GET /admin/subscription-plans/ - List all plans
    - POST /admin/subscription-plans/ - Create new plan
    - GET /admin/subscription-plans/{id}/ - Get plan details
    - PUT/PATCH /admin/subscription-plans/{id}/ - Update plan
    - DELETE /admin/subscription-plans/{id}/ - Delete plan (if no active subscriptions)
    - POST /admin/subscription-plans/bulk-update-limits/ - Bulk update usage limits
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = AdminSubscriptionPlanSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        """Return all plans including inactive ones for admins"""
        return SubscriptionPlan.objects.all().order_by('monthly_price')
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of plans with active subscriptions"""
        instance = self.get_object()
        
        # Check if plan has active subscriptions
        if hasattr(instance, 'user_subscriptions') and instance.user_subscriptions.filter(
            status__in=['active', 'trialing']
        ).exists():
            return Response(
                {
                    'error': 'Cannot delete plan with active subscriptions',
                    'detail': 'Please migrate users to another plan before deleting this one.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prevent deletion of free plan
        if instance.name == 'free':
            return Response(
                {
                    'error': 'Cannot delete free plan',
                    'detail': 'The free plan is required for the system to function.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'], url_path='bulk-update-limits')
    def bulk_update_limits(self, request):
        """
        Bulk update usage limits for multiple plans at once.
        
        Request body:
        {
            "plan_ids": ["uuid1", "uuid2"],
            "event_limits": {"limit": 100, "period": "week"},
            "task_limits": {"limit": 50, "period": "week"}
        }
        """
        serializer = SubscriptionPlanBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_ids = serializer.validated_data['plan_ids']
        plans = SubscriptionPlan.objects.filter(id__in=plan_ids)
        
        if plans.count() != len(plan_ids):
            return Response(
                {'error': 'One or more plan IDs not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update each plan's features
        updated_count = 0
        for plan in plans:
            features = plan.features or {}
            
            if 'event_limits' in serializer.validated_data:
                features['event'] = serializer.validated_data['event_limits']
            if 'task_limits' in serializer.validated_data:
                features['task'] = serializer.validated_data['task_limits']
            if 'note_limits' in serializer.validated_data:
                features['note'] = serializer.validated_data['note_limits']
            if 'edit_limits' in serializer.validated_data:
                features['edit'] = serializer.validated_data['edit_limits']
            
            plan.features = features
            plan.save()
            updated_count += 1
        
        return Response({
            'detail': f'Successfully updated {updated_count} plans',
            'updated_plans': [str(plan.id) for plan in plans]
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='usage-stats')
    def usage_stats(self, request, pk=None):
        """
        Get usage statistics for a specific plan.
        
        Returns:
        - Number of active subscriptions
        - Number of users on this plan
        - Total revenue from this plan (monthly equivalent)
        """
        plan = self.get_object()
        
        from subscription.models import Subscription
        from decimal import Decimal
        
        active_subs = Subscription.objects.filter(
            plan=plan,
            status__in=['active', 'trialing']
        )
        
        user_count = active_subs.count()
        
        # Calculate monthly revenue
        monthly_revenue = Decimal('0.00')
        for sub in active_subs:
            if sub.billing_interval == 'month':
                monthly_revenue += plan.monthly_price
            else:  # annual
                monthly_revenue += plan.annual_price / 12
        
        return Response({
            'plan_name': plan.name,
            'active_subscriptions': user_count,
            'estimated_monthly_revenue': float(monthly_revenue),
            'monthly_price': float(plan.monthly_price),
            'annual_price': float(plan.annual_price),
            'is_active': plan.is_active
        })
