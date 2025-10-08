from decimal import Decimal
from typing import Optional

from ninja import Schema


class SymbolAutoRenewSubscriptionResponse(Schema):
    subscription_id: str
    symbol_id: int
    status: str
    cycle_days: int
    price: Decimal
    payment_method: str
    next_billing_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    consecutive_failures: int
    grace_period_hours: int
    retry_interval_minutes: int
    max_retry_attempts: int
    current_license_id: Optional[str] = None
    last_order_id: Optional[str] = None
    created_at: str
    updated_at: str


class SymbolAutoRenewAttemptResponse(Schema):
    attempt_id: str
    subscription_id: str
    status: str
    fail_reason: Optional[str] = None
    charged_amount: Optional[Decimal] = None
    wallet_balance_snapshot: Optional[Decimal] = None
    order_id: Optional[str] = None
    ran_at: str
