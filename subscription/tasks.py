from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal

    




@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_subscription_confirmation_email(self, user_email, plan_name, amount, billing_interval):
    """Send email when user subscribes to a plan"""
    try:
        subject = f"Welcome to {plan_name.title()} Plan!"
        
        interval_text = "month" if billing_interval == "month" else "year"
        
        message = f"""Hi there,

        Thank you for subscribing to the {plan_name.title()} plan!

        Your subscription details:
        - Plan: {plan_name.title()}
        - Amount: ${amount}
        - Billing: {interval_text}ly

        Your subscription is now active and you have access to all {plan_name} features.

        If you have any questions, please don't hesitate to reach out.

        Best regards,
        The Taskly Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)



@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_payment_receipt_email(self, user_email, plan_name, amount, billing_interval, invoice_url=None):
    """Send email when user is charged (monthly renewal)"""
    try:
        subject = "Payment Receipt - Taskly Subscription"
        
        interval_text = "month" if billing_interval == "month" else "year"
        
        invoice_text = f"\n\nView Invoice: {invoice_url}" if invoice_url else ""
        
        message = f"""Hi there,

Your payment has been processed successfully!

Payment Details:
- Plan: {plan_name.title()}
- Amount: ${amount}
- Billing Period: {interval_text}ly
{invoice_text}

Thank you for continuing to use Taskly!

Best regards,
The Taskly Team
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_upgrade_email(self, user_email, old_plan_name, new_plan_name, old_price, new_price, charge_amount, proration_amount, invoice_url=None):
    """Send email when user upgrades to a higher plan"""
    try:
        subject = f"Upgrade Confirmed - Welcome to {new_plan_name.title()}!"
        
        invoice_text = f"\n\nView Invoice: {invoice_url}" if invoice_url else ""
        
        message = f"""Hi there,

Congratulations! You've successfully upgraded to the {new_plan_name.title()} plan!

Upgrade Details:
- Previous Plan: {old_plan_name.title()} (${old_price}/month)
- New Plan: {new_plan_name.title()} (${new_price}/month)
- Prorated Charge: ${charge_amount}

This charge covers the remaining time in your current billing cycle at the new plan rate.
{invoice_text}

You now have access to all {new_plan_name.title()} features! Enjoy!

Best regards,
The Taskly Team
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_downgrade_email(self, user_email, old_plan_name, new_plan_name, old_price, new_price, credit_amount, invoice_url=None):
    """Send email when user downgrades to a lower plan"""
    try:
        subject = f"Downgrade Confirmed - Now on {new_plan_name.title()} Plan"
        
        invoice_text = f"\n\nView Invoice: {invoice_url}" if invoice_url else ""
        
        message = f"""Hi there,

Your subscription has been downgraded to the {new_plan_name.title()} plan.

Downgrade Details:
- Previous Plan: {old_plan_name.title()} (${old_price}/month)
- New Plan: {new_plan_name.title()} (${new_price}/month)
- Credit Applied: ${credit_amount}

Good news! The unused time from your {old_plan_name.title()} plan has been converted to account credit.
This ${credit_amount} credit will automatically apply to your next invoice.

Next billing: ${new_price} - ${credit_amount} credit = ${max(0, new_price - credit_amount)} charged
{invoice_text}

You can upgrade back to {old_plan_name.title()} anytime!

Best regards,
The Taskly Team
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)

def send_price_change_notification_email(self, user_email, plan_name, old_price, new_price, billing_interval, renewal_date):
    """Send email when admin changes plan price"""
    try:
        from dateutil import parser
        
        price_change = "increase" if new_price > old_price else "decrease"
        interval_text = "monthly" if billing_interval == "month" else "annual"
        
        # Parse renewal_date string to datetime object
        if isinstance(renewal_date, str):
            renewal_date_obj = parser.parse(renewal_date)
        else:
            renewal_date_obj = renewal_date
        
        subject = f"Important: {plan_name.title()} Plan Price Update"
        
        message = f"""Hi there,

We're writing to inform you about an upcoming change to the {plan_name.title()} plan pricing.

Price Update:
- Current Price: ${old_price}
- New Price: ${new_price}
- Billing: {interval_text}

This change will take effect on your next billing date: {renewal_date_obj.strftime('%B %d, %Y')}

You can cancel your subscription at any time without penalty if you prefer not to continue at the new price.

We appreciate your understanding and continued support.

Best regards,
The Taskly Team
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)



@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_cancellation_confirmation_email(self, user_email, plan_name, end_date):
    """Send email when user cancels subscription"""
    try:
        subject = "Subscription Cancellation Confirmed"
        
        # Handle end_date which could be None, string, or datetime
        if end_date:
            if isinstance(end_date, str):
                from dateutil import parser
                end_date_obj = parser.parse(end_date)
            else:
                end_date_obj = end_date
            end_text = f"Your subscription will remain active until {end_date_obj.strftime('%B %d, %Y')}."
        else:
            end_text = "Your subscription has been cancelled."
        
        message = f"""Hi there,

We're sorry to see you go. Your {plan_name.title()} subscription has been cancelled.

{end_text}

After that date, you'll be downgraded to the Free plan and lose access to {plan_name} features.

You can resubscribe at any time if you change your mind.

