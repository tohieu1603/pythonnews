"""Repository layer cho notification - xử lý database operations"""
import logging
from typing import Optional, List
from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.notification.models import (
    NotificationEvent,
    NotificationDelivery,
    UserEndpoint,
    DeliveryStatus,
    WebhookLog,
    WebhookSource,
)

User = get_user_model()
logger = logging.getLogger('app')


class NotificationEventRepository:
    """Repository cho NotificationEvent model"""

    @staticmethod
    def create(
        user_id: int,
        event_type: str,
        payload: dict,
        subject_id: Optional[str] = None
    ) -> NotificationEvent:
        """Tạo notification event mới"""
        user = User.objects.get(id=user_id)
        event = NotificationEvent.objects.create(
            user=user,
            event_type=event_type,
            subject_id=subject_id,
            payload=payload,
            processed=False
        )
        logger.info(f"Created notification event {event.event_id} for user {user.email}")
        return event

    @staticmethod
    def get_by_id(event_id: str) -> Optional[NotificationEvent]:
        """Lấy event theo ID"""
        try:
            return NotificationEvent.objects.select_for_update().get(event_id=event_id)
        except NotificationEvent.DoesNotExist:
            logger.error(f"Event {event_id} not found")
            return None

    @staticmethod
    def get_by_user(user_id: int, limit: int = 50, offset: int = 0) -> QuerySet:
        """Lấy danh sách events của user"""
        return NotificationEvent.objects.filter(
            user_id=user_id
        ).order_by('-created_at')[offset:offset + limit]

    @staticmethod
    def mark_as_processed(event: NotificationEvent) -> None:
        """Đánh dấu event đã được xử lý"""
        event.processed = True
        event.save(update_fields=['processed'])


class NotificationDeliveryRepository:
    """Repository cho NotificationDelivery model"""

    @staticmethod
    def create(
        event: NotificationEvent,
        endpoint: UserEndpoint,
        channel: str
    ) -> NotificationDelivery:
        """Tạo delivery record mới"""
        return NotificationDelivery.objects.create(
            event=event,
            endpoint=endpoint,
            channel=channel,
            status=DeliveryStatus.QUEUED
        )

    @staticmethod
    def get_by_id(delivery_id: str) -> Optional[NotificationDelivery]:
        """Lấy delivery theo ID"""
        try:
            return NotificationDelivery.objects.select_related(
                'event', 'endpoint'
            ).get(delivery_id=delivery_id)
        except NotificationDelivery.DoesNotExist:
            logger.error(f"Delivery {delivery_id} not found")
            return None

    @staticmethod
    def get_by_event(event_id: str) -> QuerySet:
        """Lấy deliveries của một event"""
        return NotificationDelivery.objects.filter(
            event__event_id=event_id
        ).order_by('-sent_at')

    @staticmethod
    def get_failed_deliveries(limit: int = 100) -> QuerySet:
        """Lấy các deliveries bị failed"""
        return NotificationDelivery.objects.filter(
            status=DeliveryStatus.FAILED
        )[:limit]

    @staticmethod
    def get_pending_deliveries(limit: int = 100) -> QuerySet:
        """Lấy các deliveries đang pending"""
        return NotificationDelivery.objects.filter(
            status=DeliveryStatus.QUEUED
        ).select_related('event', 'endpoint')[:limit]

    @staticmethod
    def update_status(
        delivery: NotificationDelivery,
        status: str,
        error_message: Optional[str] = None,
        sent_at=None
    ) -> None:
        """Cập nhật status của delivery"""
        delivery.status = status
        if error_message:
            delivery.error_message = error_message
        if sent_at:
            delivery.sent_at = sent_at

        update_fields = ['status']
        if error_message:
            update_fields.append('error_message')
        if sent_at:
            update_fields.append('sent_at')

        delivery.save(update_fields=update_fields)


class UserEndpointRepository:
    """Repository cho UserEndpoint model"""

    @staticmethod
    def get_verified_endpoints(user_id: int) -> QuerySet:
        """Lấy tất cả endpoints đã verified của user"""
        return UserEndpoint.objects.filter(
            user_id=user_id,
            verified=True
        )

    @staticmethod
    def get_by_user(user_id: int) -> QuerySet:
        """Lấy tất cả endpoints của user"""
        return UserEndpoint.objects.filter(user_id=user_id).order_by('-created_at')

    @staticmethod
    def get_by_id(endpoint_id: str, user_id: int) -> Optional[UserEndpoint]:
        """Lấy endpoint theo ID và user"""
        try:
            return UserEndpoint.objects.get(
                endpoint_id=endpoint_id,
                user_id=user_id
            )
        except UserEndpoint.DoesNotExist:
            return None

    @staticmethod
    def exists(user_id: int, channel: str, address: str) -> bool:
        """Kiểm tra endpoint đã tồn tại chưa"""
        return UserEndpoint.objects.filter(
            user_id=user_id,
            channel=channel,
            address=address
        ).exists()

    @staticmethod
    def create(
        user_id: int,
        channel: str,
        address: str,
        details: Optional[dict] = None,
        is_primary: bool = False
    ) -> UserEndpoint:
        """Tạo endpoint mới"""
        user = User.objects.get(id=user_id)
        return UserEndpoint.objects.create(
            user=user,
            channel=channel,
            address=address,
            details=details,
            is_primary=is_primary,
            verified=False
        )

    @staticmethod
    def unset_primary_for_channel(user_id: int, channel: str, exclude_id: Optional[str] = None) -> None:
        """Unset is_primary cho tất cả endpoints của channel"""
        queryset = UserEndpoint.objects.filter(
            user_id=user_id,
            channel=channel,
            is_primary=True
        )
        if exclude_id:
            queryset = queryset.exclude(endpoint_id=exclude_id)
        queryset.update(is_primary=False)

    @staticmethod
    def update(endpoint: UserEndpoint, **kwargs) -> UserEndpoint:
        """Cập nhật endpoint"""
        for key, value in kwargs.items():
            if value is not None:
                setattr(endpoint, key, value)
        endpoint.save()
        return endpoint

    @staticmethod
    def delete(endpoint: UserEndpoint) -> None:
        """Xóa endpoint"""
        endpoint.delete()


class WebhookLogRepository:
    """Repository cho WebhookLog model"""

    @staticmethod
    def create(
        source: str,
        symbol: Optional[str],
        payload: dict,
        status_code: int = 200,
        response_data: Optional[dict] = None,
        error_message: Optional[str] = None,
        users_notified: int = 0
    ) -> WebhookLog:
        """Tạo webhook log mới"""
        webhook_log = WebhookLog.objects.create(
            source=source,
            symbol=symbol,
            payload=payload,
            status_code=status_code,
            response_data=response_data,
            error_message=error_message,
            users_notified=users_notified
        )
        logger.info(f"Created webhook log {webhook_log.webhook_id} for {source} - {symbol}")
        return webhook_log

    @staticmethod
    def get_by_symbol(symbol: str, limit: int = 50) -> QuerySet:
        """Lấy webhook logs theo symbol"""
        return WebhookLog.objects.filter(symbol=symbol).order_by('-created_at')[:limit]

    @staticmethod
    def get_by_source(source: str, limit: int = 50) -> QuerySet:
        """Lấy webhook logs theo source"""
        return WebhookLog.objects.filter(source=source).order_by('-created_at')[:limit]

    @staticmethod
    def get_recent(limit: int = 50) -> QuerySet:
        """Lấy webhook logs gần đây"""
        return WebhookLog.objects.all().order_by('-created_at')[:limit]
