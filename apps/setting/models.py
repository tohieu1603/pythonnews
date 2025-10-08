import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class SettingScope(models.TextChoices):
    SYSTEM = 'system', 'System'
    USER = 'user', 'User'


class Setting(models.Model):
    """Key-value settings storage supporting system-wide and per-user overrides."""
    key = models.CharField(max_length=100)
    scope = models.CharField(max_length=20, choices=SettingScope.choices, default=SettingScope.SYSTEM)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'settings'
        db_table_comment = 'Generic key-value settings store supporting overrides.'
        unique_together = [('key', 'scope', 'user')]
        indexes = [
            models.Index(fields=['key'], name='idx_settings_key'),
            models.Index(fields=['scope'], name='idx_settings_scope'),
        ]

    def __str__(self):
        subject = self.user_id if self.scope == SettingScope.USER else 'system'
        return f"{self.key} ({self.scope}:{subject})"


class AutoRenewStatus(models.TextChoices):
    PENDING_ACTIVATION = 'pending_activation', 'Pending Activation'
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    SUSPENDED = 'suspended', 'Suspended'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class AutoRenewAttemptStatus(models.TextChoices):
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'


class SymbolAutoRenewSubscription(models.Model):
    """Represents an auto-renew subscription for a user-symbol pair."""
    subscription_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symbol_autorenew_subscriptions')
    symbol_id = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=AutoRenewStatus.choices, default=AutoRenewStatus.PENDING_ACTIVATION)
    cycle_days = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=30, default='wallet')
    last_order = models.ForeignKey('seapay.PaySymbolOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='autorenew_subscriptions')
    current_license = models.ForeignKey('seapay.PayUserSymbolLicense', on_delete=models.SET_NULL, null=True, blank=True, related_name='autorenew_subscriptions')
    next_billing_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveSmallIntegerField(default=0)
    grace_period_hours = models.PositiveIntegerField(default=12)
    retry_interval_minutes = models.PositiveIntegerField(default=60)
    max_retry_attempts = models.PositiveSmallIntegerField(default=3)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'symbol_autorenew_subscriptions'
        db_table_comment = 'Tracks auto-renew subscriptions for user symbols.'
        indexes = [
            models.Index(fields=['user', 'symbol_id'], name='idx_autorenew_user_symbol'),
            models.Index(fields=['status'], name='idx_autorenew_status'),
            models.Index(fields=['next_billing_at'], name='idx_autorenew_next_billing'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'symbol_id'],
                condition=Q(status__in=[AutoRenewStatus.PENDING_ACTIVATION, AutoRenewStatus.ACTIVE, AutoRenewStatus.PAUSED]),
                name='uq_autorenew_active_symbol'
            )
        ]

    def __str__(self):
        return f"Subscription {self.subscription_id} - {self.user_id} - {self.symbol_id}"

    @property
    def is_active(self) -> bool:
        return self.status in {AutoRenewStatus.ACTIVE, AutoRenewStatus.PAUSED} and (self.next_billing_at is not None)

    def mark_success(self, license_obj):
        self.current_license = license_obj
        self.last_success_at = timezone.now()
        self.consecutive_failures = 0
        self.status = AutoRenewStatus.ACTIVE
        self.save(update_fields=['current_license', 'last_success_at', 'consecutive_failures', 'status', 'updated_at'])

    def mark_failure(self, reason: str | None = None):
        self.consecutive_failures += 1
        self.last_attempt_at = timezone.now()
        if self.consecutive_failures >= self.max_retry_attempts:
            self.status = AutoRenewStatus.SUSPENDED
        self.save(update_fields=['consecutive_failures', 'last_attempt_at', 'status', 'updated_at'])


class SymbolAutoRenewAttempt(models.Model):
    attempt_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(SymbolAutoRenewSubscription, on_delete=models.CASCADE, related_name='attempts')
    order = models.ForeignKey('seapay.PaySymbolOrder', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=AutoRenewAttemptStatus.choices)
    fail_reason = models.TextField(blank=True)
    charged_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    wallet_balance_snapshot = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    ran_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'symbol_autorenew_attempts'
        db_table_comment = 'History of auto-renew execution attempts.'
        indexes = [
            models.Index(fields=['subscription'], name='idx_autorenew_attempt'),
            models.Index(fields=['ran_at'], name='idx_autorenew_attempt_ran_at'),
        ]

    @property
    def amount_charged(self):
        """Backwards compatible alias for charged_amount."""
        return self.charged_amount

    @property
    def error_message(self):
        """Backwards compatible alias for fail_reason."""
        return self.fail_reason

    def __str__(self):
        return f"Attempt {self.attempt_id} - {self.status}"
