"""
Admin forms for subscription plan management with flexible limit configuration.
"""

from django import forms
from django.contrib import admin
from .models import SubscriptionPlan


class SubscriptionPlanAdminForm(forms.ModelForm):
    """
    Custom admin form for SubscriptionPlan with individual fields for limit configuration.
    
    This form extracts limits from the features JSONField and presents them as
    separate form fields for easy admin configuration.
    """
    
    # Event limits
    events_limit = forms.IntegerField(
        required=False,
        label="Events Limit",
        help_text="Leave blank for unlimited"
    )
    events_period = forms.ChoiceField(
        choices=[
            ('minute', 'Per Minute'),
            ('hour', 'Per Hour'),
            ('day', 'Per Day'),
            ('week', 'Per Week'),
            ('month', 'Per Month'),
        ],
        initial='week',
        label="Events Period"
    )
    
    # Task limits
    tasks_limit = forms.IntegerField(
        required=False,
        label="Tasks Limit",
        help_text="Leave blank for unlimited"
    )
    tasks_period = forms.ChoiceField(
        choices=[
            ('minute', 'Per Minute'),
            ('hour', 'Per Hour'),
            ('day', 'Per Day'),
            ('week', 'Per Week'),
            ('month', 'Per Month'),
        ],
        initial='week',
        label="Tasks Period"
    )
    
    # Note limits
    notes_limit = forms.IntegerField(
        required=False,
        label="Notes Limit",
        help_text="Leave blank for unlimited"
    )
    notes_period = forms.ChoiceField(
        choices=[
            ('minute', 'Per Minute'),
            ('hour', 'Per Hour'),
            ('day', 'Per Day'),
            ('week', 'Per Week'),
            ('month', 'Per Month'),
        ],
        initial='week',
        label="Notes Period"
    )
    
    # Edit limits
    edits_limit = forms.IntegerField(
        required=False,
        label="Edits Limit",
        help_text="Leave blank for unlimited"
    )
    edits_period = forms.ChoiceField(
        choices=[
            ('minute', 'Per Minute'),
            ('hour', 'Per Hour'),
            ('day', 'Per Day'),
            ('week', 'Per Week'),
            ('month', 'Per Month'),
        ],
        initial='month',
        label="Edits Period"
    )
    
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate from features JSONField if instance exists
        if self.instance and self.instance.pk and self.instance.features:
            features = self.instance.features
            
            # Events
            if 'event' in features:
                self.fields['events_limit'].initial = features['event'].get('limit')
                self.fields['events_period'].initial = features['event'].get('period', 'week')
            
            # Tasks
            if 'task' in features:
                self.fields['tasks_limit'].initial = features['task'].get('limit')
                self.fields['tasks_period'].initial = features['task'].get('period', 'week')
            
            # Notes
            if 'note' in features:
                self.fields['notes_limit'].initial = features['note'].get('limit')
                self.fields['notes_period'].initial = features['note'].get('period', 'week')
            
            # Edits
            if 'edit' in features:
                self.fields['edits_limit'].initial = features['edit'].get('limit')
                self.fields['edits_period'].initial = features['edit'].get('period', 'month')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Build features JSONField from form fields
        instance.features = {
            'event': {
                'limit': self.cleaned_data.get('events_limit'),
                'period': self.cleaned_data.get('events_period')
            },
            'task': {
                'limit': self.cleaned_data.get('tasks_limit'),
                'period': self.cleaned_data.get('tasks_period')
            },
            'note': {
                'limit': self.cleaned_data.get('notes_limit'),
                'period': self.cleaned_data.get('notes_period')
            },
            'edit': {
                'limit': self.cleaned_data.get('edits_limit'),
                'period': self.cleaned_data.get('edits_period')
            },
        }
        
        if commit:
            instance.save()
        return instance
