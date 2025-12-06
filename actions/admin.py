from django.contrib import admin
from actions.models import Note, Event, Task, Reminder


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'original', 'summarized', 'created_at')
    search_fields = ('original', 'summarized', 'user__email')
    list_filter = ('created_at', 'user')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'event_datetime', 'location_address', 'created_at')
    search_fields = ('title', 'description', 'location_address', 'user__email')
    list_filter = ('event_datetime', 'user')
    readonly_fields = ('id', 'created_at')
    ordering = ('-event_datetime',)



@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'start_time', 'end_time', 'completed', 'created_at')
    search_fields = ('title', 'description', 'tags', 'user__email')
    list_filter = ('completed', 'user')
    readonly_fields = ('id', 'created_at')
    ordering = ('-start_time',)


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_object_type',
        'get_object_title',
        'time_before',
        'types_display',
        'scheduled_time',
        'sent',
        'sent_at',
        'created_at'
    )
    list_filter = ('sent', 'types', 'scheduled_time')
    search_fields = () 
    readonly_fields = (
        'content_type', 'object_id', 'time_before', 'types', 'scheduled_time',
        'sent', 'sent_at', 'created_at'
    )
    ordering = ('-scheduled_time',)

    def has_add_permission(self, request):
        return False

    def get_user(self, obj):
        return obj.content_object.user
    get_user.short_description = 'User'
    get_user.admin_order_field = 'content_object__user'

    def get_object_type(self, obj):
        return obj.content_type.model
    get_object_type.short_description = 'Object Type'

    def get_object_title(self, obj):
        return str(obj.content_object)
    get_object_title.short_description = 'Object'

    def types_display(self, obj):
        return ", ".join(obj.types)
    types_display.short_description = 'Reminder Type'