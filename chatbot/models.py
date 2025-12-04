from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    
    response_type = models.CharField(
        max_length=20,
        choices=[
            ('response', 'General Response'),
            ('event', 'Event'),
            ('task', 'Task'),
            ('note', 'Note')
        ],
        default='response',
        null=True,
        blank=True
    )
    metadata = models.JSONField(null=True, blank=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.role}: {self.content[:50]}"

