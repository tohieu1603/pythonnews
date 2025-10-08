from __future__ import annotations

from decimal import Decimal
from typing import Optional, Dict, Any

from django.db import transaction
from django.contrib.auth import get_user_model

from apps.seapay.models import PayWallet, PayWalletLedger, WalletTxType

User = get_user_model()


class WalletService:
    """Utility helpers around PayWallet and its ledger."""

    DEFAULT_CURRENCY = "VND"

    def get_or_create_wallet(
        self,
        user: User,
        currency: str = DEFAULT_CURRENCY,
        status: str = "active",
    ) -> PayWallet:
        wallet, created = PayWallet.objects.get_or_create(
            user=user,
            defaults={
                "currency": currency,
                "status": status,
            },
        )

        if wallet.currency != currency:
            # Keep the existing wallet but warn via metadata to avoid silent currency mix.
            # For now we simply return the wallet to preserve backward compatibility.
            pass

        if status and wallet.status != status and created:
            wallet.status = status
            wallet.save(update_fields=["status", "updated_at"])

        return wallet

    def credit(
        self,
        wallet: PayWallet,
        amount: Decimal,
        tx_type: str,
        note: str = "",
        order: Optional[Any] = None,
        payment: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PayWalletLedger:
        if amount <= 0:
            raise ValueError("Credit amount must be positive")

        if tx_type not in WalletTxType.values:
            raise ValueError(f"Invalid tx_type: {tx_type}")

        metadata = metadata or {}

        with transaction.atomic():
            wallet.refresh_from_db()
            balance_before = wallet.balance
            balance_after = balance_before + amount

            ledger_entry = PayWalletLedger.objects.create(
                wallet=wallet,
                tx_type=tx_type,
                amount=amount,
                is_credit=True,
                balance_before=balance_before,
                balance_after=balance_after,
                note=note,
                order=order,
                payment=payment,
                metadata=metadata,
            )

            wallet.balance = balance_after
            wallet.save(update_fields=["balance", "updated_at"])

        return ledger_entry

    def debit(
        self,
        wallet: PayWallet,
        amount: Decimal,
        tx_type: str,
        note: str = "",
        order: Optional[Any] = None,
        payment: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PayWalletLedger:
        if amount <= 0:
            raise ValueError("Debit amount must be positive")

        if tx_type not in WalletTxType.values:
            raise ValueError(f"Invalid tx_type: {tx_type}")

        metadata = metadata or {}

        with transaction.atomic():
            wallet.refresh_from_db()
            if wallet.balance < amount:
                raise ValueError("Insufficient balance")

            balance_before = wallet.balance
            balance_after = balance_before - amount

            ledger_entry = PayWalletLedger.objects.create(
                wallet=wallet,
                tx_type=tx_type,
                amount=amount,
                is_credit=False,
                balance_before=balance_before,
                balance_after=balance_after,
                note=note,
                order=order,
                payment=payment,
                metadata=metadata,
            )

            wallet.balance = balance_after
            wallet.save(update_fields=["balance", "updated_at"])

        return ledger_entry