Best regards,
The Taskly Team
"""
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)



@shared_task
def send_bulk_price_change_notifications(scheduled_changes_data):
    """
    Send price change emails in bulk (production-ready way)
    Uses Celery group to send emails in parallel batches
    
    Args:
        scheduled_changes_data: List of dicts with email data
    """
    from celery import group
    
    # Create a group of email tasks to run in parallel
    job = group([
        send_price_change_notification_email.s(
            user_email=data['user_email'],
            plan_name=data['plan_name'],
            old_price=str(data['old_price']),
            new_price=str(data['new_price']),
            billing_interval=data['billing_interval'],
            renewal_date=data['renewal_date']
        )
        for data in scheduled_changes_data
    ])
    
    # Execute all email tasks in parallel
    job.apply_async()


@shared_task
def reset_weekly_usage():
    """
    Reset weekly usage counters for all users.
    Runs every Monday at midnight via Celery Beat.
    """
    from .models import WeeklyUsage
    from django.utils import timezone
    
    count = WeeklyUsage.objects.count()
    
    # Reset all usage records
    WeeklyUsage.objects.all().update(
        events_created=0,
        notes_created=0,
        week_start_date=timezone.now().date()
    )
    
    print(f"✅ Reset weekly usage for {count} users")


@shared_task
def check_and_send_reminders():
    """
    Check for reminders that need to be sent and dispatch them.
    Runs every minute via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta, datetime
    from chatbot.models import Task, Event
    from chatbot.services.fcm_service import FCMService
    from chatbot.services.agora_service import AgoraService
    from authentication.models import UserProfile
    import logging
    
    logger = logging.getLogger(__name__)
    now = timezone.now()
    logger.info(f"Checking reminders at {now}")
    
    reminders_sent = 0
    
    # Check Tasks
    tasks_with_reminders = Task.objects.filter(
        reminder_enabled=True,
        reminder_sent=False,
        deadline__isnull=False,
        completed=False
    )
    
    for task in tasks_with_reminders:
        # Calculate when to send reminder
        reminder_time = task.deadline - timedelta(minutes=task.reminder_time_before or 0)
        
        # Check if it's time to send (within current minute)
        if now >= reminder_time and now < reminder_time + timedelta(minutes=1):
            _send_reminder(task.user, task, 'task')
            task.reminder_sent = True
            task.reminder_sent_at = now
            task.save()
            reminders_sent += 1
    
    # Check Events
    events_with_reminders = Event.objects.filter(
        reminder_enabled=True,
        reminder_sent=False,
        date__isnull=False
    )
    
    for event in events_with_reminders:
        # Combine date and time to get event datetime
        if event.time:
            event_datetime = timezone.make_aware(
                datetime.combine(event.date, event.time)
            )
        else:
            # If no time specified, use start of day
            event_datetime = timezone.make_aware(
                datetime.combine(event.date, datetime.min.time())
            )
        
        # Calculate when to send reminder
        reminder_time = event_datetime - timedelta(minutes=event.reminder_time_before or 0)
        
        # Check if it's time to send (within current minute)
        if now >= reminder_time and now < reminder_time + timedelta(minutes=1):
            _send_reminder(event.user, event, 'event')
            event.reminder_sent = True
            event.reminder_sent_at = now
            event.save()
            reminders_sent += 1
    
    logger.info(f"Sent {reminders_sent} reminders")
    return f"Checked reminders at {now}, sent {reminders_sent}"


def _send_reminder(user, item, item_type):
    """
    Send reminder based on type (notification/call/both)
    
    Args:
        user: User instance
        item: Task or Event instance
        item_type: 'task' or 'event'
    """
    import logging
    from authentication.models import UserProfile
    from chatbot.services.fcm_service import FCMService
    from chatbot.services.agora_service import AgoraService
    
    logger = logging.getLogger(__name__)
    
    # Get user profile for FCM token
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        logger.warning(f"User {user.email} has no profile, cannot send reminder")
        return
    
    # Prepare message
    if item_type == 'task':
        title = "⏰ Task Reminder"
        body = f"Reminder: {item.description}"
        if item.deadline:
            body += f" (Due: {item.deadline.strftime('%I:%M %p')})"
    else:  # event
        title = "📅 Event Reminder"
        body = f"Reminder: {item.title}"
        if item.date:
            body += f" ({item.date.strftime('%b %d')})"
            if item.time:
                body += f" at {item.time.strftime('%I:%M %p')}"
    
    # Send notification
    if item.reminder_type in ['notification', 'both']:
        if profile.fcm_token and profile.notifications_enabled:
            result = FCMService.send_notification(
                profile.fcm_token,
                title,
                body,
                data={
                    'type': item_type,
                    'id': str(item.id),
                    'reminder': 'true'
                }
            )
            logger.info(f"FCM notification sent to {user.email}: {result}")
        else:
            logger.warning(f"No FCM token for {user.email}, skipping notification")
    
    # Make call
    if item.reminder_type in ['call', 'both']:
        if user.phone_number:
            result = AgoraService.initiate_call(user.phone_number, body)
            logger.info(f"Agora call initiated for {user.email}: {result}")
        else:
            logger.warning(f"No phone number for {user.email}, skipping call")

    return f"Reset {count} users"
