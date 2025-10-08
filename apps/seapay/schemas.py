from ninja import Schema
from decimal import Decimal
from typing import Optional, List
from datetime import datetime


class UserResponse(Schema):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    date_joined: datetime


# Request DTOs
class CreatePaymentIntentRequest(Schema):
    purpose: str 
    amount: Decimal
    currency: str = "VND"
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None
    expires_in_minutes: int = 60
    metadata: dict = {}


class PaymentCallbackRequest(Schema):
    gateway: str
    transactionDate: str
    accountNumber: str
    subAccount: str
    code: Optional[str] = None
    content: str 
    transferType: str
    description: Optional[str] = None
    transferAmount: Decimal
    referenceCode: str
    accumulated: int
    id: int


class CreateLegacyOrderRequest(Schema):
    order_id: str
    amount: Decimal
    description: str = ""


class CreatePaymentIntentResponse(Schema):
    intent_id: str
    order_code: str
    qr_code_url: str
    transfer_content: str
    amount: Decimal
    status: str
    expires_at: str


class PaymentIntentDetailResponse(Schema):
    intent_id: str
    order_code: str
    amount: float
    status: str
    purpose: str
    expires_at: Optional[str]
    is_expired: bool
    created_at: str
    updated_at: str


class WalletResponse(Schema):
    wallet_id: str
    balance: float
    currency: str
    status: str
    created_at: str
    updated_at: str


class PaymentCallbackResponse(Schema):
    message: str
    intent_id: Optional[str] = None
    order_code: Optional[str] = None
    status: Optional[str] = None
    wallet_balance: Optional[float] = None
    transfer_type: Optional[str] = None


class CreateLegacyOrderResponse(Schema):
    order_id: str
    qr_code_url: str
    transfer_content: str
    status: str


class FallbackCallbackResponse(Schema):
    message: str
    path: str
    method: Optional[str] = None
    params: Optional[dict] = None

class PaymentIntentOut(Schema):
    id: str
    order_code: str
    reference_code: Optional[str]
    amount: Decimal
    status: str
    purpose: str
    provider: str
    created_at: datetime
    user_id: int 


class PaginatedPaymentIntent(Schema):
    total: int
    page: int
    page_size: int
    user: UserResponse  
    results: List[PaymentIntentOut]


# Wallet Topup Schemas
class CreateWalletTopupRequest(Schema):
    amount: Decimal
    currency: str = "VND"
    bank_code: str = "BIDV"
    expires_in_minutes: int = 60


class CreateWalletTopupResponse(Schema):
    intent_id: str
    order_code: str
    amount: Decimal
    currency: str
    status: str
    qr_image_url: str
    qr_code_url: str
    account_number: str
    account_name: str
    transfer_content: str
    bank_code: str
    expires_at: str
    message: str


class WalletTopupStatusResponse(Schema):
    intent_id: str
    order_code: str
    amount: Decimal
    status: str
    is_expired: bool
    qr_image_url: str
    account_number: str
    account_name: str
    transfer_content: str
    bank_code: str
    expires_at: str
    payment_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    balance_before: Optional[Decimal] = None
    balance_after: Optional[Decimal] = None
    completed_at: Optional[str] = None
    message: str


class SepayWebhookRequest(Schema):
    id: int
    gateway: str
    transactionDate: str
    accountNumber: str
    subAccount: Optional[str] = None
    code: Optional[str] = None
    content: str
    transferType: str
    description: Optional[str] = None
    transferAmount: Decimal
    referenceCode: str
    accumulated: Optional[int] = None


class SepayWebhookResponse(Schema):
    status: str
    message: str
    payment_id: Optional[str] = None
    processed_at: str



class SymbolOrderItemRequest(Schema):
    symbol_id: int
    price: Decimal
    license_days: Optional[int] = None
    metadata: Optional[dict] = {}
    auto_renew: bool = False
    auto_renew_price: Optional[Decimal] = None
    auto_renew_cycle_days: Optional[int] = None


class CreateSymbolOrderRequest(Schema):
    items: List[SymbolOrderItemRequest]
    payment_method: str = "wallet"  # wallet | sepay_transfer
    description: Optional[str] = ""


class SymbolOrderItemResponse(Schema):
    symbol_id: int
    price: Decimal
    license_days: Optional[int]
    symbol_name: Optional[str] = None
    metadata: dict
    auto_renew: bool = False
    auto_renew_price: Optional[Decimal] = None
    auto_renew_cycle_days: Optional[int] = None


class CreateSymbolOrderResponse(Schema):
    order_id: str
    total_amount: Decimal
    status: str
    payment_method: str
    items: List[SymbolOrderItemResponse]
    created_at: str
    message: str
    payment_intent_id: Optional[str] = None
    qr_code_url: Optional[str] = None
    deep_link: Optional[str] = None
    # Fields cho trường hợp thiếu tiền
    insufficient_balance: Optional[bool] = False
    wallet_balance: Optional[Decimal] = None
    shortage: Optional[Decimal] = None


class ProcessWalletPaymentResponse(Schema):
    success: bool
    message: str
    order_id: str
    amount_charged: Decimal
    wallet_balance_after: Decimal
    licenses_created: int
    subscriptions_updated: int | None = 0


class CreateSepayPaymentResponse(Schema):
    intent_id: str
    order_code: str
    amount: Decimal
    currency: str
    expires_at: str
    qr_code_url: str
    message: str


class SymbolAccessCheckResponse(Schema):
    has_access: bool
    license_id: Optional[str] = None
    symbol_id: Optional[int] = None
    symbol_name: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    is_lifetime: Optional[bool] = False
    expires_soon: Optional[bool] = False
    reason: Optional[str] = None
    expired_at: Optional[str] = None


class UserSymbolLicenseResponse(Schema):
    license_id: str
    symbol_id: int
    symbol_name: Optional[str] = None
    status: str
    start_at: str
    end_at: Optional[str]
    is_lifetime: bool
    is_active: bool
    order_id: Optional[str]
    created_at: str
    # Thông tin từ order
    purchase_price: Optional[float] = None
    license_days: Optional[int] = None
    auto_renew: Optional[bool] = False
    payment_method: Optional[str] = None
    order_total_amount: Optional[float] = None


class SymbolOrderHistoryResponse(Schema):
    order_id: str
    total_amount: Decimal
    status: str
    payment_method: str
    description: Optional[str] = None
    created_at: str
    updated_at: str
    items: List[SymbolOrderItemResponse]


class PaginatedSymbolOrderHistory(Schema):
    results: List[SymbolOrderHistoryResponse]
    total: int
    page: int
    limit: int
    total_pages: int
