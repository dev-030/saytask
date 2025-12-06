from django.contrib import admin
from .models import LegalDocument, ActivityLog


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_type', 'version', 'created_by', 'updated_at')
    list_filter = ('document_type', 'created_at')
    search_fields = ('content', 'version')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    
    def has_delete_permission(self, request, obj=None):
        return False  # Prevent deletion


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'description', 'amount', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__email', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False  # Logs are created programmatically only
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs
