from django.apps import AppConfig


class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notification'
    verbose_name = 'Notification Management'

    def ready(self):

        import apps.notification.signals
