from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid
from django.contrib.postgres.fields import ArrayField




User = get_user_model()






class Note(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=255, blank=True, null=True)
    original = models.TextField()
    summarized = models.TextField(blank=True)
    points = models.JSONField(default=list, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title if self.title else self.original[:50]
    


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    location_address = models.TextField(null=True, blank=True)
    event_datetime = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event_datetime']
    
    def __str__(self):
        return self.title



class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    tags = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="List of tags associated with this task"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_time', 'end_time']

    def __str__(self):
        return self.title

    @property
    def scheduled_start(self):
        """Return start datetime or None if not set"""
        return self.start_time

    @property
    def scheduled_end(self):
        """Return end datetime or None if not set"""
        return self.end_time




class Reminder(models.Model):
    REMINDER_TYPE_CHOICES = [
        ('notification', 'Push Notification'),
        ('call', 'Phone Call'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')
    time_before = models.IntegerField(help_text="Minutes before the scheduled time")
    types = models.JSONField(default=list, blank=True, help_text="['notification','call']")
    scheduled_time = models.DateTimeField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_time']
        indexes = [
            models.Index(fields=['sent', 'scheduled_time']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"Reminder for {self.content_object} in {self.time_before} min"






