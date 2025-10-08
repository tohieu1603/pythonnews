"""Service layer cho notification events - xử lý business logic"""
import logging
from typing import Optional
from django.db import transaction

from apps.notification.repositories.notification_repository import (
    NotificationEventRepository,
    NotificationDeliveryRepository,
    UserEndpointRepository
)

logger = logging.getLogger('app')


class NotificationService:
    """Service để tạo và xử lý notification events"""

    def __init__(self):
        self.event_repo = NotificationEventRepository()
        self.delivery_repo = NotificationDeliveryRepository()
        self.endpoint_repo = UserEndpointRepository()

    def create_event(
        self,
        user_id: int,
        event_type: str,
        payload: dict,
        subject_id: Optional[str] = None
    ):
        """Tạo notification event mới"""
        return self.event_repo.create(
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            subject_id=subject_id
        )

    @transaction.atomic
    def process_event(self, event_id: str) -> int:
        """
        Xử lý event: tạo delivery records cho tất cả endpoints đã verified của user
        Returns: số lượng deliveries được tạo
        """
        event = self.event_repo.get_by_id(event_id)
        if not event:
            return 0

        if event.processed:
            logger.warning(f"Event {event_id} already processed")
            return 0

        endpoints = self.endpoint_repo.get_verified_endpoints(event.user_id)

        deliveries_created = 0
        for endpoint in endpoints:
            self.delivery_repo.create(
                event=event,
                endpoint=endpoint,
                channel=endpoint.channel
            )
            deliveries_created += 1

        self.event_repo.mark_as_processed(event)

        logger.info(f"Processed event {event_id}: created {deliveries_created} deliveries")
        return deliveries_created

    def create_and_process_event(
        self,
        user_id: int,
        event_type: str,
        payload: dict,
        subject_id: Optional[str] = None
    ) -> tuple:
        """
        Tạo event và process ngay lập tức
        Returns: (event, số delivery được tạo)
        """
        event = self.create_event(
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            subject_id=subject_id
        )
        deliveries_count = self.process_event(str(event.event_id))
        return event, deliveries_count

    def get_event(self, event_id: str):
        """Lấy event theo ID"""
        return self.event_repo.get_by_id(event_id)

    def get_user_events(self, user_id: int, limit: int = 50, offset: int = 0):
        """Lấy danh sách events của user"""
        return self.event_repo.get_by_user(user_id, limit, offset)

    def get_event_deliveries(self, event_id: str):
        """Lấy deliveries của một event"""
        return self.delivery_repo.get_by_event(event_id)
