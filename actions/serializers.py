from rest_framework import serializers
from .models import Event, Task, Note, Reminder
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta





class ReminderSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Reminder
        fields = ['id', 'time_before', 'types', 'scheduled_time', 'sent']
        read_only_fields = ['id', 'scheduled_time', 'sent']



class NoteSerializer(serializers.ModelSerializer):

    summarized = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = ['id', 'title', 'original', 'summarized', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_summarized(self, obj):
        return {
            'summary': obj.summarized or '',
            'points': obj.points or []
        }
    
    def create(self, validated_data):
        user = self.context['request'].user
        summarized_data = self.initial_data.get('summarized', {})
        return Note.objects.create(
            user=user,
            title=validated_data.get('title', ''),
            original=validated_data['original'],
            summarized=summarized_data.get('summary', ''), 
            points=summarized_data.get('points', [])
        )
    
    def update(self, instance, validated_data):
        summarized_data = self.initial_data.get('summarized', {})
        instance.title = validated_data.get('title', instance.title)
        instance.original = validated_data.get('original', instance.original)
        instance.summarized = summarized_data.get('summary', instance.summarized) 
        instance.points = summarized_data.get('points', instance.points)
        instance.save()
        return instance



class EventSerializer(serializers.ModelSerializer):

    reminders = ReminderSerializer(many=True, required=False)

    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'location_address', 'event_datetime', 'created_at', 'reminders']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        event_ct = ContentType.objects.get_for_model(Event)
        reminders = Reminder.objects.filter(
            content_type=event_ct,
            object_id=instance.id
        )
        representation['reminders'] = ReminderSerializer(reminders, many=True).data
        
        return representation


    def create(self, validated_data):
        reminders_data = validated_data.pop('reminders', [])
        
        if 'user' not in validated_data:
            if 'request' in self.context:
                validated_data['user'] = self.context['request'].user
            else:
                raise ValueError("User must be provided either in validated_data or context")
        
        event = Event.objects.create(**validated_data)

        if event.event_datetime:
            event_ct = ContentType.objects.get_for_model(Event)
            for rem_data in reminders_data:
                scheduled_time = event.event_datetime - timedelta(minutes=rem_data['time_before'])
                Reminder.objects.create(
                    content_type=event_ct,
                    object_id=event.id,
                    scheduled_time=scheduled_time,
                    time_before=rem_data['time_before'],
                    types=rem_data.get('types', [])
                )
        
        return event
    

    def update(self, instance, validated_data):
        reminders_data = validated_data.pop('reminders', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if reminders_data is not None:
            event_ct = ContentType.objects.get_for_model(Event)
            Reminder.objects.filter(
                content_type=event_ct,
                object_id=instance.id
            ).delete()

            if instance.event_datetime:
                for rem_data in reminders_data:
                    scheduled_time = instance.event_datetime - timedelta(minutes=rem_data['time_before'])
                    Reminder.objects.create(
                        content_type=event_ct,
                        object_id=instance.id,
                        scheduled_time=scheduled_time,
                        time_before=rem_data['time_before'],
                        types=rem_data.get('types', [])
                    )
        
        return instance






class TaskSerializer(serializers.ModelSerializer):

    reminders = ReminderSerializer(many=True, required=False)

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'start_time', 'end_time', 'tags', 'completed', 'created_at', 'reminders']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        task_ct = ContentType.objects.get_for_model(Task)
        reminders = Reminder.objects.filter(
            content_type=task_ct,
            object_id=instance.id
        )
        representation['reminders'] = ReminderSerializer(reminders, many=True).data
        
        return representation


    def create(self, validated_data):
        reminders_data = validated_data.pop('reminders', [])
        
        if 'user' not in validated_data:
            if 'request' in self.context:
                validated_data['user'] = self.context['request'].user
            else:
                raise ValueError("User must be provided either in validated_data or context")
        
        task = Task.objects.create(**validated_data)

        if task.scheduled_start:
            task_ct = ContentType.objects.get_for_model(Task)
            for rem_data in reminders_data:
                scheduled_time = task.scheduled_start - timedelta(minutes=rem_data['time_before'])
                Reminder.objects.create(
                    content_type=task_ct,
                    object_id=task.id,
                    scheduled_time=scheduled_time,
                    time_before=rem_data['time_before'],
                    types=rem_data.get('types', [])
                )
        
        return task
    

    def update(self, instance, validated_data):
        reminders_data = validated_data.pop('reminders', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if reminders_data is not None:
            task_ct = ContentType.objects.get_for_model(Task)
            Reminder.objects.filter(
                content_type=task_ct,
                object_id=instance.id
            ).delete()

            if instance.scheduled_start:
                for rem_data in reminders_data:
                    scheduled_time = instance.scheduled_start - timedelta(minutes=rem_data['time_before'])
                    Reminder.objects.create(
                        content_type=task_ct,
                        object_id=instance.id,
                        scheduled_time=scheduled_time,
                        time_before=rem_data['time_before'],
                        types=rem_data.get('types', [])
                    )
        
        return instance