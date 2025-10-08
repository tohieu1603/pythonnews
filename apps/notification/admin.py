from django.contrib import admin
from .models import UserEndpoint, NotificationEvent, NotificationDelivery, WebhookLog


@admin.register(UserEndpoint)
class UserEndpointAdmin(admin.ModelAdmin):
    list_display = ['endpoint_id', 'user', 'channel', 'address', 'is_primary', 'verified', 'created_at']
    list_filter = ['channel', 'is_primary', 'verified', 'created_at']
    search_fields = ['user__email', 'user__username', 'address']
    readonly_fields = ['endpoint_id', 'created_at']
    ordering = ['-created_at']


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'user', 'event_type', 'processed', 'created_at']
    list_filter = ['event_type', 'processed', 'created_at']
    search_fields = ['user__email', 'user__username', 'event_id']
    readonly_fields = ['event_id', 'created_at']
    ordering = ['-created_at']


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ['delivery_id', 'get_user', 'channel', 'status', 'sent_at']
    list_filter = ['channel', 'status', 'sent_at']
    search_fields = ['delivery_id', 'event__user__email']
    readonly_fields = ['delivery_id', 'response_raw']
    ordering = ['-sent_at']

    def get_user(self, obj):
        return obj.event.user.email if obj.event else None
    get_user.short_description = 'User'


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['webhook_id', 'source', 'symbol', 'status_code', 'users_notified', 'created_at']
    list_filter = ['source', 'status_code', 'created_at']
    search_fields = ['webhook_id', 'symbol', 'error_message']
    readonly_fields = ['webhook_id', 'created_at', 'payload', 'response_data']
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('webhook_id', 'source', 'symbol', 'created_at')
        }),
        ('Request', {
            'fields': ('payload',)
        }),
        ('Response', {
            'fields': ('status_code', 'response_data', 'users_notified')
        }),
        ('Error', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
