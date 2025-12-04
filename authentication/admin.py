from django.contrib import admin
from .models import UserAccount, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('birth_date', 'country', 'phone_number', 'notifications_enabled', 'fcm_token', 'fcm_token_updated_at')
    readonly_fields = ('fcm_token_updated_at', 'created_at', 'updated_at')


class UserAccountAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'full_name', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_google_auth', 'is_apple_auth')
    search_fields = ('email', 'username', 'full_name')
    readonly_fields = ('id', 'date_joined', 'last_login')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'email', 'username', 'full_name', 'profile_pic', 'gender', 'phone_number')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('OAuth', {
            'fields': ('google_id', 'is_google_auth', 'did_google_auth', 'apple_id', 'is_apple_auth', 'did_apple_auth')
        }),
        ('Dates', {
            'fields': ('date_joined', 'last_login', 'deletion_scheduled_at')
        }),
        ('Account Management', {
            'fields': ('username_update_count', 'last_username_update', 'new_email')
        }),
    )
    
    inlines = (UserProfileInline,)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'country', 'phone_number', 'notifications_enabled', 'created_at')
    list_filter = ('notifications_enabled', 'country')
    search_fields = ('user__email', 'user__username', 'country', 'phone_number')
    readonly_fields = ('created_at', 'updated_at', 'fcm_token_updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('birth_date', 'country', 'phone_number', 'notifications_enabled')
        }),
        ('FCM Token', {
            'fields': ('fcm_token', 'fcm_token_updated_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


admin.site.register(UserAccount, UserAccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
