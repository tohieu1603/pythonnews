import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.setting.models import (
    SymbolAutoRenewSubscription,
    SymbolAutoRenewAttempt,
    AutoRenewStatus,
    AutoRenewAttemptStatus,
)
from apps.seapay.models import (
    PaySymbolOrder,
    PayUserSymbolLicense,
    PayWallet,
    PaymentMethod,
)

User = get_user_model()
logger = logging.getLogger("app.autorenew")


class SymbolAutoRenewService:
    """Encapsulates auto-renew subscription orchestration and execution."""

    DEFAULT_CYCLE_DAYS = 30

    def sync_pending_from_order(self, order: PaySymbolOrder) -> List[SymbolAutoRenewSubscription]:
        """Ensure subscriptions exist for order items flagged for auto-renew."""
        subscriptions: List[SymbolAutoRenewSubscription] = []
        items = list(order.items.all())
        if not items:
            return subscriptions

        for item in items:
            if not getattr(item, "auto_renew", False):
                continue

            cycle_days = self._resolve_cycle_days(item)
            price = self._resolve_price(item)

            with transaction.atomic():
                subscription = (
                    SymbolAutoRenewSubscription.objects.select_for_update()
                    .filter(
                        user=order.user,
                        symbol_id=item.symbol_id,
                        status__in=[
                            AutoRenewStatus.PENDING_ACTIVATION,
                            AutoRenewStatus.ACTIVE,
                            AutoRenewStatus.PAUSED,
                        ],
                    )
                    .order_by("created_at")
                    .first()
                )

                if subscription:
                    updates = {
                        "cycle_days": cycle_days,
                        "price": price,
                        "payment_method": order.payment_method,
                        "last_order": order,
                        "metadata": {**(subscription.metadata or {}), "last_enroll_order_id": str(order.order_id)},
                    }
                    if subscription.status != AutoRenewStatus.ACTIVE:
                        updates["status"] = AutoRenewStatus.PENDING_ACTIVATION
                        updates["next_billing_at"] = None
                    for field, value in updates.items():
                        setattr(subscription, field, value)
                    subscription.save(update_fields=list(updates.keys()) + ["updated_at"])
                else:
                    subscription = SymbolAutoRenewSubscription.objects.create(
                        user=order.user,
                        symbol_id=item.symbol_id,
                        status=AutoRenewStatus.PENDING_ACTIVATION,
                        cycle_days=cycle_days,
                        price=price,
                        payment_method=order.payment_method,
                        last_order=order,
                        metadata={
                            "created_from_order_id": str(order.order_id),
                            "initial_cycle_days": cycle_days,
                            "initial_price": str(price),
                        },
                    )
                subscriptions.append(subscription)
        return subscriptions

    def activate_for_order(self, order: PaySymbolOrder) -> List[SymbolAutoRenewSubscription]:
        """Activate or update subscriptions after an order is fully paid."""
        items = list(order.items.all())
        if not items:
            return []

        licenses = {
            lic.symbol_id: lic
            for lic in PayUserSymbolLicense.objects.filter(order=order)
        }
        activated: List[SymbolAutoRenewSubscription] = []
        now = timezone.now()

        for item in items:
            if not getattr(item, "auto_renew", False):
                continue

            cycle_days = self._resolve_cycle_days(item)
            price = self._resolve_price(item)
            license_obj = licenses.get(item.symbol_id)

            with transaction.atomic():
                subscription = (
                    SymbolAutoRenewSubscription.objects.select_for_update()
                    .filter(user=order.user, symbol_id=item.symbol_id)
                    .order_by("-created_at")
                    .first()
                )
                if not subscription:
                    subscription = SymbolAutoRenewSubscription.objects.create(
                        user=order.user,
                        symbol_id=item.symbol_id,
                        status=AutoRenewStatus.PENDING_ACTIVATION,
                        cycle_days=cycle_days,
                        price=price,
                        payment_method=order.payment_method,
                        last_order=order,
                        metadata={
                            "created_from_order_id": str(order.order_id),
                            "initial_cycle_days": cycle_days,
                            "initial_price": str(price),
                        },
                    )

                next_billing_at = None
                status = AutoRenewStatus.ACTIVE
                if license_obj and license_obj.end_at:
                    next_billing_at = license_obj.end_at - timedelta(hours=subscription.grace_period_hours)
                    if next_billing_at <= now:
                        next_billing_at = license_obj.end_at
                else:
                    status = AutoRenewStatus.COMPLETED

                metadata = subscription.metadata or {}
                metadata.update(
                    {
                        "last_activation_order_id": str(order.order_id),
                        "last_activation_at": now.isoformat(),
                    }
                )

                subscription.cycle_days = cycle_days
                subscription.price = price
                subscription.payment_method = order.payment_method
                subscription.last_order = order
                subscription.current_license = license_obj
                subscription.next_billing_at = next_billing_at
                subscription.status = status
                subscription.last_success_at = now
                subscription.consecutive_failures = 0
                subscription.metadata = metadata
                subscription.save(
                    update_fields=[
                        "cycle_days",
                        "price",
                        "payment_method",
                        "last_order",
                        "current_license",
                        "next_billing_at",
                        "status",
                        "last_success_at",
                        "consecutive_failures",
                        "metadata",
                        "updated_at",
                    ]
                )

                if license_obj and license_obj.subscription_id != subscription.subscription_id:
                    license_obj.subscription = subscription
                    license_obj.save(update_fields=["subscription"])

                activated.append(subscription)
        return activated

    def list_user_subscriptions(self, user: User) -> List[Dict]:
        """List subscriptions for the given user with current status."""
        subs = (
            SymbolAutoRenewSubscription.objects.filter(user=user)
            .select_related("current_license", "last_order")
            .order_by("-created_at")
        )
        return [self._serialize_subscription(sub) for sub in subs]

    def pause_subscription(self, subscription_id: str, user: User) -> Dict:
        subscription = self._set_status(subscription_id, user, AutoRenewStatus.PAUSED)
        return self._serialize_subscription(subscription)

    def resume_subscription(self, subscription_id: str, user: User) -> Dict:
        subscription = self._set_status(subscription_id, user, AutoRenewStatus.ACTIVE)
        if subscription.next_billing_at is None and subscription.current_license and subscription.current_license.end_at:
            subscription.next_billing_at = subscription.current_license.end_at
            subscription.save(update_fields=['next_billing_at', 'updated_at'])

        now = timezone.now()
        if subscription.payment_method == PaymentMethod.WALLET:
            wallet_balance: Optional[Decimal] = None
            try:
                wallet = PayWallet.objects.get(user=user)
                wallet_balance = wallet.balance
            except PayWallet.DoesNotExist:
                self._cancel_due_to_insufficient_funds(
                    subscription,
                    reason="Wallet not found",
                    wallet_balance=wallet_balance,
                    timestamp=now,
                )
                subscription.refresh_from_db()
                return self._serialize_subscription(subscription)

            if wallet.balance < subscription.price:
                self._cancel_due_to_insufficient_funds(
                    subscription,
                    reason=f"Insufficient balance: requires {subscription.price}, has {wallet.balance}",
                    wallet_balance=wallet.balance,
                    timestamp=now,
                )
                subscription.refresh_from_db()
                return self._serialize_subscription(subscription)

        return self._serialize_subscription(subscription)

    def cancel_subscription(self, subscription_id: str, user: User) -> Dict:
        subscription = self._set_status(subscription_id, user, AutoRenewStatus.CANCELLED)
        subscription.next_billing_at = None
        subscription.current_license = None
        subscription.save(update_fields=['next_billing_at', 'current_license', 'updated_at'])
        return self._serialize_subscription(subscription)
    def get_subscription_attempts(self, subscription_id: str, user: User, limit: int = 20) -> List[Dict]:
        try:
            subscription = SymbolAutoRenewSubscription.objects.get(subscription_id=subscription_id, user=user)
        except SymbolAutoRenewSubscription.DoesNotExist as exc:
            raise ValueError('Subscription not found') from exc

        attempts = (
            SymbolAutoRenewAttempt.objects.filter(subscription=subscription)
            .select_related('order')
            .order_by('-ran_at')[:limit]
        )
        results: List[Dict] = []
        for attempt in attempts:
            results.append({
                'attempt_id': str(attempt.attempt_id),
                'subscription_id': str(subscription.subscription_id),
                'status': attempt.status,
                'fail_reason': attempt.fail_reason,
                'charged_amount': attempt.charged_amount,
                'wallet_balance_snapshot': attempt.wallet_balance_snapshot,
                'order_id': str(attempt.order_id) if attempt.order_id else None,
                'ran_at': attempt.ran_at.isoformat(),
            })
        return results

    def run_due_subscriptions(self, limit: int = 50) -> Dict[str, int]:
        """Execute auto-renew for subscriptions whose billing date is due."""
        now = timezone.now()
        due_subs = (
            SymbolAutoRenewSubscription.objects.select_related("user")
            .filter(
                status=AutoRenewStatus.ACTIVE,
                next_billing_at__isnull=False,
                next_billing_at__lte=now,
            )
            .order_by("next_billing_at")[:limit]
        )
        processed = success = failed = skipped = 0
        from apps.seapay.services.symbol_purchase_service import SymbolPurchaseService

        purchase_service = SymbolPurchaseService()

        for sub in due_subs:
            processed += 1
            with transaction.atomic():
                sub = SymbolAutoRenewSubscription.objects.select_for_update().get(
                    pk=sub.subscription_id
                )
                wallet_balance: Optional[Decimal] = None
                try:
                    wallet = PayWallet.objects.select_for_update().get(user=sub.user)
                    wallet_balance = wallet.balance
                except PayWallet.DoesNotExist:
                    wallet = None

                if sub.payment_method != PaymentMethod.WALLET:
                    SymbolAutoRenewAttempt.objects.create(
                        subscription=sub,
                        status=AutoRenewAttemptStatus.SKIPPED,
                        fail_reason="Auto-renew currently requires wallet payment",
                        wallet_balance_snapshot=wallet_balance,
                    )
                    sub.last_attempt_at = now
                    sub.next_billing_at = now + timedelta(minutes=sub.retry_interval_minutes)
                    sub.save(update_fields=["last_attempt_at", "next_billing_at", "updated_at"])
                    skipped += 1
                    continue

                if wallet is None:
                    self._cancel_due_to_insufficient_funds(
                        sub,
                        reason="Wallet not found",
                        wallet_balance=wallet_balance,
                        timestamp=now,
                    )
                    failed += 1
                    continue

                if wallet.balance < sub.price:
                    self._cancel_due_to_insufficient_funds(
                        sub,
                        reason=f"Insufficient balance: requires {sub.price}, has {wallet.balance}",
                        wallet_balance=wallet.balance,
                        timestamp=now,
                    )
                    failed += 1
                    continue

                try:
                    order = purchase_service.create_symbol_order(
                        user=sub.user,
                        items=[
                            {
                                "symbol_id": sub.symbol_id,
                                "price": sub.price,
                                "license_days": sub.cycle_days,
                                "auto_renew": True,
                                "auto_renew_price": sub.price,
                                "auto_renew_cycle_days": sub.cycle_days,
                            }
                        ],
                        payment_method=PaymentMethod.WALLET,
                        description=f"Auto-renew for symbol {sub.symbol_id}",
                    )
                    SymbolAutoRenewAttempt.objects.create(
                        subscription=sub,
                        order=order,
                        status=AutoRenewAttemptStatus.SUCCESS,
                        charged_amount=sub.price,
                        wallet_balance_snapshot=wallet.balance,
                    )
                    success += 1
                except Exception as exc:
                    message = str(exc)
                    if "insufficient" in message.lower():
                        self._cancel_due_to_insufficient_funds(
                            sub,
                            reason=message,
                            wallet_balance=wallet.balance if wallet else None,
                            timestamp=now,
                        )
                    else:
                        self._handle_failure(
                            sub,
                            reason=message,
                            wallet_balance=wallet.balance if wallet else None,
                            timestamp=now,
                        )
                    failed += 1
        return {
            "processed": processed,
            "success": success,
            "failed": failed,
            "skipped": skipped,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_cycle_days(self, item) -> int:
        if getattr(item, "cycle_days_override", None):
            return int(item.cycle_days_override)
        if getattr(item, "license_days", None):
            return int(item.license_days)
        return self.DEFAULT_CYCLE_DAYS

    def _resolve_price(self, item) -> Decimal:
        if getattr(item, "auto_renew_price", None):
            return Decimal(item.auto_renew_price)
        return Decimal(item.price)

    def _set_status(
        self, subscription_id: str, user: User, status: str
    ) -> SymbolAutoRenewSubscription:
        try:
            subscription = SymbolAutoRenewSubscription.objects.select_for_update().get(
                subscription_id=subscription_id,
                user=user,
            )
        except SymbolAutoRenewSubscription.DoesNotExist as exc:
            raise ValueError("Subscription not found") from exc
        subscription.status = status
        subscription.updated_at = timezone.now()
        subscription.save(update_fields=['status', 'updated_at'])
        return subscription

    def _serialize_subscription(self, sub: SymbolAutoRenewSubscription) -> Dict:
        return {
            'subscription_id': str(sub.subscription_id),
            'symbol_id': sub.symbol_id,
            'status': sub.status,
            'cycle_days': sub.cycle_days,
            'price': sub.price,
            'payment_method': sub.payment_method,
            'next_billing_at': sub.next_billing_at.isoformat() if sub.next_billing_at else None,
            'last_success_at': sub.last_success_at.isoformat() if sub.last_success_at else None,
            'last_attempt_at': sub.last_attempt_at.isoformat() if sub.last_attempt_at else None,
            'consecutive_failures': sub.consecutive_failures,
            'grace_period_hours': sub.grace_period_hours,
            'retry_interval_minutes': sub.retry_interval_minutes,
            'max_retry_attempts': sub.max_retry_attempts,
            'current_license_id': str(sub.current_license_id) if sub.current_license_id else None,
            'last_order_id': str(sub.last_order_id) if sub.last_order_id else None,
            'created_at': sub.created_at.isoformat(),
            'updated_at': sub.updated_at.isoformat(),
        }

    def _cancel_due_to_insufficient_funds(
        self,
        subscription: SymbolAutoRenewSubscription,
        reason: str,
        wallet_balance: Optional[Decimal],
        timestamp,
    ) -> None:
        SymbolAutoRenewAttempt.objects.create(
            subscription=subscription,
            status=AutoRenewAttemptStatus.FAILED,
            fail_reason=reason,
            wallet_balance_snapshot=wallet_balance,
        )
        subscription.status = AutoRenewStatus.CANCELLED
        subscription.next_billing_at = None
        subscription.last_attempt_at = timestamp
        subscription.consecutive_failures = 0
        subscription.save(
            update_fields=[
                "status",
                "next_billing_at",
                "last_attempt_at",
                "consecutive_failures",
                "updated_at",
            ]
        )

    def _handle_failure(
        self,
        subscription: SymbolAutoRenewSubscription,
        reason: str,
        wallet_balance: Optional[Decimal],
        timestamp,
    ) -> None:
        SymbolAutoRenewAttempt.objects.create(
            subscription=subscription,
            status=AutoRenewAttemptStatus.FAILED,
            fail_reason=reason,
            wallet_balance_snapshot=wallet_balance,
        )
        subscription.consecutive_failures += 1
        subscription.last_attempt_at = timestamp
        if subscription.consecutive_failures >= subscription.max_retry_attempts:
            subscription.status = AutoRenewStatus.SUSPENDED
            subscription.next_billing_at = None
        else:
            subscription.next_billing_at = timestamp + timedelta(minutes=subscription.retry_interval_minutes)
        subscription.save(
            update_fields=[
                "consecutive_failures",
                "last_attempt_at",
                "status",
                "next_billing_at",
                "updated_at",
            ]
        )

