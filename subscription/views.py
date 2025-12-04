from rest_framework import views, response, permissions, viewsets, status
from .models import SubscriptionPlan, AnnualDiscount, Subscription, PaymentHistory
from .serializers import AnnualDiscountSerializer, SubscriptionPlanSerializer, CreateCheckoutSessionSerializer, PaymentHistorySerializer
from .tasks import send_subscription_confirmation_email, send_payment_receipt_email, send_cancellation_confirmation_email, send_upgrade_email, send_downgrade_email
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from django.utils import timezone
from decimal import Decimal
import stripe
from django.db.models import Q





stripe.api_key = settings.STRIPE_SECRET_KEY






class CustomerPortalViewSet(viewsets.ViewSet):

    def create(self, request):

        user = request.user
        subscription = getattr(user, 'subscriptions', None)

        print(subscription.stripe_customer_id)

        if not subscription or not subscription.stripe_customer_id:
            return response.Response(
                {"detail": "No billing account found."}, 
                status=400
            )

        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=settings.FRONTEND_URL + "/dashboard"
            )

            return response.Response({"portal_url": portal_session.url})

        except Exception as e:
            return response.Response(
                {"detail": "An error occurred generating the portal link."},
                status=400
            )
        



class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer

    def get_queryset(self):
        if not self.request.user.is_staff:
            return SubscriptionPlan.objects.filter(is_active=True)
        return SubscriptionPlan.objects.all()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if hasattr(instance, 'subscriptions') and instance.subscriptions.exists():
            return response.Response(
                {'error': 'Cannot delete plan with active subscriptions'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)



class AnnualDiscountViewSet(viewsets.ModelViewSet):
    queryset = AnnualDiscount.objects.all()
    serializer_class = AnnualDiscountSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request, *args, **kwargs):
        instance = AnnualDiscount.objects.first()
        if not instance:
            return response.Response({"detail": "No annual discount exists."}, status=404)

        serializer = self.get_serializer(instance)
        return response.Response(serializer.data)

    def create(self, request, *args, **kwargs):
        if AnnualDiscount.objects.exists():
            return response.Response(
                {"detail": "Annual discount already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        return response.Response(
            {"detail": "Deletion not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    


class PaymentMethodViewSet(viewsets.ViewSet):

    def list(self, request):
        """List all saved cards for the logged-in user"""
        subscription = getattr(request.user, 'subscriptions', None)
        if not subscription or not subscription.stripe_customer_id:
            return response.Response({"detail": "No saved payment methods"}, status=404)

        payment_methods = stripe.PaymentMethod.list(
            customer=subscription.stripe_customer_id,
            type="card"
        )

        default_pm = subscription.stripe_customer_id and stripe.Customer.retrieve(
            subscription.stripe_customer_id
        ).invoice_settings.default_payment_method

        cards = [
            {
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "is_default": pm.id == default_pm
            }
            for pm in payment_methods.data
        ]
        return response.Response(cards)

    def destroy(self, request, pk=None):
        subscription = getattr(request.user, 'subscriptions', None)
        if not subscription or not subscription.stripe_customer_id:
            return response.Response({"detail": "No subscription found"}, status=404)

        try:
            stripe.PaymentMethod.detach(pk)
        except stripe.error.InvalidRequestError:
            return response.Response({"detail": "Card not found or cannot be removed"}, status=400)

        return response.Response({"detail": "Card removed successfully"}, status=200)
    




class CancelSubscriptionViewSet(viewsets.ViewSet):

    def create(self, request):
        user = request.user
        
        try:
            subscription = Subscription.objects.get(user=user)
        except Subscription.DoesNotExist:
            return response.Response(
                {"detail": "No active subscription found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if subscription.plan.name == 'free':
            return response.Response(
                {"detail": "You are already on the free plan"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not subscription.stripe_subscription_id:
            return response.Response(
                {"detail": "No active subscription to cancel"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            subscription.cancel_at_period_end = True
            subscription.save()
            
            send_cancellation_confirmation_email.delay(
                user_email=user.email,
                plan_name=subscription.plan.name,
                end_date=subscription.current_period_end
            )
            
            return response.Response({
                "detail": "Subscription cancelled successfully",
                "message": f"Your subscription will remain active until {subscription.current_period_end.strftime('%B %d, %Y')}",
                "end_date": subscription.current_period_end
            })
            
        except stripe.error.StripeError as e:
            return response.Response(
                {"detail": f"Stripe error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )



class PaymentHistoryViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PaymentHistorySerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PaymentHistory.objects.all()
        return PaymentHistory.objects.filter(user=user)





class CheckoutSessionViewSet(viewsets.GenericViewSet):
    serializer_class = CreateCheckoutSessionSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        plan= serializer.validated_data['plan_id']
        billing_interval = serializer.validated_data['billing_interval']

        subscription, _ = Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": SubscriptionPlan.objects.get(name="free"),
                "billing_interval": "month",
                "status": "active"
            }
        )

        if subscription.plan == plan and subscription.billing_interval == billing_interval:
            return response.Response(
                {"detail": "You are already subscribed to this plan."},
                status=400
            )

        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            subscription.stripe_customer_id = customer.id
            subscription.save()


        price_id = plan.stripe_monthly_price_id if billing_interval == 'month' else plan.stripe_annual_price_id

        if not price_id:
            return response.Response(
                {
                    "detail": f"Plan '{plan.name}' is missing Stripe price ID for {billing_interval} billing.",
                    "error": "missing_stripe_price_id"
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        if subscription.stripe_subscription_id:
            try:

                stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                
                updated_stripe_sub = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                    items=[{
                        'id': stripe_sub['items']['data'][0].id, 
                        'price': price_id                      
                    }],
                    proration_behavior='always_invoice',
                    billing_cycle_anchor='unchanged',
                    expand=['latest_invoice'] 
                )

                invoice = updated_stripe_sub.latest_invoice
                amount_paid = invoice.amount_paid / 100
                total_value = invoice.total / 100
                
                if total_value < 0:
                    msg = "Downgrade successful. Credit applied to account."
                    action = "downgrade"
                elif amount_paid > 0:
                    msg = f"Upgrade successful. Charged ${amount_paid}."
                    action = "upgrade"
                else:
                    msg = "Plan updated successfully."
                    action = "update"

                return response.Response({
                    "detail": msg,
                    "action": action,
                    "amount_paid": amount_paid,
                    "credit_amount": abs(total_value) if total_value < 0 else 0
                })
            
                # return response.Response({
                #     "detail": "Subscription updated successfully."
                # })

            except stripe.error.CardError as e:
                return response.Response(
                    {
                        "detail": f"Payment declined: {e.user_message}",
                        "code": "card_declined"
                    }, 
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )            

        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=settings.FRONTEND_URL + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.FRONTEND_URL + "/cancel",
            client_reference_id=user.id
        )

        return response.Response({"checkout_url": checkout_session.url})



@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)

    except Exception as e:
        print(f"Webhook signature verification failed: {e}")
        return HttpResponse(status=400)

    event_type = event['type']
    data_object = event['data']['object']

    print("webhook 🎣", event['type'])

    handlers = {
        'checkout.session.completed': handle_checkout_completed,
        'customer.subscription.updated': handle_subscription_updated,
        'customer.subscription.deleted': handle_subscription_deleted,
        'invoice.paid': handle_invoice_paid,
        'invoice.payment_failed': handle_payment_failed,
        'charge.refunded': handle_refund,
    }

    handler = handlers.get(event_type)
    if handler:
        try:
            handler(data_object)
        except Exception as e:
            print(f"Error handling {event_type}: {e}")
            return HttpResponse(status=500)

    return HttpResponse(status=200)





def handle_checkout_completed(session):
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    if not subscription_id:
        print("❌ No subscription ID found in session.")
        return
    try:
        subscription = Subscription.objects.get(stripe_customer_id=customer_id)
        stripe_sub = stripe.Subscription.retrieve(subscription_id)

        sub_item = stripe_sub['items']['data'][0]
        price_id = sub_item['price']['id']
        billing_interval = sub_item['price']['recurring']['interval']

        plan = _get_plan_from_price_id(price_id, billing_interval)
        if not plan:
            print(f"No plan found for price_id: {price_id}")
            return
        
        subscription.plan = plan
        subscription.billing_interval = billing_interval
        subscription.stripe_subscription_id = subscription_id
        subscription.status = stripe_sub['status']
        subscription.current_period_start = timezone.datetime.fromtimestamp(
            sub_item['current_period_start'], 
            tz=timezone.get_current_timezone()
        )
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            sub_item['current_period_end'], 
            tz=timezone.get_current_timezone()
        )
        subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
        subscription.save()

        print(f"✅ Subscription Activated: {subscription.user.email} -> {plan.name}")
        
        send_subscription_confirmation_email.delay(
            user_email=subscription.user.email,
            plan_name=plan.name,
            amount=str(subscription.current_price),
            billing_interval=billing_interval
        )
        
    except Subscription.DoesNotExist:
        print(f"Subscription not found for customer: {customer_id}")
    except Exception as e:
        print(f"Error in checkout completed: {e}")
        import traceback
        traceback.print_exc()




def handle_invoice_paid(invoice):
    customer_id = invoice['customer']
    print("inside invoice paid 🔴")
    try:
        subscription = Subscription.objects.get(stripe_customer_id=customer_id)

        lines = invoice["lines"]["data"]
        positive_lines = [l for l in lines if l["amount"] > 0]
        if positive_lines:
            line = positive_lines[0]
        else:
            line = lines[0]

        price_id = line["pricing"]["price_details"]["price"]
        price = stripe.Price.retrieve(price_id)
        interval = price["recurring"]["interval"]

        if interval == "month":
            plan = SubscriptionPlan.objects.get(stripe_monthly_price_id=price_id)
        else:
            plan = SubscriptionPlan.objects.filter(
                Q(stripe_monthly_price_id=plan_price_id) |
                Q(stripe_annual_price_id=plan_price_id)
            ).first()

            if plan:
                interval = "month" if plan.stripe_monthly_price_id == plan_price_id else "year"
            else:
                print(f"❌ Plan not found locally for price: {plan_price_id}")
                return

        billing_reason = invoice.get('billing_reason')
        transaction_type = 'renewal'

        if billing_reason == 'subscription_create':
            transaction_type = 'initial'
        elif billing_reason == 'subscription_cycle':
            transaction_type = 'renewal'
        elif billing_reason == 'subscription_update':
            if proration_sum_cents > 0:
                transaction_type = 'upgrade'
            elif proration_sum_cents < 0:
                transaction_type = 'downgrade'
            else:
                transaction_type = 'interval_change'

        if PaymentHistory.objects.filter(stripe_invoice_id=invoice['id']).exists():
            print(f"⚠️ Payment already recorded: {invoice['id']}")
            return

        PaymentHistory.objects.create(
            user=subscription.user,
            transaction_type=transaction_type,
            payment_status='succeeded',
            plan=plan,
            billing_interval=interval,
            amount=invoice['amount_paid'] / 100,
            stripe_invoice_id=invoice['id'],
            proration_amount=line.get("amount", 0)/100,
            notes=f"Reason: {billing_reason}"
        )

        if invoice['amount_paid'] > 0:
            send_payment_receipt_email.delay(
                user_email=subscription.user.email,
                plan_name=plan.name,
                amount=invoice['amount_paid'] / 100,
                billing_interval=interval,
                invoice_url=invoice.get("hosted_invoice_url"),
            )

        print(f"✅ Payment recorded: ${invoice['amount_paid'] / 100}")

    except Exception as e:
        print(f"Error in invoice paid: {e}")





def handle_subscription_updated(stripe_sub):
    subscription_id = stripe_sub['id']
    print("inside subscription updated 🔴")
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)

        sub_item = stripe_sub['items']['data'][0]
        price_id = sub_item['price']['id']
        billing_interval = sub_item['price']['recurring']['interval']

        new_plan = SubscriptionPlan.objects.filter(
            Q(stripe_monthly_price_id=price_id) | 
            Q(stripe_annual_price_id=price_id)
        ).first()

        if not new_plan:
            print(f"❌ Plan not found locally for price_id: {price_id}")
            return
        
        old_plan = subscription.plan
        old_interval = subscription.billing_interval
        old_cancel_at_period_end = subscription.cancel_at_period_end
        old_status = subscription.status

        subscription.plan = new_plan
        subscription.billing_interval = billing_interval
        subscription.status = stripe_sub['status']
        subscription.cancel_at_period_end = stripe_sub['cancel_at_period_end']
        
        if sub_item.get('current_period_start'):
            subscription.current_period_start = timezone.datetime.fromtimestamp(
                sub_item['current_period_start'], tz=timezone.get_current_timezone()
            )
        if sub_item.get('current_period_end'):
            subscription.current_period_end = timezone.datetime.fromtimestamp(
                sub_item['current_period_end'], tz=timezone.get_current_timezone()
            )
        
        subscription.save()
        print(f"✅ Database updated for {subscription.user.email}")
        

        # A. Plan or Interval Change (Upgrade/Downgrade)
        # We check if the Plan ID changed OR if the Interval changed
        if old_plan.id != new_plan.id or old_interval != billing_interval:
            
            # 1. Determine Prices to compare
            old_price = old_plan.monthly_price if old_interval == 'month' else old_plan.annual_price
            new_price = new_plan.monthly_price if billing_interval == 'month' else new_plan.annual_price
            
            # 2. Compare Prices explicitly (No helper function needed)
            if new_price > old_price:
                print(f"🚀 UPGRADE DETECTED: {old_plan.name} -> {new_plan.name}")
                # send_upgrade_email.delay(
                #     user_email=subscription.user.email,
                #     old_plan_name=old_plan.name,
                #     new_plan_name=new_plan.name
                # )
            elif new_price < old_price:
                print(f"📉 DOWNGRADE DETECTED: {old_plan.name} -> {new_plan.name}")
                # send_downgrade_email.delay(
                #     user_email=subscription.user.email,
                #     old_plan_name=old_plan.name,
                #     new_plan_name=new_plan.name
                # )
            else:
                print(f"🔄 INTERVAL CHANGE: {old_interval} -> {billing_interval}")

        # B. Cancellation Scheduled
        # User clicked "Cancel" in portal (flag flipped from False to True)
        print(old_cancel_at_period_end, "🔴")
        if not old_cancel_at_period_end and subscription.cancel_at_period_end:
            print(f"😢 Cancellation Scheduled for {subscription.current_period_end}")

        # C. Reactivation (Undo Cancel)
        # User clicked "Resume" in portal (flag flipped from True to False)
        if old_cancel_at_period_end and not subscription.cancel_at_period_end:
            print(f"🎉 Subscription Reactivated!")
            # send_reactivation_email.delay(...)

        # D. Status Change (Payment Failure / Expiration)
        if old_status != subscription.status:
            print(f"⚠️ Status changed: {old_status} -> {subscription.status}")
            print(f"⚠️ Status changed: {old_status} -> {subscription.status}")
            
            if subscription.status == 'past_due':
                print("❌ Payment Failed - Subscription is Past Due")
            elif subscription.status == 'active' and old_status in ['past_due', 'incomplete']:
                print("✅ Subscription recovered to active")
        
    except Subscription.DoesNotExist:
        print(f"❌ Subscription not found: {subscription_id}")



def handle_subscription_deleted(stripe_sub):
    """
    Fired when subscription is PERMANENTLY deleted (after billing period ends).
    This is the final step - subscription has already ended.
    """
    subscription_id = stripe_sub['id']

    print("inside subscription deleted 🔴")

    
    try:
        subscription = Subscription.objects.get(stripe_subscription_id=subscription_id)
        free_plan = SubscriptionPlan.objects.get(name='free')
        
        print(f"✓ Subscription ended: {subscription.user.email} - {subscription.plan.name}")
        
        # Record cancellation in payment history
        PaymentHistory.objects.create(
            user=subscription.user,
            transaction_type='cancellation',
            payment_status='succeeded',
            plan=subscription.plan,
            billing_interval=subscription.billing_interval,
            amount=Decimal('0.00'),
            notes=f"Subscription cancelled - downgraded to free plan"
        )
        
        # Send final cancellation email
        send_cancellation_confirmation_email.delay(
            user_email=subscription.user.email,
            plan_name=subscription.plan.name,
            end_date=None  # Already ended
        )
        
        # Downgrade to free plan
        subscription.plan = free_plan
        subscription.status = 'canceled'
        subscription.billing_interval = 'month'
        subscription.stripe_subscription_id = None
        subscription.cancel_at_period_end = False
        subscription.current_period_start = None
        subscription.current_period_end = None
        subscription.save()
        
        print(f"   → Downgraded to free plan")
        
    except Subscription.DoesNotExist:
        print(f"❌ Subscription not found: {subscription_id}")
    except SubscriptionPlan.DoesNotExist:
        print(f"❌ Free plan not found in database")
    except Exception as e:
        print(f"❌ Error in subscription deleted: {e}")
        import traceback
        traceback.print_exc()


def handle_payment_failed(invoice):
    """
    Fired when payment fails (card declined, insufficient funds, etc.).
    Updates subscription status and records failed payment.
    """
    customer_id = invoice['customer']
    subscription_id = invoice.get('subscription')

    print("inside payment failed 🔴")

    
    try:
        subscription = Subscription.objects.get(stripe_customer_id=customer_id)
        
        # Update subscription status to past_due
        old_status = subscription.status
        subscription.status = 'past_due'
        subscription.save()
        
        print(f"⚠ Payment failed: {subscription.user.email} - attempt {invoice.get('attempt_count', 1)}")
        
        # Get plan details from invoice
        line_item = invoice['lines']['data'][0]
        price_id = line_item['price']['id']
        billing_interval = line_item['price']['recurring']['interval']
        plan = _get_plan_from_price_id(price_id, billing_interval)
        
        if not plan:
            plan = subscription.plan  # Fallback to current plan
        
        # Record failed payment in history
        PaymentHistory.objects.create(
            user=subscription.user,
            transaction_type='renewal',
            payment_status='failed',
            plan=plan,
            billing_interval=billing_interval,
            amount=Decimal(invoice['amount_due']) / 100,
            stripe_invoice_id=invoice['id'],
            stripe_payment_intent_id=invoice.get('payment_intent'),
            notes=f"Payment failed (attempt {invoice.get('attempt_count', 1)}): {invoice.get('last_finalization_error', {}).get('message', 'Card declined')}"
        )
        
        # Send payment failed email with retry instructions
        # send_payment_failed_email.delay(
        #     user_email=subscription.user.email,
        #     plan_name=plan.name,
        #     amount=float(Decimal(invoice['amount_due']) / 100),
        #     attempt_count=invoice.get('attempt_count', 1),
        #     hosted_invoice_url=invoice.get('hosted_invoice_url')
        # )
        
        print(f"   → Status: {old_status} → past_due")
        print(f"   → Failed payment recorded in history")
        
    except Subscription.DoesNotExist:
        print(f"❌ Subscription not found for customer: {customer_id}")
    except Exception as e:
        print(f"❌ Error in payment failed: {e}")
        import traceback
        traceback.print_exc()


def handle_refund(charge):
    """
    Fired when refund is issued.
    Records refund in PaymentHistory (negative amount).
    """
    customer_id = charge.get('customer')

    print("inside handle refund 🔴")

    
    if not customer_id:
        print(f"⚠ Refund event received without customer_id")
        return
    
    try:
        subscription = Subscription.objects.get(stripe_customer_id=customer_id)
        
        # Check if refund already recorded (idempotency)
        existing = PaymentHistory.objects.filter(
            stripe_charge_id=charge['id'],
            transaction_type='refund'
        ).exists()
        
        if existing:
            print(f"⚠ Refund already recorded for charge: {charge['id']}")
            return
        
        refund_amount = Decimal(charge['amount_refunded']) / 100
        
        # Record refund in payment history (negative amount)
        PaymentHistory.objects.create(
            user=subscription.user,
            transaction_type='refund',
            payment_status='refunded',
            plan=subscription.plan,
            billing_interval=subscription.billing_interval,
            amount=-refund_amount,  # Negative to indicate refund
            stripe_charge_id=charge['id'],
            notes=f"Refund: ${refund_amount} - Reason: {charge.get('refunds', {}).get('data', [{}])[0].get('reason', 'N/A')}"
        )
        
        print(f"✓ Refund recorded: {subscription.user.email} - ${refund_amount}")
        
        # Send refund confirmation email
        # send_refund_confirmation_email.delay(
        #     user_email=subscription.user.email,
        #     amount=float(refund_amount),
        #     reason=charge.get('refunds', {}).get('data', [{}])[0].get('reason', 'N/A')
        # )
        
    except Subscription.DoesNotExist:
        print(f"❌ Subscription not found for customer: {customer_id}")
    except Exception as e:
        print(f"❌ Error in refund handler: {e}")
        import traceback
        traceback.print_exc()


def _get_plan_from_price_id(price_id, billing_interval):
    """Find plan by Stripe price ID"""
    if billing_interval == 'month':
        return SubscriptionPlan.objects.filter(stripe_monthly_price_id=price_id).first()
    else:
        return SubscriptionPlan.objects.filter(stripe_annual_price_id=price_id).first()
