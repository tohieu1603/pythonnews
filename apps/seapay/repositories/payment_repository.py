from typing import Optional, List, Tuple
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.seapay.models import PayWallet, PayPaymentIntent, SeapayOrder

User = get_user_model()


class PaymentRepository:
    """Repository layer cho payment operations"""
    
    @staticmethod
    def get_or_create_wallet(user: User, currency: str = "VND") -> tuple[PayWallet, bool]:
        """Tạo hoặc lấy wallet của user"""
        return PayWallet.objects.get_or_create(
            user=user,
            defaults={
                'currency': currency,
                'balance': Decimal('0.00'),
                'status': 'active'
            }
        )
    
    @staticmethod
    def get_wallet_by_user(user: User) -> Optional[PayWallet]:
        """Lấy wallet của user"""
        try:
            return PayWallet.objects.get(user=user)
        except PayWallet.DoesNotExist:
            return None
    
    @staticmethod
    def create_payment_intent(
        user: User,
        wallet: PayWallet,
        provider: str,
        purpose: str,
        amount: Decimal,
        order_code: str,
        expires_at,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        metadata: dict = None
    ) -> PayPaymentIntent:
        """Tạo payment intent mới"""
        # Tạo intent với QR code URL
        intent = PayPaymentIntent.objects.create(
            user=user,
            purpose=purpose,
            amount=amount,
            order_code=order_code,
            return_url=return_url,
            cancel_url=cancel_url,
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        intent.qr_code_url = (
            f"https://qr.sepay.vn/img?acc=96247CISI1"
            f"&bank=BIDV"
            f"&amount={int(amount)}"
            f"&des={order_code}"
            f"&template=compact"
        )
        
        intent.deep_link = (
            f"https://sepay.vn/payment?acc=96247CISI1"
            f"&bank=BIDV"
            f"&amount={int(amount)}"
            f"&des={order_code}"
        )
        
        intent.save()
        
        return intent
    
    @staticmethod
    def get_payment_intent_by_order_code(order_code: str) -> Optional[PayPaymentIntent]:
        """Tìm payment intent theo order code"""
        try:
            return PayPaymentIntent.objects.get(order_code=order_code)
        except PayPaymentIntent.DoesNotExist:
            return None
    
    @staticmethod
    def get_payment_intent_by_id(intent_id: str, user: User) -> Optional[PayPaymentIntent]:
        """Tìm payment intent theo ID và user"""
        try:
            return PayPaymentIntent.objects.get(intent_id=intent_id, user=user)
        except PayPaymentIntent.DoesNotExist:
            return None
    
    @staticmethod
    def update_wallet_balance(wallet: PayWallet, amount: Decimal) -> None:
        """Cập nhật balance của wallet"""
        with transaction.atomic():
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
    
    @staticmethod
    def update_payment_intent_status(
        intent: PayPaymentIntent, 
        status: str, 
        reference_code: Optional[str] = None
    ) -> None:
        """Cập nhật status của payment intent"""
        intent.status = status
        update_fields = ['status', 'updated_at']
        if reference_code:
            intent.reference_code = reference_code
            metadata = intent.metadata or {}
            metadata['reference_code'] = reference_code
            intent.metadata = metadata
            update_fields.extend(['reference_code', 'metadata'])
        intent.save(update_fields=update_fields)
    
    @staticmethod
    def get_or_create_legacy_order(order_id: str, amount: Decimal, description: str = "") -> tuple[SeapayOrder, bool]:
        """Tạo hoặc lấy legacy order (cho compatibility)"""
        return SeapayOrder.objects.get_or_create(
            defaults={
                "amount": amount,
                "description": description,
                "status": "pending",
            },
        )
    
    @staticmethod
    def get_all_payment_intents_by_user(user: User) -> List[PayPaymentIntent]:
        """Lấy tất cả payment intents của user"""
        return PayPaymentIntent.objects.filter(user=user).order_by('-created_at')
    
    @staticmethod
    def get_wallet_by_user(user: User) -> Optional[PayWallet]:
        """Lấy wallet của user"""
        try:
            return PayWallet.objects.filter(user=user).first()
        except PayWallet.DoesNotExist:
            return None
        
    @staticmethod
    def get_payment_intents_by_user(
        user: User,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> Tuple[int, List[PayPaymentIntent]]:
        """Lấy payment intents của user với phân trang và filter"""
        page = page or 1
        limit = limit or 10
        
        qs = PayPaymentIntent.objects.filter(user=user).select_related('user') 

        if search:
            qs = qs.filter(order_code__icontains=search)

        if status:
            qs = qs.filter(status=status)

        if purpose:
            qs = qs.filter(purpose=purpose)

        total = qs.count()

        offset = (page - 1) * limit
        items = qs.order_by("-created_at")[offset : offset + limit]

        return total, list(items)

    
        
