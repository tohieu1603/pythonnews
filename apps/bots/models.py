import uuid
from django.db import models


class BotType(models.TextChoices):
    """Loại bot theo kỳ hạn"""
    SHORT_TERM = 'short', 'Ngắn hạn'
    MEDIUM_TERM = 'medium', 'Trung hạn'
    LONG_TERM = 'long', 'Dài hạn'


class Bot(models.Model):
    """Thông tin bot TradingView gắn với từng symbol"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    bot_type = models.CharField(
        max_length=10,
        choices=BotType.choices,
        default=BotType.SHORT_TERM,
        help_text='Loại bot: Ngắn hạn, Trung hạn, Dài hạn'
    )
    symbol = models.ForeignKey(
        'stock.Symbol',
        on_delete=models.CASCADE,
        related_name='bots'
    )

    class Meta:
        db_table = 'bots'
        unique_together = [['symbol', 'bot_type']]
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['bot_type']),
        ]

    def __str__(self):
        symbol_name = getattr(self.symbol, 'name', self.symbol_id)
        bot_type_display = self.get_bot_type_display()
        return f"{symbol_name} - {bot_type_display}"


class Trade(models.Model):
    """Nhật ký giao dịch cho từng bot"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trans_id = models.BigIntegerField(help_text='Lệnh mở và đóng cùng một trans_id')
    trade_type = models.CharField(max_length=10, db_column='type')
    direction = models.CharField(max_length=10, null=True, blank=True)
    price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, help_text='Giá vào')
    entry_date = models.DateTimeField(help_text='Thời điểm có lệnh')
    exit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, help_text='Giá thoát')
    stop_loss = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, help_text='Giá dừng lỗ')
    take_profit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, help_text='Giá chốt lời')
    position_size = models.FloatField(null=True, blank=True)
    profit = models.FloatField(null=True, blank=True, help_text='Phần trăm lợi nhuận')
    max_duration = models.IntegerField(null=True, blank=True)
    win_loss_status = models.CharField(max_length=10, null=True, blank=True)
    action = models.CharField(max_length=10, help_text='Open | Close')
    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE,
        related_name='trades'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trades'
        indexes = [
            models.Index(fields=['trans_id']),
            models.Index(fields=['bot', 'entry_date']),
        ]

    def __str__(self):
        return f"{self.bot_id} - {self.trade_type} ({self.trans_id})"
