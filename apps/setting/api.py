from typing import List

from django.http import HttpRequest
from django.db import transaction
from ninja import Router
from ninja.errors import HttpError

from core.jwt_auth import JWTAuth
from apps.setting.schemas import (
    SymbolAutoRenewAttemptResponse,
    SymbolAutoRenewSubscriptionResponse,
)
from apps.setting.services.subscription_service import SymbolAutoRenewService

router = Router()
auto_renew_service = SymbolAutoRenewService()


@router.get("/symbol/subscriptions", response=List[SymbolAutoRenewSubscriptionResponse], auth=JWTAuth())
def list_symbol_subscriptions(request: HttpRequest):
    """Return every auto-renew subscription for the authenticated user."""
    user = request.auth
    subscriptions = auto_renew_service.list_user_subscriptions(user)
    return [SymbolAutoRenewSubscriptionResponse(**subscription) for subscription in subscriptions]


@router.post("/symbol/subscriptions/{subscription_id}/pause", response=SymbolAutoRenewSubscriptionResponse, auth=JWTAuth())
@transaction.atomic
def pause_symbol_subscription(request: HttpRequest, subscription_id: str):
    """Pause billing for a specific subscription."""
    user = request.auth
    try:
        subscription = auto_renew_service.pause_subscription(subscription_id, user)
        return SymbolAutoRenewSubscriptionResponse(**subscription)
    except ValueError as exc:
        raise HttpError(404, str(exc))


@router.post("/symbol/subscriptions/{subscription_id}/resume", response=SymbolAutoRenewSubscriptionResponse, auth=JWTAuth())
@transaction.atomic
def resume_symbol_subscription(request: HttpRequest, subscription_id: str):
    """Resume billing for a paused subscription."""
    user = request.auth
    try:
        subscription = auto_renew_service.resume_subscription(subscription_id, user)
        return SymbolAutoRenewSubscriptionResponse(**subscription)
    except ValueError as exc:
        raise HttpError(404, str(exc))


@router.post("/symbol/subscriptions/{subscription_id}/cancel", response=SymbolAutoRenewSubscriptionResponse, auth=JWTAuth())
@transaction.atomic
def cancel_symbol_subscription(request: HttpRequest, subscription_id: str):
    """Cancel a subscription and clear its future billing schedule."""
    user = request.auth
    try:
        subscription = auto_renew_service.cancel_subscription(subscription_id, user)
        return SymbolAutoRenewSubscriptionResponse(**subscription)
    except ValueError as exc:
        raise HttpError(404, str(exc))


@router.get("/symbol/subscriptions/{subscription_id}/attempts", response=List[SymbolAutoRenewAttemptResponse], auth=JWTAuth())
def list_symbol_subscription_attempts(request: HttpRequest, subscription_id: str, limit: int = 20):
    """Return auto-renew attempts for the given subscription (newest first)."""
    user = request.auth
    if limit <= 0:
        limit = 20
    if limit > 100:
        limit = 100
    try:
        attempts = auto_renew_service.get_subscription_attempts(subscription_id, user, limit=limit)
        return [SymbolAutoRenewAttemptResponse(**attempt) for attempt in attempts]
    except ValueError as exc:
        raise HttpError(404, str(exc))
