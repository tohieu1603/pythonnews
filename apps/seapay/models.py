import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

class IntentPurpose(models.TextChoices):
    WALLET_TOPUP = 'wallet_topup', 'Wallet Top-up'
    ORDER_PAYMENT = 'order_payment', 'Order Payment'
    SYMBOL_PURCHASE = 'symbol_purchase', 'Symbol Purchase'
    WITHDRAW = 'withdraw', 'Withdraw'


class PaymentStatus(models.TextChoices):
    REQUIRES_PAYMENT_METHOD = 'requires_payment_method', 'Requires Payment Method'
    PROCESSING = 'processing', 'Processing'
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'


class OrderStatus(models.TextChoices):
    PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'


class PaymentMethod(models.TextChoices):
    WALLET = 'wallet', 'Wallet Balance'
    SEPAY_TRANSFER = 'sepay_transfer', 'SePay Transfer (QR/Bank)'


class LicenseStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    SUSPENDED = 'suspended', 'Suspended'
    REVOKED = 'revoked', 'Revoked'


class WalletTxType(models.TextChoices):
    DEPOSIT = 'deposit', 'Nạp tiền (từ SePay)'
    PURCHASE = 'purchase', 'Mua bot'
    REFUND = 'refund', 'Hoàn tiền'
    WITHDRAWAL = 'withdrawal', 'Rút tiền'
    TRANSFER_IN = 'transfer_in', 'Chuyển đến'
    TRANSFER_OUT = 'transfer_out', 'Chuyển đi'


