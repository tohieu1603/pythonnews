import logging
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from ninja.errors import HttpError

from apps.seapay.models import (
    IntentPurpose,
    OrderStatus,
    PayPayment,
    PayPaymentIntent,
    PayWallet,
    PaymentStatus,
)
from apps.seapay.repositories.payment_repository import PaymentRepository

User = get_user_model()
logger = logging.getLogger(__name__)


class PaymentService:
    """Business logic for SePay payment intents and webhook processing."""

    def __init__(
        self,
        repository: Optional[PaymentRepository] = None,
        http_client=requests,
    ) -> None:
        self.repository = repository or PaymentRepository()
        self._http_client = http_client

    def create_payment_intent(
        self,
        user: User,
        purpose: str,
        amount: Decimal,
        currency: str = "VND",
        expires_in_minutes: int = 60,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PayPaymentIntent:
        """Create a payment intent for the given user and purpose."""

        valid_purposes = {
            IntentPurpose.WALLET_TOPUP,
            IntentPurpose.ORDER_PAYMENT,
            IntentPurpose.SYMBOL_PURCHASE,
            "withdraw",
        }
        if purpose not in valid_purposes:
            raise ValueError(f"Invalid purpose. Must be one of: {sorted(valid_purposes)}")

        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            raise ValueError("Amount must be a valid decimal number") from None

        if amount <= 0:
            raise ValueError("Amount must be greater than 0")

        wallet, _ = self.repository.get_or_create_wallet(user, currency)
        if not wallet.is_active:
            raise HttpError(400, "Wallet is suspended")

        order_code = f"PAY_{uuid.uuid4().hex[:8].upper()}_{int(timezone.now().timestamp())}"
        expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)

        intent = self.repository.create_payment_intent(
            user=user,
            wallet=wallet,
            provider="sepay",
            purpose=purpose,
            amount=amount,
            order_code=order_code,
            expires_at=expires_at,
            return_url=return_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
        )
        return intent

    @staticmethod
    def generate_qr_code_url(order_code: str, amount: Decimal) -> str:
        """Generate a SePay QR code URL for the given order code and amount."""
        return (
            "https://qr.sepay.vn/img?acc=96247CISI1"
            f"&bank=BIDV&amount={int(amount)}&des={order_code}&template=compact"
        )

    def process_callback(
        self,
        content: str,
        amount: Decimal,
        transfer_type: str,
        reference_code: str,
    ) -> Dict[str, Any]:
        """Process a callback payload received from SePay."""

        if not content:
            raise HttpError(400, "Missing content (order_code)")

        if transfer_type != "in":
            return {
                "message": "Ignored - not an incoming transfer",
                "transfer_type": transfer_type,
            }

        intent = self._find_payment_intent_by_order_code(content)
        if not intent:
            raise HttpError(404, f"Payment intent not found for order_code: {content}")

        amount = Decimal(str(amount))
        if amount != intent.amount:
            raise HttpError(
                400,
                f"Amount mismatch. Expected: {intent.amount}, Received: {amount}",
            )

        if intent.status not in {
            PaymentStatus.REQUIRES_PAYMENT_METHOD,
            PaymentStatus.PROCESSING,
        }:
            if intent.status == PaymentStatus.SUCCEEDED and intent.purpose == IntentPurpose.ORDER_PAYMENT:
                self._ensure_order_status_synced(intent)
            return {
                "message": "Already processed",
                "intent_id": str(intent.intent_id),
                "status": intent.status,
            }

        if intent.is_expired():
            self.repository.update_payment_intent_status(intent, PaymentStatus.EXPIRED)
            raise HttpError(400, "Payment intent has expired")

        return self._process_successful_payment(intent, reference_code)

    def _find_payment_intent_by_order_code(self, content: str) -> Optional[PayPaymentIntent]:
        content = content.strip()
        intent = self.repository.get_payment_intent_by_order_code(content)
        if intent:
            return intent

        if content.startswith("PAY") and len(content) > 11:
            reformatted = f"PAY_{content[3:11]}_{content[11:]}"
            intent = self.repository.get_payment_intent_by_order_code(reformatted)
            if intent:
                logger.debug("Resolved formatted order code %s -> %s", content, reformatted)
        return intent

    def _process_successful_payment(
        self,
        intent: PayPaymentIntent,
        reference_code: Optional[str],
    ) -> Dict[str, Any]:
        self.repository.update_payment_intent_status(intent, PaymentStatus.SUCCEEDED, reference_code)

        if intent.purpose == IntentPurpose.WALLET_TOPUP:
            wallet = self.repository.get_wallet_by_user(intent.user)
            if not wallet:
                wallet, _ = self.repository.get_or_create_wallet(intent.user)
            self.repository.update_wallet_balance(wallet, intent.amount)
            logger.info("Wallet %s credited with %s", wallet.id, intent.amount)
        elif intent.purpose in {IntentPurpose.ORDER_PAYMENT, IntentPurpose.SYMBOL_PURCHASE}:
            self._process_symbol_order_payment(intent)

        wallet_balance = None
        if intent.user:
            wallet = self.repository.get_wallet_by_user(intent.user)
            if wallet:
                wallet_balance = float(wallet.balance)

        return {
            "message": "OK",
            "intent_id": str(intent.intent_id),
            "order_code": intent.order_code,
            "status": intent.status,
            "wallet_balance": wallet_balance,
        }

    def _ensure_payment_record(
        self,
        intent_id: str,
        amount: Decimal,
        reference_code: Optional[str],
    ) -> Optional[PayPayment]:
        intent = PayPaymentIntent.objects.filter(intent_id=intent_id).first()
        if not intent:
            return None

        payment = PayPayment.objects.filter(intent=intent).first()
        if payment:
            updated_fields: List[str] = []
            if payment.status != PaymentStatus.SUCCEEDED:
                payment.status = PaymentStatus.SUCCEEDED
                updated_fields.append("status")
            if reference_code and not payment.provider_payment_id:
                payment.provider_payment_id = reference_code
                updated_fields.append("provider_payment_id")
            if reference_code:
                metadata = payment.metadata or {}
                if metadata.get("reference_code") != reference_code:
                    metadata["reference_code"] = reference_code
                    payment.metadata = metadata
                    updated_fields.append("metadata")
            if updated_fields:
                updated_fields.append("updated_at")
                payment.save(update_fields=updated_fields)
            return payment

        metadata = {"reference_code": reference_code} if reference_code else {}
        return PayPayment.objects.create(
            user=intent.user,
            order=None,
            intent=intent,
            amount=amount,
            status=PaymentStatus.SUCCEEDED,
            provider_payment_id=reference_code or intent.order_code,
            message="Processed via SePay webhook",
            metadata=metadata,
        )

    def process_sepay_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = (payload or {}).get("content") or payload.get("referenceCode") or payload.get("orderCode")
        if not content:
            return {"success": False, "message": "Missing content"}

        try:
            amount = Decimal(str(payload.get("transferAmount", 0)))
        except (InvalidOperation, TypeError, ValueError):
            return {"success": False, "message": "Invalid amount"}

        transfer_type = payload.get("transferType", "")
        reference_code = payload.get("referenceCode") or payload.get("content") or ""

        intent_lookup = None
        if content and not content.startswith("PAY_"):
            intent_lookup = PayPaymentIntent.objects.filter(reference_code=content).first()
        if not intent_lookup and reference_code:
            intent_lookup = PayPaymentIntent.objects.filter(reference_code=reference_code).first()
        if intent_lookup:
            content = intent_lookup.order_code

        try:
            result = self.process_callback(
                content=content,
                amount=amount,
                transfer_type=transfer_type,
                reference_code=reference_code,
            )
        except HttpError as exc:
            detail = getattr(exc, "detail", str(exc))
            return {"success": False, "message": str(detail)}
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unhandled error processing SePay webhook: %s", exc)
            return {"success": False, "message": str(exc)}

        payment = None
        intent_id = result.get("intent_id")
        if intent_id:
            payment = self._ensure_payment_record(intent_id, amount, reference_code)

        return {
            "success": True,
            "message": result.get("message", "OK"),
            "intent_id": intent_id,
            "status": result.get("status"),
            "order_code": result.get("order_code"),
            "wallet_balance": result.get("wallet_balance"),
            "payment_id": str(payment.payment_id) if payment else None,
        }

    def _process_symbol_order_payment(self, intent: PayPaymentIntent) -> None:
        from apps.seapay.models import PaySymbolOrder

        order = PaySymbolOrder.objects.filter(payment_intent_id=intent.intent_id).first()
        if not order:
            logger.warning("No symbol order found for payment intent %s", intent.intent_id)
            return

        if order.status == OrderStatus.PAID:
            return

        order.status = OrderStatus.PAID
        order.save(update_fields=["status", "updated_at"])
        self._create_symbol_licenses(order)
        logger.info("Symbol order %s marked as paid", order.order_id)

    def _create_symbol_licenses(self, order) -> None:
        from apps.seapay.models import PayUserSymbolLicense

        now = timezone.now()
        for item in order.items.all():
            end_at = None
            if item.license_days:
                end_at = now + timezone.timedelta(days=item.license_days)
            PayUserSymbolLicense.objects.create(
                user=order.user,
                symbol_id=item.symbol_id,
                order=order,
                start_at=now,
                end_at=end_at,
                status="active",
            )

    def _ensure_order_status_synced(self, intent: PayPaymentIntent) -> None:
        from apps.seapay.models import PaySymbolOrder

        order = PaySymbolOrder.objects.filter(payment_intent_id=intent.intent_id).first()
        if not order:
            logger.warning("No order found for intent %s", intent.intent_id)
            return
        if order.status == OrderStatus.PAID:
            return
        logger.info("Syncing order %s status with succeeded intent", order.order_id)
        self._process_symbol_order_payment(intent)

    def get_payment_intent(self, intent_id: str, user: User) -> PayPaymentIntent:
        intent = self.repository.get_payment_intent_by_id(intent_id, user)
        if not intent:
            raise HttpError(404, "Payment intent not found")
        return intent

    def get_or_create_wallet(self, user: User) -> PayWallet:
        wallet = self.repository.get_wallet_by_user(user)
        if not wallet:
            wallet, _ = self.repository.get_or_create_wallet(user)
        return wallet

    def create_legacy_order(
        self,
        order_id: str,
        amount: Decimal,
        description: str = "",
    ) -> Dict[str, Any]:
        order, created = self.repository.get_or_create_legacy_order(order_id, amount, description)
        if not created:
            raise HttpError(400, f"Order {order_id} already exists")

        transfer_content = f"SEPAY_{order_id}"
        qr_code_url = self.generate_qr_code_url(transfer_content, amount)
        return {
            "order_id": str(order.id),
            "qr_code_url": qr_code_url,
            "transfer_content": transfer_content,
            "status": order.status,
        }

    def get_user_wallet(self, user: User) -> PayWallet:
        wallet, _ = self.repository.get_or_create_wallet(user)
        return wallet

    def list_user_payment_intents(self, user: User) -> List[PayPaymentIntent]:
        return self.repository.get_payment_intents_by_user(user)[1]

    def get_paginated_payment_intents(
        self,
        user: User,
        page: int = 1,
        limit: int = 10,
        search: Optional[str] = None,
        status: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        page = page or 1
        limit = limit or 10
        total, items = self.repository.get_payment_intents_by_user(
            user,
            page,
            limit,
            search,
            status,
            purpose,
        )
        return {
            "total": total,
            "results": items,
            "page": page,
            "page_size": limit,
        }
