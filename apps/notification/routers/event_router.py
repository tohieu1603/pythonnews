"""Router cho Notification Events"""
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from core.jwt_auth import cookie_or_bearer_jwt_auth
from apps.notification.models import NotificationEvent, AppEventType
from apps.notification.schemas import (
    NotificationEventSchema,
    NotificationDeliverySchema
)
from apps.notification.services.notification_service import NotificationService
from apps.notification.services.delivery_service import DeliveryService

router = Router(tags=["notification-events"], auth=cookie_or_bearer_jwt_auth)


@router.get("/events", response=List[NotificationEventSchema])
def list_events(request, limit: int = 50, offset: int = 0):
    """Lấy danh sách events của user"""
    service = NotificationService()
    events = service.get_user_events(request.auth.id, limit, offset)
    return [NotificationEventSchema.from_orm(event) for event in events]


@router.get("/events/{event_id}", response={200: NotificationEventSchema, 404: dict})
def get_event(request, event_id: str):
    """Lấy chi tiết một event"""
    event = get_object_or_404(
        NotificationEvent,
        event_id=event_id,
        user=request.auth
    )
    return NotificationEventSchema.from_orm(event)


@router.get("/events/{event_id}/deliveries", response=List[NotificationDeliverySchema])
def get_event_deliveries(request, event_id: str):
    """Lấy danh sách deliveries của một event"""
    event = get_object_or_404(
        NotificationEvent,
        event_id=event_id,
        user=request.auth
    )

    service = NotificationService()
    deliveries = service.get_event_deliveries(str(event.event_id))
    return [NotificationDeliverySchema.from_orm(d) for d in deliveries]


@router.post("/test-send", response={200: dict, 400: dict})
def test_send_notification(request, event_type: str, payload: dict):
    """
    Testing endpoint: Tạo và gửi notification test
    """
    try:
        notification_service = NotificationService()
        delivery_service = DeliveryService()

        event, deliveries_count = notification_service.create_and_process_event(
            user_id=request.auth.id,
            event_type=event_type,
            payload=payload
        )

        if deliveries_count > 0:
            sent_count = delivery_service.send_pending_deliveries(limit=deliveries_count)
            return {
                "event_id": str(event.event_id),
                "deliveries_created": deliveries_count,
                "deliveries_sent": sent_count
            }
        else:
            return {
                "event_id": str(event.event_id),
                "deliveries_created": 0,
                "message": "No verified endpoints found"
            }

    except Exception as e:
        return 400, {"error": str(e)}


@router.get("/tradingview-signals", response=List[NotificationEventSchema])
def list_tradingview_signals(request, symbol: str = None, limit: int = 50, offset: int = 0):
    """
    Xem danh sách signals đã nhận từ TradingView
    Filter theo symbol nếu cần
    """
    queryset = NotificationEvent.objects.filter(
        event_type=AppEventType.SYMBOL_SIGNAL
    )

    if symbol:
        queryset = queryset.filter(payload__symbol=symbol.upper())

    events = queryset.order_by('-created_at')[offset:offset + limit]
    return [NotificationEventSchema.from_orm(event) for event in events]
