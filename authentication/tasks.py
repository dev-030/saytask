from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from celery.exceptions import Ignore
from django_otp.plugins.otp_email.models import EmailDevice
from django.conf import settings



User = get_user_model()



@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_verification_email(self, token, email):
    try:
        send_mail(
            subject="Your Taskly Verification Code",
            message=f"Your verification code is: {token}\n\nIt expires in 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,  
            recipient_list=[email],
            fail_silently=False 
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
    
