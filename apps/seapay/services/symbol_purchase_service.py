import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..models import (
    IntentPurpose,
    LicenseStatus,
    OrderStatus,
    PayPaymentIntent,
    PaySymbolOrder,
    PaySymbolOrderItem,
    PayUserSymbolLicense,
    PayWallet,
    PayWalletLedger,
    PaymentMethod,
    WalletTxType,
)
from .payment_service import PaymentService
from apps.setting.services.subscription_service import SymbolAutoRenewService
from apps.stock.models import Symbol

User = get_user_model()
logger = logging.getLogger(__name__)


class SymbolPurchaseService:
    """Handle symbol purchase flows including wallet and SePay payments."""

    def __init__(self) -> None:
        self.payment_service = PaymentService()
        self.subscription_service = SymbolAutoRenewService()

    def create_symbol_order(
        self,
        user: User,
        items: List[Dict],
        payment_method: str,
        description: Optional[str] = None,
    ) -> PaySymbolOrder | Dict[str, object]:
        if payment_method not in {PaymentMethod.WALLET, PaymentMethod.SEPAY_TRANSFER}:
            raise ValueError(f"Invalid payment method: {payment_method}")
        if not items:
            raise ValueError("Order must have at least one item")

        normalized_items: List[Dict] = []
        total_amount = Decimal("0")

        for raw in items:
            if "symbol_id" not in raw or "price" not in raw:
                raise ValueError("Each item must include symbol_id and price")

            price = Decimal(str(raw["price"]))
            if price <= 0:
                raise ValueError("Price must be positive")

            license_days = raw.get("license_days")
            metadata = raw.get("metadata") or {}
            auto_renew = bool(raw.get("auto_renew", False))
            cycle_override = raw.get("auto_renew_cycle_days")
            if cycle_override is not None:
                cycle_override = int(cycle_override)
                if cycle_override <= 0:
                    raise ValueError("Auto-renew cycle days must be positive")
            auto_renew_price = raw.get("auto_renew_price")
            if auto_renew_price is not None:
                auto_renew_price = Decimal(str(auto_renew_price))
                if auto_renew_price <= 0:
                    raise ValueError("Auto-renew price must be positive")

            normalized_items.append(
                {
                    "symbol_id": raw["symbol_id"],
                    "price": price,
                    "license_days": license_days,
                    "metadata": metadata,
                    "auto_renew": auto_renew,
                    "cycle_days_override": cycle_override,
                    "auto_renew_price": auto_renew_price,
                }
            )
            total_amount += price

        symbol_ids = {item["symbol_id"] for item in normalized_items}
        if symbol_ids:
            existing = set(
                Symbol.objects.filter(id__in=symbol_ids).values_list("id", flat=True)
            )
            missing = symbol_ids - existing
            if missing:
                raise ValueError("Symbol not found")

        with transaction.atomic():
            order = PaySymbolOrder.objects.create(
                user=user,
                total_amount=total_amount,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=payment_method,
                description=description or f"Symbol purchase x{len(normalized_items)}",
            )
            for item in normalized_items:
                PaySymbolOrderItem.objects.create(
                    order=order,
                    symbol_id=item["symbol_id"],
                    price=item["price"],
                    license_days=item["license_days"],
                    auto_renew=item["auto_renew"],
                    cycle_days_override=item["cycle_days_override"],
                    auto_renew_price=item["auto_renew_price"],
                    metadata=item["metadata"],
                )

        self.subscription_service.sync_pending_from_order(order)

        if payment_method == PaymentMethod.WALLET:
            wallet = PayWallet.objects.filter(user=user).first()
            if not wallet:
                order.delete()
                raise ValueError("User wallet not found. Please create a wallet first.")

            if wallet.balance >= total_amount:
                return self._process_immediate_wallet_payment(order, wallet)

            # Không đủ tiền - trả về đơn pending để user chọn thanh toán bằng SePay
            shortage = total_amount - wallet.balance
            return {
                "order": order,
                "insufficient_balance": True,
                "wallet_balance": wallet.balance,
                "total_amount": total_amount,
                "shortage": shortage,
                "message": f"Số dư ví không đủ. Thiếu {shortage:,.0f} VND. Vui lòng chọn thanh toán bằng SePay."
            }

        payment_intent = self._create_sepay_payment_intent_for_order(order)
        return {"order": order, "payment_intent": payment_intent}

    def _create_sepay_payment_intent_for_order(
        self,
        order: PaySymbolOrder,
    ) -> Optional[PayPaymentIntent]:
        try:
            intent = self.payment_service.create_payment_intent(
                user=order.user,
                purpose=IntentPurpose.SYMBOL_PURCHASE,
                amount=order.total_amount,
                currency="VND",
                metadata={
                    "order_id": str(order.order_id),
                    "order_type": "symbol_purchase",
                    "items_count": order.items.count(),
                    "auto_created": True,
                },
            )
            order.payment_intent = intent
            order.save(update_fields=["payment_intent", "updated_at"])
            return intent
        except Exception as exc: 
            logger.exception(
                "Failed to create SePay intent for order %s: %s", order.order_id, exc
            )
            return None

    def _process_immediate_wallet_payment(
        self,
        order: PaySymbolOrder,
        wallet: PayWallet,
    ) -> PaySymbolOrder:
        with transaction.atomic():
            ledger_entry = PayWalletLedger.objects.create(
                wallet=wallet,
                tx_type=WalletTxType.PURCHASE,
                amount=order.total_amount,
                is_credit=False,
                balance_before=wallet.balance,
                balance_after=wallet.balance - order.total_amount,
                order_id=order.order_id,
                note=f"Symbol purchase order {order.order_id}",
            )
            wallet.balance = ledger_entry.balance_after
            wallet.save(update_fields=["balance", "updated_at"])

            order.status = OrderStatus.PAID
            order.save(update_fields=["status", "updated_at"])

        self._create_symbol_licenses(order)
        self.subscription_service.activate_for_order(order)
        return order

    def create_sepay_topup_for_insufficient_order(self, order_id: str, user: User) -> Dict[str, object]:
        try:
            order = PaySymbolOrder.objects.get(order_id=order_id, user=user)
        except PaySymbolOrder.DoesNotExist as exc:
            raise ValueError("Order not found") from exc

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise ValueError(f"Order status is {order.status}, cannot create top-up")
        if order.payment_method != PaymentMethod.WALLET:
            raise ValueError("Top-up is only available for wallet orders")

        wallet = PayWallet.objects.filter(user=user).first()
        if not wallet:
            raise ValueError("User wallet not found")

        required_amount = order.total_amount - wallet.balance
        if required_amount <= 0:
            raise ValueError("Wallet balance is sufficient, no top-up needed")

        intent = self.payment_service.create_payment_intent(
            user=user,
            purpose=IntentPurpose.WALLET_TOPUP,
            amount=required_amount,
            currency="VND",
            metadata={
                "order_id": str(order.order_id),
                "order_type": "symbol_purchase_topup",
                "required_amount": float(required_amount),
                "current_balance": float(wallet.balance),
                "order_total": float(order.total_amount),
            },
        )

        order.payment_intent = intent
        order.save(update_fields=["payment_intent", "updated_at"])

        return {
            "intent_id": str(intent.intent_id),
            "order_code": intent.order_code,
            "amount": required_amount,
            "currency": "VND",
            "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
            "qr_code_url": intent.qr_code_url,
            "message": f"Create a SePay top-up for {required_amount:,.0f} VND to finish the order.",
        }

    @transaction.atomic
    def process_wallet_payment(self, order_id: str, user: User) -> Dict[str, object]:
        try:
            order = PaySymbolOrder.objects.select_for_update().get(order_id=order_id, user=user)
        except PaySymbolOrder.DoesNotExist as exc:
            raise ValueError("Order not found") from exc

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise ValueError(f"Order status is {order.status}, cannot process payment")
        if order.payment_method != PaymentMethod.WALLET:
            raise ValueError("Order payment method is not wallet")

        wallet = PayWallet.objects.select_for_update().get(user=user)
        if wallet.balance < order.total_amount:
            raise ValueError(
                f"Insufficient balance. Required: {order.total_amount}, Available: {wallet.balance}"
            )

        ledger_entry = PayWalletLedger.objects.create(
            wallet=wallet,
            tx_type=WalletTxType.PURCHASE,
            amount=order.total_amount,
            is_credit=False,
            balance_before=wallet.balance,
            balance_after=wallet.balance - order.total_amount,
            order_id=order.order_id,
            note=f"Symbol purchase order {order.order_id}",
        )
        wallet.balance = ledger_entry.balance_after
        wallet.save(update_fields=["balance", "updated_at"])

        order.status = OrderStatus.PAID
        order.save(update_fields=["status", "updated_at"])

        licenses_created = self._create_symbol_licenses(order)
        subscriptions = self.subscription_service.activate_for_order(order)

        return {
            "success": True,
            "message": "Payment processed successfully",
            "order_id": str(order.order_id),
            "amount_charged": float(order.total_amount),
            "wallet_balance_after": float(wallet.balance),
            "licenses_created": licenses_created,
            "subscriptions_updated": len(subscriptions),
        }

    def create_sepay_payment_intent(self, order_id: str, user: User) -> Dict[str, object]:
        try:
            order = PaySymbolOrder.objects.get(order_id=order_id, user=user)
        except PaySymbolOrder.DoesNotExist as exc:
            raise ValueError("Order not found") from exc

        if order.status != OrderStatus.PENDING_PAYMENT:
            raise ValueError(f"Order status is {order.status}, cannot create payment intent")

        # Cho phép tạo payment intent cho cả wallet và sepay_transfer orders
        # Vì khi wallet thiếu tiền, user có thể chọn thanh toán bằng SePay
        if order.payment_method not in [PaymentMethod.WALLET, PaymentMethod.SEPAY_TRANSFER]:
            raise ValueError(f"Cannot create SePay payment intent for payment method: {order.payment_method}")

        intent = self.payment_service.create_payment_intent(
            user=user,
            purpose=IntentPurpose.ORDER_PAYMENT,
            amount=order.total_amount,
            currency="VND",
            metadata={
                "order_id": str(order.order_id),
                "order_type": "symbol_purchase",
                "items_count": order.items.count(),
            },
        )

        order.payment_intent = intent
        order.save(update_fields=["payment_intent", "updated_at"])

        return {
            "intent_id": str(intent.intent_id),
            "order_code": intent.order_code,
            "amount": intent.amount,
            "currency": "VND",
            "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
            "qr_code_url": intent.qr_code_url,
            "message": "Payment intent created successfully.",
        }

    def process_sepay_payment_completion(self, payment_id: str) -> Dict[str, object]:
        from ..models import PayPayment

        try:
            payment = PayPayment.objects.get(payment_id=payment_id)
        except PayPayment.DoesNotExist as exc:
            raise ValueError("Payment or order not found") from exc

        intent = payment.intent
        if intent and intent.purpose == IntentPurpose.WALLET_TOPUP:
            metadata = intent.metadata or {}
            order_id = metadata.get("order_id")
            if order_id:
                return self._process_topup_and_auto_payment(payment, order_id)

        if not payment.order_id:
            raise ValueError("Payment is not linked to any order")

        order = PaySymbolOrder.objects.get(order_id=payment.order_id)
        if order.status == OrderStatus.PAID:
            return {"success": True, "message": "Order already processed", "order_id": str(order.order_id)}

        order.status = OrderStatus.PAID
        order.save(update_fields=["status", "updated_at"])

        licenses_created = self._create_symbol_licenses(order)
        self.subscription_service.activate_for_order(order)

        return {
            "success": True,
            "message": "SePay payment completed and licenses created",
            "order_id": str(order.order_id),
            "payment_id": str(payment.payment_id),
            "licenses_created": licenses_created,
        }

    @transaction.atomic
    def _process_topup_and_auto_payment(self, payment, order_id: str) -> Dict[str, object]:
        order = PaySymbolOrder.objects.select_for_update().get(order_id=order_id)
        wallet = PayWallet.objects.select_for_update().get(user=order.user)

        if wallet.balance < order.total_amount:
            return {
                "success": False,
                "message": "Wallet balance still insufficient after top-up.",
                "order_id": str(order.order_id),
                "topup_amount": float(payment.amount),
                "current_balance": float(wallet.balance),
            }

        ledger_entry = PayWalletLedger.objects.create(
            wallet=wallet,
            tx_type=WalletTxType.PURCHASE,
            amount=order.total_amount,
            is_credit=False,
            balance_before=wallet.balance,
            balance_after=wallet.balance - order.total_amount,
            order_id=order.order_id,
            note=f"Auto-payment after top-up for order {order.order_id}",
        )
        wallet.balance = ledger_entry.balance_after
        wallet.save(update_fields=["balance", "updated_at"])

        order.status = OrderStatus.PAID
        order.save(update_fields=["status", "updated_at"])

        licenses_created = self._create_symbol_licenses(order)
        self.subscription_service.activate_for_order(order)

        return {
            "success": True,
            "message": "Top-up completed and order paid",
            "order_id": str(order.order_id),
            "topup_amount": float(payment.amount),
            "order_amount": float(order.total_amount),
            "wallet_balance_after": float(wallet.balance),
            "licenses_created": licenses_created,
            "auto_payment": True,
        }

    def _create_symbol_licenses(self, order: PaySymbolOrder) -> int:
        licenses_created = 0
        now = timezone.now()

        for item in order.items.all():
            start_at = now
            end_at = None
            if item.license_days:
                end_at = start_at + timedelta(days=item.license_days)

            existing = PayUserSymbolLicense.objects.filter(
                user=order.user,
                symbol_id=item.symbol_id,
                status=LicenseStatus.ACTIVE,
            ).first()

            if existing:
                if existing.end_at and end_at:
                    existing.end_at = max(existing.end_at, end_at)
                elif not end_at:
                    existing.end_at = None
                existing.order = order
                existing.save(update_fields=["end_at", "order", "updated_at"])
                licenses_created += 1
                continue

            PayUserSymbolLicense.objects.create(
                user=order.user,
                symbol_id=item.symbol_id,
                order=order,
                status=LicenseStatus.ACTIVE,
                start_at=start_at,
                end_at=end_at,
            )
            licenses_created += 1

        return licenses_created

    def check_symbol_access(self, user: User, symbol_id: int) -> Dict[str, object]:
        license_obj = PayUserSymbolLicense.objects.filter(
            user=user,
            symbol_id=symbol_id,
            status=LicenseStatus.ACTIVE,
        ).first()

        if not license_obj:
            return {"has_access": False, "reason": "No active license found"}

        now = timezone.now()
        if license_obj.end_at and license_obj.end_at <= now:
            license_obj.status = LicenseStatus.EXPIRED
            license_obj.save(update_fields=["status", "updated_at"])
            return {
                "has_access": False,
                "reason": "License expired",
                "expired_at": license_obj.end_at.isoformat(),
            }

        expires_soon = False
        if license_obj.end_at:
            expires_soon = (license_obj.end_at - now).days <= 7

        # Lấy tên symbol
        symbol_name = None
        try:
            symbol = Symbol.objects.get(id=symbol_id)
            symbol_name = symbol.name
        except Symbol.DoesNotExist:
            pass

        return {
            "has_access": True,
            "license_id": str(license_obj.license_id),
            "symbol_id": symbol_id,
            "symbol_name": symbol_name,
            "start_at": license_obj.start_at.isoformat(),
            "end_at": license_obj.end_at.isoformat() if license_obj.end_at else None,
            "is_lifetime": license_obj.end_at is None,
            "expires_soon": expires_soon,
        }

    def get_user_symbol_licenses(self, user: User, page: int = 1, limit: int = 20) -> Dict[str, object]:
        if page <= 0:
            page = 1
        if limit <= 0:
            limit = 20

        offset = (page - 1) * limit
        qs = PayUserSymbolLicense.objects.filter(user=user).select_related('order').order_by("-created_at")
        total = qs.count()

        # Lấy tất cả symbol_ids để query tên 1 lần
        licenses_list = list(qs[offset : offset + limit])
        symbol_ids = {license_obj.symbol_id for license_obj in licenses_list if license_obj.symbol_id}

        symbol_names = {}
        if symbol_ids:
            symbol_names = {symbol.id: symbol.name for symbol in Symbol.objects.filter(id__in=symbol_ids)}

        # Lấy thông tin order items để lấy giá
        order_ids = {license_obj.order_id for license_obj in licenses_list if license_obj.order_id}
        order_items_map = {}
        if order_ids:
            from ..models import PaySymbolOrderItem
            order_items = PaySymbolOrderItem.objects.filter(order_id__in=order_ids)
            for item in order_items:
                key = (item.order_id, item.symbol_id)
                order_items_map[key] = item

        results: List[Dict[str, object]] = []
        now = timezone.now()
        for license_obj in licenses_list:
            is_active = (
                license_obj.status == LicenseStatus.ACTIVE
                and (license_obj.end_at is None or license_obj.end_at > now)
            )

            # Lấy thông tin từ order item
            order_item = None
            purchase_price = None
            license_days = None
            auto_renew = False

            if license_obj.order_id and license_obj.symbol_id:
                order_item = order_items_map.get((license_obj.order_id, license_obj.symbol_id))
                if order_item:
                    purchase_price = float(order_item.price)
                    license_days = order_item.license_days
                    auto_renew = order_item.auto_renew

            results.append(
                {
                    "license_id": str(license_obj.license_id),
                    "symbol_id": license_obj.symbol_id,
                    "symbol_name": symbol_names.get(license_obj.symbol_id),
                    "status": license_obj.status,
                    "start_at": license_obj.start_at.isoformat(),
                    "end_at": license_obj.end_at.isoformat() if license_obj.end_at else None,
                    "is_lifetime": license_obj.end_at is None,
                    "is_active": is_active,
                    "order_id": str(license_obj.order_id) if license_obj.order_id else None,
                    "created_at": license_obj.created_at.isoformat(),
                    # Thông tin từ order
                    "purchase_price": purchase_price,
                    "license_days": license_days,
                    "auto_renew": auto_renew,
                    "payment_method": license_obj.order.payment_method if license_obj.order else None,
                    "order_total_amount": float(license_obj.order.total_amount) if license_obj.order else None,
                }
            )

        return {
            "results": results,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }

    def get_order_history(
        self,
        user: User,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, object]:
        if page <= 0:
            page = 1
        if limit <= 0:
            limit = 20

        if status is None:
            status_filter = [OrderStatus.PAID]
        else:
            status_filter = [status]

        qs = (
            PaySymbolOrder.objects.filter(user=user, status__in=status_filter)
            .order_by("-created_at")
            .prefetch_related("items")
        )
        total = qs.count()

        offset = (page - 1) * limit
        orders = list(qs[offset : offset + limit])

        symbol_ids = {
            item.symbol_id
            for order in orders
            for item in order.items.all()
            if item.symbol_id
        }
        symbol_names = {}
        if symbol_ids:
            symbol_names = {
                symbol.id: symbol.name for symbol in Symbol.objects.filter(id__in=symbol_ids)
            }

        results = []
        for order in orders:
            items: List[Dict[str, object]] = []
            for item in order.items.all():
                items.append(
                    {
                        "symbol_id": item.symbol_id,
                        "symbol_name": symbol_names.get(item.symbol_id),
                        "price": item.price,
                        "license_days": item.license_days,
                        "metadata": item.metadata or {},
                    }
                )

            results.append(
                {
                    "order_id": str(order.order_id),
                    "total_amount": order.total_amount,
                    "status": order.status,
                    "payment_method": order.payment_method,
                    "description": order.description or "",
                    "items": items,
                    "created_at": order.created_at.isoformat(),
                    "updated_at": order.updated_at.isoformat(),
                }
            )

        return {
            "results": results,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }
