import logging
from decimal import Decimal
from typing import List, Optional

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError

from core.jwt_auth import JWTAuth

from apps.seapay.models import OrderStatus, PaymentStatus, PaySymbolOrder
from apps.seapay.schemas import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    PaymentIntentDetailResponse,
    WalletResponse,
    PaymentCallbackResponse,
    FallbackCallbackResponse,
    PaymentIntentOut,
    PaginatedPaymentIntent,
    UserResponse,
    CreateWalletTopupRequest,
    CreateWalletTopupResponse,
    WalletTopupStatusResponse,
    SepayWebhookRequest,
    SepayWebhookResponse,
    CreateSymbolOrderRequest,
    CreateSymbolOrderResponse,
    ProcessWalletPaymentResponse,
    CreateSepayPaymentResponse,
    SymbolAccessCheckResponse,
    SymbolOrderItemResponse,
    UserSymbolLicenseResponse,
    PaginatedSymbolOrderHistory,
)
from apps.seapay.services.payment_service import PaymentService
from apps.seapay.services.wallet_topup_service import WalletTopupService
from apps.seapay.services.symbol_purchase_service import SymbolPurchaseService
from apps.stock.models import Symbol

logger = logging.getLogger(__name__)

router = Router()
payment_service = PaymentService()
topup_service = WalletTopupService()
symbol_purchase_service = SymbolPurchaseService()


@router.post("/create-intent", response=CreatePaymentIntentResponse, auth=JWTAuth())
def create_payment_intent(request: HttpRequest, data: CreatePaymentIntentRequest):
    user = request.auth
    intent = payment_service.create_payment_intent(
        user=user,
        purpose=data.purpose,
        amount=data.amount,
        currency=data.currency,
        expires_in_minutes=data.expires_in_minutes,
        return_url=data.return_url,
        cancel_url=data.cancel_url,
        metadata=data.metadata,
    )
    qr_code_url = payment_service.generate_qr_code_url(intent.order_code, intent.amount)
    return CreatePaymentIntentResponse(
        intent_id=str(intent.intent_id),
        order_code=intent.order_code,
        qr_code_url=qr_code_url,
        transfer_content=intent.order_code,
        amount=intent.amount,
        status=intent.status,
        expires_at=intent.expires_at.isoformat(),
    )


@router.post("/webhook/", response=SepayWebhookResponse)
def sepay_webhook(request: HttpRequest, payload: SepayWebhookRequest):
    result = payment_service.process_sepay_webhook(payload.dict())
    status = "success" if result.get("success") else "error"
    return SepayWebhookResponse(
        status=status,
        message=result.get("message", ""),
        payment_id=result.get("payment_id"),
        processed_at=timezone.now().isoformat(),
    )


@router.post("/callback")
@router.get("/callback")
def sepay_callback(request: HttpRequest):
    """Fallback callback endpoint kept for backwards compatibility."""
    logger.info("Received callback at %s with method %s", request.path, request.method)

    payload: Optional[dict] = None
    try:
        if request.body:
            payload = request.json()
    except Exception:
        payload = None

    if not payload and request.POST:
        payload = request.POST.dict()

    if not payload and request.GET:
        payload = request.GET.dict()

    if not payload:
        return PaymentCallbackResponse(message="Could not parse request data")

    try:
        if payload.get("content", "").startswith("TOPUP"):
            result = topup_service.process_webhook_event(payload)
        else:
            result = payment_service.process_callback(
                content=payload.get("content", ""),
                amount=Decimal(str(payload.get("transferAmount", 0))),
                transfer_type=payload.get("transferType", ""),
                reference_code=payload.get("referenceCode", ""),
            )
        return PaymentCallbackResponse(**result)
    except Exception as exc: 
        logger.exception("Callback processing failed: %s", exc)
        return PaymentCallbackResponse(message=f"Callback processing failed: {exc}")


@router.get("/intent/{intent_id}", response=PaymentIntentDetailResponse, auth=JWTAuth())
def get_payment_intent(request: HttpRequest, intent_id: str):
    user = request.auth
    intent = payment_service.get_payment_intent(intent_id, user)
    return PaymentIntentDetailResponse(
        intent_id=str(intent.intent_id),
        order_code=intent.order_code,
        amount=float(intent.amount),
        status=intent.status,
        purpose=intent.purpose,
        expires_at=intent.expires_at.isoformat() if intent.expires_at else None,
        is_expired=intent.is_expired(),
        created_at=intent.created_at.isoformat(),
        updated_at=intent.updated_at.isoformat(),
    )


@router.get("/wallet/", response=WalletResponse, auth=JWTAuth())
@router.get("/wallet", response=WalletResponse, auth=JWTAuth())
def get_wallet(request: HttpRequest):
    wallet = payment_service.get_or_create_wallet(request.auth)
    return WalletResponse(
        wallet_id=str(wallet.id),
        balance=float(wallet.balance),
        currency=wallet.currency,
        status=wallet.status,
        created_at=wallet.created_at.isoformat(),
        updated_at=wallet.updated_at.isoformat(),
    )


@router.get("/payments/user", response=PaginatedPaymentIntent, auth=JWTAuth())
def list_user_payments(
    request: HttpRequest,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[str] = None,
    purpose: Optional[str] = None,
):
    user = request.auth

    valid_statuses = {choice for choice, _ in PaymentStatus.choices}
    resolved_status = status.strip() if isinstance(status, str) else None
    if not resolved_status:
        resolved_status = PaymentStatus.SUCCEEDED
    elif resolved_status not in valid_statuses:
        raise HttpError(400, "Invalid status")

    result = payment_service.get_paginated_payment_intents(
        user=user,
        page=page,
        limit=limit,
        search=search,
        status=resolved_status,
        purpose=purpose,
    )

    intents: List[PaymentIntentOut] = []
    for intent in result["results"]:
        metadata = intent.metadata or {}
        intents.append(
            PaymentIntentOut(
                id=str(intent.intent_id),
                order_code=intent.order_code,
                reference_code=metadata.get("reference_code"),
                amount=intent.amount,
                status=intent.status,
                purpose=intent.purpose,
                provider=metadata.get("provider", "sepay"),
                created_at=intent.created_at,
                user_id=intent.user_id,
            )
        )

    return PaginatedPaymentIntent(
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            date_joined=user.date_joined,
        ),
        results=intents,
    )


@router.post("/wallet/topup/", response=CreateWalletTopupResponse, auth=JWTAuth())
def create_wallet_topup(request: HttpRequest, data: CreateWalletTopupRequest):
    if data.amount <= 0:
        raise HttpError(400, "Amount must be greater than 0")
    if data.amount > Decimal("100000000"):
        raise HttpError(400, "Amount exceeds maximum limit")

    try:
        intent = topup_service.create_topup_intent(
            user=request.auth,
            amount=data.amount,
            currency=data.currency,
            expires_in_minutes=data.expires_in_minutes,
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT"),
            },
        )
        attempt = topup_service.create_payment_attempt(intent=intent, bank_code=data.bank_code)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception as exc: 
        raise HttpError(500, f"Failed to create topup request: {exc}")

    return CreateWalletTopupResponse(
        intent_id=str(intent.intent_id),
        order_code=intent.order_code,
        amount=intent.amount,
        currency="VND",
        status=intent.status,
        qr_image_url=attempt.qr_image_url or "",
        qr_code_url=attempt.qr_image_url or "",
        account_number=attempt.account_number or "",
        account_name=attempt.account_name or "",
        transfer_content=attempt.transfer_content or "",
        bank_code=attempt.bank_code or "",
        expires_at=intent.expires_at.isoformat() if intent.expires_at else "",
        message="Topup request created successfully. Please scan the QR code to complete payment.",
    )


@router.get("/wallet/topup-history/", response=List[WalletTopupStatusResponse], auth=JWTAuth())
def get_wallet_topup_history(request: HttpRequest):
    return []


@router.get("/wallet/topup/{intent_id}/status", response=WalletTopupStatusResponse, auth=JWTAuth())
def get_topup_status(request: HttpRequest, intent_id: str):
    try:
        status_data = topup_service.get_topup_status(intent_id, request.auth)
    except ValueError as exc:
        raise HttpError(404, str(exc))
    except Exception as exc:  
        raise HttpError(500, f"Failed to get topup status: {exc}")

    intent = status_data["intent"]
    attempt = status_data.get("attempt")
    payment = status_data.get("payment")
    ledger = status_data.get("ledger")

    return WalletTopupStatusResponse(
        intent_id=intent["id"],
        order_code=intent["order_code"],
        amount=Decimal(str(intent["amount"])),
        status=intent["status"],
        is_expired=intent["is_expired"],
        qr_image_url=attempt["qr_image_url"] if attempt else "",
        account_number=attempt["account_number"] if attempt else "",
        account_name=attempt["account_name"] if attempt else "",
        transfer_content=attempt["transfer_content"] if attempt else "",
        bank_code=attempt["bank_code"] if attempt else "",
        expires_at=intent["expires_at"] or "",
        payment_id=payment["id"] if payment else None,
        provider_payment_id=payment["provider_payment_id"] if payment else None,
        balance_before=ledger["balance_before"] if ledger else None,
        balance_after=ledger["balance_after"] if ledger else None,
        completed_at=payment["created_at"] if payment else None,
        message=f"Topup status: {intent['status']}",
    )


@router.post("/symbol/orders/", response=CreateSymbolOrderResponse, auth=JWTAuth())
def create_symbol_order_endpoint(request: HttpRequest, data: CreateSymbolOrderRequest):
    user = request.auth
    try:
        items_payload = [item.dict() for item in data.items]
        result = symbol_purchase_service.create_symbol_order(
            user=user,
            items=items_payload,
            payment_method=data.payment_method,
            description=data.description or None,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception as exc: 
        raise HttpError(500, f"Failed to create symbol order: {exc}")

    if isinstance(result, PaySymbolOrder):
        order = result
        payment_intent = getattr(order, "payment_intent", None)
        message = "Order processed successfully."
        insufficient_balance = False
        wallet_balance = None
        shortage = None
    else:
        order = result.get("order")
        payment_intent = result.get("payment_intent")
        insufficient_balance = result.get("insufficient_balance", False)
        wallet_balance = result.get("wallet_balance")
        shortage = result.get("shortage")
        message = result.get("message", "Order created successfully. Complete payment via SePay.")

    items_qs = list(order.items.all())
    symbol_ids = {item.symbol_id for item in items_qs if item.symbol_id}
    symbol_names = {}
    if symbol_ids:
        symbol_names = {symbol.id: symbol.name for symbol in Symbol.objects.filter(id__in=symbol_ids)}

    response_items: List[SymbolOrderItemResponse] = []
    for item in items_qs:
        response_items.append(
            SymbolOrderItemResponse(
                symbol_id=item.symbol_id,
                price=item.price,
                license_days=item.license_days,
                metadata=item.metadata or {},
                auto_renew=getattr(item, "auto_renew", False),
                auto_renew_price=getattr(item, "auto_renew_price", None),
                auto_renew_cycle_days=getattr(item, "cycle_days_override", None),
                symbol_name=symbol_names.get(item.symbol_id),
            )
        )

    payment_intent_id = None
    qr_code_url = None
    deep_link = None
    if payment_intent:
        payment_intent_id = str(getattr(payment_intent, "intent_id", getattr(payment_intent, "id", "")))
        qr_code_url = getattr(payment_intent, "qr_code_url", None)
        deep_link = getattr(payment_intent, "deep_link", None)

    return CreateSymbolOrderResponse(
        order_id=str(order.order_id),
        total_amount=order.total_amount.quantize(Decimal('0.00')),
        status=order.status,
        payment_method=order.payment_method,
        items=response_items,
        created_at=order.created_at.isoformat(),
        message=message,
        payment_intent_id=payment_intent_id,
        qr_code_url=qr_code_url,
        deep_link=deep_link,
        insufficient_balance=insufficient_balance,
        wallet_balance=wallet_balance,
        shortage=shortage,
    )


@router.get("/symbol/orders/history/", response=PaginatedSymbolOrderHistory, auth=JWTAuth())
@router.get("/symbol/orders/history", response=PaginatedSymbolOrderHistory, auth=JWTAuth())
def get_order_history(
    request: HttpRequest,
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
):
    user = request.auth

    if limit > 100:
        limit = 100
    if limit <= 0:
        limit = 20
    if page <= 0:
        page = 1

    if status and status not in {choice for choice, _ in OrderStatus.choices}:
        raise HttpError(400, "Invalid status")

    try:
        orders_data = symbol_purchase_service.get_order_history(
            user=user,
            page=page,
            limit=limit,
            status=status,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise HttpError(500, f"Failed to get order history: {exc}")

    return PaginatedSymbolOrderHistory(**orders_data)


@router.post("/symbol/orders/{order_id}/pay-wallet", response=ProcessWalletPaymentResponse, auth=JWTAuth())
def process_wallet_payment(request: HttpRequest, order_id: str):
    try:
        result = symbol_purchase_service.process_wallet_payment(order_id, request.auth)
        return ProcessWalletPaymentResponse(**result)
    except ValueError as exc:
        raise HttpError(404, str(exc))


@router.post("/symbol/orders/{order_id}/pay-sepay", response=CreateSepayPaymentResponse, auth=JWTAuth())
def create_sepay_payment(request: HttpRequest, order_id: str):
    try:
        result = symbol_purchase_service.create_sepay_payment_intent(order_id, request.auth)
        return CreateSepayPaymentResponse(**result)
    except ValueError as exc:
        raise HttpError(404, str(exc))
    except Exception as exc:  # pragma: no cover
        raise HttpError(500, f"Failed to create payment intent: {exc}")


@router.post("/symbol/orders/{order_id}/topup-sepay", response=CreateSepayPaymentResponse, auth=JWTAuth())
def create_sepay_topup_for_order(request: HttpRequest, order_id: str):
    try:
        result = symbol_purchase_service.create_sepay_topup_for_insufficient_order(order_id, request.auth)
        return CreateSepayPaymentResponse(**result)
    except ValueError as exc:
        raise HttpError(400, str(exc))
    except Exception as exc:  # pragma: no cover
        raise HttpError(500, f"Failed to create topup intent: {exc}")


@router.get("/symbol/{symbol_id}/access", response=SymbolAccessCheckResponse, auth=JWTAuth())
def check_symbol_access(request: HttpRequest, symbol_id: int):
    try:
        result = symbol_purchase_service.check_symbol_access(request.auth, symbol_id)
        return SymbolAccessCheckResponse(**result)
    except Exception as exc:  # pragma: no cover - defensive
        raise HttpError(500, f"Failed to check access: {exc}")


@router.get("/symbol/licenses", response=List[UserSymbolLicenseResponse], auth=JWTAuth())
def get_user_symbol_licenses(request: HttpRequest, page: int = 1, limit: int = 20):
    try:
        licenses_data = symbol_purchase_service.get_user_symbol_licenses(request.auth, page, limit)
        return [UserSymbolLicenseResponse(**license) for license in licenses_data["results"]]
    except Exception as exc: 
        raise HttpError(500, f"Failed to get licenses: {exc}")


@router.get("/fallback", response=FallbackCallbackResponse)
def fallback_endpoint(request: HttpRequest):
    return FallbackCallbackResponse(
        message="Fallback endpoint invoked.",
        path=request.path,
        method=request.method,
        params=request.GET.dict(),
    )
