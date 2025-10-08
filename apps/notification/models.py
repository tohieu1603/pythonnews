import uuid
from django.conf import settings
from django.db import models


class NotificationChannel(models.TextChoices):
    TELEGRAM = 'telegram', 'Telegram'
    ZALO = 'zalo', 'Zalo'
    EMAIL = 'email', 'Email'


class AppEventType(models.TextChoices):
    SYMBOL_SIGNAL = 'symbol_signal', 'Symbol Signal'
    PAYMENT_SUCCESS = 'payment_success', 'Payment Success'
    PAYMENT_FAILED = 'payment_failed', 'Payment Failed'
    ORDER_CREATED = 'order_created', 'Order Created'
    ORDER_FILLED = 'order_filled', 'Order Filled'
    SUBSCRIPTION_EXPIRING = 'subscription_expiring', 'Subscription Expiring'


class DeliveryStatus(models.TextChoices):
    QUEUED = 'queued', 'Queued'
    SENDING = 'sending', 'Sending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    RETRYING = 'retrying', 'Retrying'


class UserEndpoint(models.Model):
    """Sổ danh bạ kênh thông báo của người dùng"""
    endpoint_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_endpoints'
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    address = models.TextField(help_text='Telegram chat_id | Zalo user_id | email')
    details = models.JSONField(
        null=True,
        blank=True,
        help_text='Thông tin phụ: username, OA id...'
    )
    is_primary = models.BooleanField(
        default=False,
        help_text='Đánh dấu endpoint mặc định'
    )
    verified = models.BooleanField(
        default=False,
        help_text='Đã xác thực (OTP/symbol start) hay chưa'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pay_user_endpoints'
        unique_together = [['user', 'channel', 'address']]
        indexes = [
            models.Index(fields=['user', 'channel', 'address']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.channel}: {self.address}"


class NotificationEvent(models.Model):
    """Hàng đợi sự kiện logic. Từ đây sẽ sinh các bản ghi deliveries theo từng kênh"""
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_events'
    )
    event_type = models.CharField(
        max_length=50,
        choices=AppEventType.choices,
        help_text='Loại sự kiện nghiệp vụ cần gửi thông báo'
    )
    subject_id = models.UUIDField(
        null=True,
        blank=True,
        help_text='ID thực thể liên quan: order_id/payment_id/signal_id...'
    )
    payload = models.JSONField(
        null=True,
        blank=True,
        help_text='Dữ liệu để render tin nhắn (template)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(
        default=False,
        help_text='Đã phát lệnh gửi tới các endpoint chưa'
    )

    class Meta:
        db_table = 'pay_notification_events'
        indexes = [
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['processed', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.user.email} ({self.event_id})"


class NotificationDelivery(models.Model):
    """Nhật ký gửi tin theo từng endpoint. Dùng để retry/thống kê"""
    delivery_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        NotificationEvent,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    endpoint = models.ForeignKey(
        UserEndpoint,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.QUEUED
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    response_raw = models.JSONField(
        null=True,
        blank=True,
        help_text='Phản hồi từ API Telegram/Zalo/Email'
    )
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'pay_notification_deliveries'
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['endpoint']),
            models.Index(fields=['status', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.channel} - {self.status} ({self.delivery_id})"

class WebhookSource(models.TextChoices):
    """Nguồn webhook"""
    TRADINGVIEW = 'tradingview', 'TradingView'
    CUSTOM = 'custom', 'Custom'


class WebhookLog(models.Model):
    """Log tất cả webhook requests từ TradingView và các nguồn khác"""
    webhook_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(
        max_length=50,
        choices=WebhookSource.choices,
        default=WebhookSource.TRADINGVIEW,
        help_text='Nguồn gửi webhook'
    )
    symbol = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text='Mã chứng khoán'
    )
    payload = models.JSONField(
        help_text='Toàn bộ payload nhận được từ webhook'
    )
    status_code = models.IntegerField(
        default=200,
        db_index=True,
        help_text='HTTP status code trả về'
    )
    response_data = models.JSONField(
        null=True,
        blank=True,
        help_text='Response data trả về cho webhook caller'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='Lỗi xảy ra (nếu có)'
    )
    users_notified = models.IntegerField(
        default=0,
        help_text='Số user đã được gửi notification'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'pay_webhook_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', '-created_at']),
            models.Index(fields=['symbol', '-created_at']),
            models.Index(fields=['status_code', '-created_at']),
        ]

    def __str__(self):
        return f"{self.source} - {self.symbol or 'N/A'} ({self.created_at})"
