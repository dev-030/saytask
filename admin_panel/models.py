from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class LegalDocument(models.Model):
    """Store Terms & Conditions and Privacy Policy"""
    
    DOCUMENT_TYPE_CHOICES = [
        ('terms', 'Terms and Conditions'),
        ('privacy', 'Privacy Policy'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES, unique=True)
    content = models.TextField(help_text="Content of the legal document")
    version = models.CharField(max_length=20, default="1.0")
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_legal_docs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Legal Document'
        verbose_name_plural = 'Legal Documents'
    
    def __str__(self):
        return f"{self.get_document_type_display()} v{self.version}"


class ActivityLog(models.Model):
    """Track admin and user activities for audit trail"""
    
    ACTION_CHOICES = [
        ('user_registered', 'User Registered'),
        ('user_upgraded', 'User Upgraded Plan'),
        ('user_downgraded', 'User Downgraded Plan'),
        ('payment_processed', 'Payment Processed'),
        ('user_suspended', 'User Suspended'),
        ('user_reactivated', 'User Reactivated'),
        ('subscription_updated', 'Subscription Updated by Admin'),
        ('subscription_canceled', 'Subscription Canceled'),
        ('maintenance_completed', 'System Maintenance Completed'),
        ('usage_exceeded', 'Usage Limit Exceeded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='activity_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField()
    
    # Optional fields for payment-related activities
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
    
    def __str__(self):
        user_info = f"{self.user.email} - " if self.user else ""
        return f"{user_info}{self.get_action_display()}"
