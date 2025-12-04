from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserAccount, UserProfile


@receiver(post_save, sender=UserAccount)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a UserProfile when a new UserAccount is created.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=UserAccount)
def save_user_profile(sender, instance, **kwargs):
    """
    Automatically save the UserProfile when the UserAccount is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
