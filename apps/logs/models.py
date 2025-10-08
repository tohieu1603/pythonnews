from django.contrib.postgres.indexes import GinIndex
from django.db import models


class LogEntry(models.Model):
    """
    Logs table để ghi lại tất cả activities trong hệ thống.
    Tương thích với PostgreSQL và sử dụng JSONB cho performance tốt.
    """
    # Thứ tự fields theo SQL schema
    created_at = models.DateTimeField(auto_now_add=True, db_comment="Timestamp when log was created")
    level = models.CharField(max_length=20, db_comment="Log level: debug, info, warning, error, critical")
    channel = models.CharField(max_length=50, db_comment="Log channel: app, queue, payment, web, etc.")
    message = models.TextField(db_comment="Log message content")
    context = models.JSONField(
        default=dict, 
        blank=True,
        db_comment="Structured metadata: user_id, request_id, ip, url, exception, stack"
    )
    extra = models.JSONField(
        default=dict, 
        blank=True,
        db_comment="Optional extra data"
    )
    environment = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        db_comment="Environment: production, staging, local"
    )

    class Meta:
        db_table = "logs"
        db_table_comment = "System logs for auditing and debugging"
        indexes = [
            models.Index(fields=["-created_at"], name="idx_logs_created_at"),
            models.Index(fields=["level"], name="idx_logs_level"),
            models.Index(fields=["channel"], name="idx_logs_channel"),
            GinIndex(fields=["context"], name="idx_logs_context_gin"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.created_at}] {self.level.upper()} - {self.channel}: {self.message[:50]}"

    @property
    def user_id(self):
        """Helper để lấy user_id từ context"""
        return self.context.get('user_id') if self.context else None

    @property
    def request_id(self):
        """Helper để lấy request_id từ context"""
        return self.context.get('request_id') if self.context else None

    @classmethod
    def get_by_user(cls, user_id):
        """Lấy logs theo user_id"""
        return cls.objects.filter(context__user_id=user_id)

    @classmethod
    def get_by_level(cls, level):
        """Lấy logs theo level"""
        return cls.objects.filter(level=level)

    @classmethod
    def get_recent(cls, hours=24):
        """Lấy logs trong N giờ gần nhất"""
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        return cls.objects.filter(created_at__gte=since)