class PayOrder(models.Model):
    """
    Đơn hàng có thể được thanh toán qua payment intents.
    """
    order_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="Người tạo đơn hàng"
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Tổng giá trị đơn hàng"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
        ],
        default='pending',
        db_comment="Trạng thái đơn hàng"
    )
    description = models.TextField(
        blank=True,
        db_comment="Mô tả đơn hàng"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Dữ liệu bổ sung của đơn hàng"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pay_orders"
        db_table_comment = "Đơn hàng có thể được thanh toán qua payment intents."
        indexes = [
            models.Index(fields=['user'], name='idx_pay_orders_user'),
            models.Index(fields=['status'], name='idx_pay_orders_status'),
            models.Index(fields=['created_at'], name='idx_pay_orders_created'),
        ]

    def __str__(self):
        return f"Order {self.order_id} - {self.status} - {self.total_amount}"


class PayWallet(models.Model):
    """
    Ví điện tử của user. Mỗi user có 1 ví / 1 loại tiền.
    Tất cả thay đổi số dư đi qua pay_wallet_ledger.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ]

    CURRENCY_CHOICES = [
        ('VND', 'Vietnamese Dong'),
        ('USD', 'US Dollar'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="Chủ ví"
    )
    balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal('0.00'),
        db_comment="Số dư hiện tại, chỉ cập nhật qua ledger"
    )
    currency = models.CharField(
        max_length=10,
        choices=CURRENCY_CHOICES,
        default='VND',
        db_comment="Loại tiền (VNĐ, USD...)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_comment="active | suspended (khóa tạm thời)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pay_wallets"
        db_table_comment = "Mỗi user có 1 ví / 1 loại tiền. Tất cả thay đổi số dư đi qua pay_wallet_ledger."
        indexes = [
            models.Index(fields=['user'], name='idx_pay_wallets_user'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_user_wallet')
        ]

    def __str__(self):
        return f"Wallet {self.user.username} - {self.balance} {self.currency}"

    @property
    def is_active(self):
        return self.status == 'active'


class PayWalletLedger(models.Model):
    """
    Nguồn sự thật cho tất cả giao dịch ví. Mọi thay đổi số dùng phải đi qua ledger này.
    """
    ledger_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        PayWallet,
        on_delete=models.CASCADE,
        related_name='ledger_entries',
        db_comment="Ví bị ảnh hưởng"
    )
    tx_type = models.CharField(
        max_length=20,
        choices=WalletTxType.choices,
        db_comment="Loại biến động: nạp/purchase/hoàn tiền/..."
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Luôn > 0; chiều thể hiện bằng is_credit"
    )
    is_credit = models.BooleanField(
        db_comment="true: cộng ví; false: trừ ví"
    )
    balance_before = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Số dư trước giao dịch"
    )
    balance_after = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Số dư ngay sau giao dịch này"
    )
    order = models.ForeignKey(
        'PaySymbolOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Liên kết đơn hàng khi là purchase/refund"
    )
    payment = models.ForeignKey(
        'PayPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
        db_comment="Bắt buộc với deposit (nạp qua SePay)"
    )
    note = models.TextField(
        blank=True,
        db_comment="Diễn giải ngắn gọn cho bản ghi sổ cái"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Payload bổ sung: ip, device, source, ..."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pay_wallet_ledger"
        db_table_comment = "Quy tắc: deposit phải có payment_id (SePay); purchase phải có order_id. Sổ cái là nguồn sự thật để tính balance."
        indexes = [
            models.Index(fields=['wallet', 'created_at'], name='idx_ledger_wallet_created'),
            models.Index(fields=['payment'], name='idx_ledger_payment'),
            models.Index(fields=['tx_type'], name='idx_ledger_tx_type'),
            models.Index(fields=['order'], name='idx_ledger_order'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.is_credit else '-'
        return f"Ledger {self.wallet.user.username} {sign}{self.amount} -> {self.balance_after}"

    def save(self, *args, **kwargs):
        """Validate balance calculation"""
        if self.is_credit:
            expected_balance = self.balance_before + self.amount
        else:
            expected_balance = self.balance_before - self.amount

        if self.balance_after != expected_balance:
            raise ValueError(f"Balance calculation error: expected {expected_balance}, got {self.balance_after}")

        super().save(*args, **kwargs)


class PayPaymentIntent(models.Model):
    """
    Một yêu cầu thu tiền. Provider cố định là SePay (chính sách hệ thống).
    """
    intent_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="Ai đang thanh toán"
    )
    order = models.ForeignKey(
        'PaySymbolOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Liên kết nếu là thanh toán đơn"
    )
    purpose = models.CharField(
        max_length=20,
        choices=IntentPurpose.choices,
        db_comment="wallet_topup (nạp ví) | order_payment (mua trực tiếp)"
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Số tiền phải trả"
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.REQUIRES_PAYMENT_METHOD,
        db_comment="Trạng thái luồng thanh toán"
    )
    order_code = models.CharField(
        max_length=255,
        unique=True,
        db_comment="Chuỗi đối soát CK (nội dung chuyển khoản). Cần duy nhất để match."
    )
    reference_code = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_comment='Reference code returned by provider for reconciliation'
    )
    return_url = models.TextField(
        null=True,
        blank=True,
        db_comment="URL trở về khi thanh toán xong (nếu dùng webflow)"
    )
    cancel_url = models.TextField(
        null=True,
        blank=True,
        db_comment="URL trở về khi hủy"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="Hạn sử dụng intent/QR"
    )
    qr_code_url = models.TextField(
        null=True,
        blank=True,
        db_comment="QR code URL for payment"
    )
    deep_link = models.TextField(
        null=True,
        blank=True,
        db_comment="Deep link for mobile payment"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Payload bổ sung (IP, UA, campaign...)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pay_payment_intents"
        db_table_comment = "Một yêu cầu thu tiền. Provider cố định là SePay (chính sách hệ thống)."
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_pay_intents_user_status'),
            models.Index(fields=['order'], name='idx_pay_intents_order'),
        ]

    def __str__(self):
        return f"Intent {self.intent_id} - {self.status} - {self.amount}"

    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def is_pending(self):
        return self.status in [PaymentStatus.REQUIRES_PAYMENT_METHOD, PaymentStatus.PROCESSING]

    @property
    def is_completed(self):
        return self.status in [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.EXPIRED]

    def expire(self):
        """Mark intent as expired"""
        if self.is_pending():
            self.status = PaymentStatus.EXPIRED
            self.save(update_fields=['status', 'updated_at'])

    def succeed(self):
        """Mark intent as succeeded"""
        self.status = PaymentStatus.SUCCEEDED
        self.save(update_fields=['status', 'updated_at'])

    def fail(self):
        """Mark intent as failed"""
        self.status = PaymentStatus.FAILED
        self.save(update_fields=['status', 'updated_at'])


class PayPaymentAttempt(models.Model):
    """
    Một intent có thể có nhiều attempt (tạo lại QR, đổi số tiền...). Provider cố định: SePay.
    """
    attempt_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intent = models.ForeignKey(
        PayPaymentIntent,
        on_delete=models.CASCADE,
        db_comment="Thuộc intent nào"
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.REQUIRES_PAYMENT_METHOD,
        db_comment="Tiến trình attempt"
    )
    bank_code = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_comment="VCB/MB/BIDV... (SePay)"
    )
    account_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_comment="STK nhận hoặc VA theo đơn"
    )
    account_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_comment="Tên tài khoản nhận"
    )
    transfer_content = models.TextField(
        null=True,
        blank=True,
        db_comment="Nội dung CK chính xác để auto-match"
    )
    transfer_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        db_comment="Số tiền hiển thị trên QR (có thể khóa cứng)"
    )
    qr_image_url = models.TextField(
        null=True,
        blank=True,
        db_comment="Link ảnh QR động VietQR (SePay)"
    )
    qr_svg = models.TextField(
        null=True,
        blank=True,
        db_comment="Dữ liệu SVG QR nếu render trực tiếp"
    )
    provider_session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_comment="Mã phiên/khoá phía SePay nếu có"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="Hết hạn phiên attempt/QR"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Payload bổ sung"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pay_payment_attempts"
        db_table_comment = "Một intent có thể có nhiều attempt (tạo lại QR, đổi số tiền...). Provider cố định: SePay."
        indexes = [
            models.Index(fields=['intent'], name='idx_pay_attempts_intent'),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - Intent {self.intent.intent_id} - {self.status}"


class PayPayment(models.Model):
    """
    Bút toán thanh toán ở cấp "gateway". Khi succeeded: nếu là nạp ví -> ghi credit ledger;
    nếu là order -> chuyển order sang paid, cấp license.
    """
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="Người thực hiện thanh toán"
    )
    order = models.ForeignKey(
        'PaySymbolOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Đơn hàng liên quan (nếu có)"
    )
    intent = models.ForeignKey(
        PayPaymentIntent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Intent dẫn đến payment này"
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Số tiền thanh toán"
    )
    status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PROCESSING,
        db_comment="Trạng thái chốt sau khi đối soát"
    )
    provider_payment_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_comment="ID giao dịch SePay (sepay_tx_id) để tra soát"
    )
    message = models.TextField(
        null=True,
        blank=True,
        db_comment="Ghi chú trạng thái (VD: Lý do failed)"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Payload bổ sung (bản đồ đối soát, sai số...)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pay_payments"
        db_table_comment = "Bút toán thanh toán ở cấp gateway. Khi succeeded: nếu là nạp ví -> ghi credit ledger; nếu là order -> chuyển order sang paid, cấp license."
        indexes = [
            models.Index(fields=['user', 'created_at'], name='idx_pay_payments_user_created'),
            models.Index(fields=['intent'], name='idx_pay_payments_intent'),
            models.Index(fields=['order'], name='idx_pay_payments_order'),
        ]

    def __str__(self):
        return f"Payment {self.payment_id} - {self.status} - {self.amount}"


class PaySepayWebhookEvent(models.Model):
    """
    Inbox webhook của SePay. Ta luôn lưu thô trước, sau đó mới parse và xử lý để đảm bảo an toàn.
    """
    webhook_event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sepay_tx_id = models.BigIntegerField(
        unique=True,
        db_comment="ID duy nhất từ SePay để idempotent (tránh xử lý trùng)"
    )
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(
        db_comment="Lưu nguyên phần thân webhook để debug/đối soát"
    )
    processed = models.BooleanField(
        default=False,
        db_comment="Đã xử lý phát sinh payment/ledger chưa"
    )
    process_error = models.TextField(
        null=True,
        blank=True,
        db_comment="Thông tin lỗi nếu xử lý thất bại"
    )

    class Meta:
        db_table = "pay_sepay_webhook_events"
        db_table_comment = "Inbox webhook của SePay. Ta luôn lưu thô trước, sau đó mới parse và xử lý để đảm bảo an toàn."
        indexes = [
            models.Index(fields=['sepay_tx_id'], name='idx_sepay_webhooks_tx_id'),
            models.Index(fields=['processed'], name='idx_sepay_webhooks_processed'),
            models.Index(fields=['received_at'], name='idx_sepay_webhooks_received'),
        ]

    def __str__(self):
        return f"Webhook {self.webhook_event_id} - TX {self.sepay_tx_id} - Processed: {self.processed}"


class PayBankTransaction(models.Model):
    """
    Bảng đối soát chủ động từ API SePay: id, số tiền, nội dung, tham chiếu...
    """
    sepay_tx_id = models.BigIntegerField(
        primary_key=True,
        db_comment="Khớp với provider_payment_id khi đã xử lý"
    )
    transaction_date = models.DateTimeField(
        db_comment="Thời gian giao dịch ngân hàng"
    )
    account_number = models.CharField(
        max_length=50,
        db_comment="STK nhận tiền"
    )
    amount_in = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        db_comment="Tiền vào (nạp ví/ thanh toán)"
    )
    amount_out = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        db_comment="Tiền ra (ít dùng)"
    )
    content = models.TextField(
        null=True,
        blank=True,
        db_comment="Nội dung CK (chứa order_code để auto-match)"
    )
    reference_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_comment="Mã tham chiếu của ngân hàng"
    )
    bank_code = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_comment="VCB/MB/BIDV..."
    )
    intent = models.ForeignKey(
        PayPaymentIntent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Khớp được intent nào"
    )
    attempt = models.ForeignKey(
        PayPaymentAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Khớp được attempt nào"
    )
    payment = models.ForeignKey(
        PayPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Payment được tạo/chốt từ giao dịch này"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pay_bank_transactions"
        db_table_comment = "Bảng đối soát chủ động từ API SePay: id, số tiền, nội dung, tham chiếu..."
        indexes = [
            models.Index(fields=['intent'], name='idx_bank_tx_intent'),
            models.Index(fields=['reference_number'], name='idx_bank_tx_reference'),
            models.Index(fields=['account_number'], name='idx_bank_tx_account'),
        ]

    def __str__(self):
        return f"Bank TX {self.sepay_tx_id} - {self.amount_in} - {self.account_number}"


class SeapayOrder(models.Model):
    """Legacy model - use PayPaymentIntent instead"""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    def __str__(self):
        return f"Order {self.id} - {self.status}"


# ============================================================================
# BOT PURCHASE SYSTEM MODELS
# ============================================================================

class PaySymbolOrder(models.Model):
    """
    Đơn hàng để mua quyền truy cập symbol. Có thể thanh toán trực tiếp qua SePay hoặc trừ ví nếu đã nạp.
    """
    order_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="ID đơn hàng"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="Người mua quyền truy cập symbol"
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Tổng tiền cần trả cho đơn"
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING_PAYMENT,
        db_comment="Trạng thái vòng đời đơn"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        null=True,
        blank=True,
        db_comment="wallet (trừ ví) hoặc sepay_transfer (QR/STK)"
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_comment="Mô tả/ghi chú đơn hàng"
    )
    payment_intent = models.ForeignKey(
        'PayPaymentIntent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Payment intent cho SePay transfer"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pay_symbol_orders"
        db_table_comment = "Đơn hàng để mua quyền truy cập symbol. Có thể thanh toán trực tiếp qua SePay hoặc trừ ví nếu đã nạp."
        indexes = [
            models.Index(fields=['user', 'status'], name='idx_symbol_orders_user_status'),
            models.Index(fields=['status'], name='idx_symbol_orders_status'),
            models.Index(fields=['created_at'], name='idx_symbol_orders_created'),
        ]

    def __str__(self):
        return f"Symbol Order {self.order_id} - {self.user.username} - {self.status}"


class PaySymbolOrderItem(models.Model):
    """
    Chi tiết từng dòng sản phẩm trong đơn: symbol nào, thời hạn bao lâu.
    """
    order_item_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="ID item đơn hàng"
    )
    order = models.ForeignKey(
        PaySymbolOrder,
        on_delete=models.CASCADE,
        related_name='items',
        db_comment="Đơn hàng chính"
    )
    symbol_id = models.BigIntegerField(
        db_comment="Symbol là sản phẩm được bán"
    )
    price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        db_comment="Đơn giá tại thời điểm mua"
    )
    license_days = models.IntegerField(
        null=True,
        blank=True,
        db_comment="Số ngày cấp quyền sử dụng symbol; null = trọn đời"
    )
    auto_renew = models.BooleanField(
        default=False,
        db_comment="Mark this order item as enrolled in auto-renew"
    )
    cycle_days_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_comment="Override renewal cycle in days; None uses subscription default"
    )
    auto_renew_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        db_comment="Override price for subsequent renewals; None uses current price"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_comment="Thuộc tính thêm (phiên bản, biến thể, ...)"
    )

    class Meta:
        db_table = "pay_symbol_order_items"
        db_table_comment = "Chi tiết từng dòng sản phẩm trong đơn: symbol nào, thời hạn bao lâu."
        indexes = [
            models.Index(fields=['order'], name='idx_symbol_order_items_order'),
            models.Index(fields=['symbol_id'], name='idx_symbol_order_items_symbol'),
        ]

    def __str__(self):
        return f"Order Item {self.order_item_id} - Symbol {self.symbol_id}"


class PayUserSymbolLicenseManager(models.Manager):
    def create(self, **kwargs):
        is_lifetime = kwargs.pop('is_lifetime', None)
        if is_lifetime is True:
            kwargs['end_at'] = None
        return super().create(**kwargs)


class PayUserSymbolLicense(models.Model):
    """
    Quyền sử dụng symbol để quyết định ai được nhận tín hiệu.
    Gia hạn bằng cách tạo license mới hoặc cập nhật end_at.
    """
    objects = PayUserSymbolLicenseManager()

    def __init__(self, *args, is_lifetime=None, **kwargs):
        if is_lifetime is True:
            kwargs.setdefault('end_at', None)
        super().__init__(*args, **kwargs)

    license_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_comment="ID license"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_comment="User được cấp quyền"
    )
    symbol_id = models.BigIntegerField(
        db_comment="Symbol được cấp quyền"
    )
    order = models.ForeignKey(
        PaySymbolOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_comment="Đơn hàng tạo ra license này"
    )
    subscription = models.ForeignKey(
        'setting.SymbolAutoRenewSubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='licenses',
        db_comment="Auto-renew subscription that governs this license"
    )
    status = models.CharField(
        max_length=20,
        choices=LicenseStatus.choices,
        default=LicenseStatus.ACTIVE,
        db_comment="Trạng thái quyền dùng symbol"
    )
    start_at = models.DateTimeField(
        default=timezone.now,
        db_comment="Thời điểm kích hoạt"
    )
    end_at = models.DateTimeField(
        null=True,
        blank=True,
        db_comment="Thời điểm hết hạn; null = trọn đời"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pay_user_symbol_licenses"
        db_table_comment = "Quyền sử dụng symbol để quyết định ai được nhận tín hiệu."
        indexes = [
            models.Index(fields=['user', 'symbol_id'], name='idx_symbol_lic_user_symbol'),
            models.Index(fields=['status'], name='idx_symbol_lic_status'),
            models.Index(fields=['end_at'], name='idx_symbol_lic_end_at'),
            models.Index(fields=['subscription'], name='idx_symbol_lic_subscription'),
        ]
        unique_together = [('user', 'symbol_id', 'start_at')]

    def __str__(self):
        return f"License {self.license_id} - {self.user.username} - Symbol {self.symbol_id}"

    @property
    def is_active(self):
        """Kiểm tra license có còn hiệu lực không"""
        if self.status != LicenseStatus.ACTIVE:
            return False
        if self.end_at and timezone.now() > self.end_at:
            return False
        return True

    @property
    def is_lifetime(self):
        """Kiểm tra có phải license trọn đời không"""
        return self.end_at is None


class IntentStatus(models.TextChoices):
    PENDING = 'requires_payment_method', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'succeeded', 'Completed'
    FAILED = 'failed', 'Failed'
    EXPIRED = 'expired', 'Expired'

PaySymbolLicense = PayUserSymbolLicense