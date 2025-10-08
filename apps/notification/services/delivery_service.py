"""Service layer cho notification deliveries - xử lý gửi notifications"""
import logging
from django.utils import timezone

from apps.notification.models import DeliveryStatus
from apps.notification.repositories.notification_repository import (
    NotificationDeliveryRepository
)

logger = logging.getLogger('app')


class DeliveryService:
    """Service để gửi notifications qua các kênh khác nhau"""

    def __init__(self):
        self.delivery_repo = NotificationDeliveryRepository()

    def send_delivery(self, delivery_id: str) -> bool:
        """
        Gửi notification qua kênh tương ứng
        Returns: True nếu gửi thành công
        """
        delivery = self.delivery_repo.get_by_id(delivery_id)
        if not delivery:
            return False

        try:
            self.delivery_repo.update_status(delivery, DeliveryStatus.SENDING)

            from apps.notification.services.handlers import get_handler
            handler = get_handler(delivery.channel)

            if handler:
                success = handler.send(delivery)
                if success:
                    self.delivery_repo.update_status(
                        delivery,
                        DeliveryStatus.SENT,
                        sent_at=timezone.now()
                    )
                else:
                    self.delivery_repo.update_status(
                        delivery,
                        DeliveryStatus.FAILED
                    )
                return success
            else:
                logger.error(f"No handler found for channel {delivery.channel}")
                self.delivery_repo.update_status(
                    delivery,
                    DeliveryStatus.FAILED,
                    error_message=f"No handler for channel {delivery.channel}"
                )
                return False

        except Exception as e:
            logger.exception(f"Error sending delivery {delivery_id}: {e}")
            try:
                delivery = self.delivery_repo.get_by_id(delivery_id)
                if delivery:
                    self.delivery_repo.update_status(
                        delivery,
                        DeliveryStatus.FAILED,
                        error_message=str(e)
                    )
            except:
                pass
            return False

    def retry_failed_deliveries(self, limit: int = 100) -> int:
        """
        Retry các deliveries bị failed
        Returns: số deliveries được retry
        """
        failed_deliveries = self.delivery_repo.get_failed_deliveries(limit)

        retried = 0
        for delivery in failed_deliveries:
            self.delivery_repo.update_status(delivery, DeliveryStatus.RETRYING)

            if self.send_delivery(str(delivery.delivery_id)):
                retried += 1

        logger.info(f"Retried {retried} failed deliveries")
        return retried

    def send_pending_deliveries(self, limit: int = 100) -> int:
        """
        Gửi các deliveries đang pending
        Returns: số deliveries được gửi thành công
        """
        pending_deliveries = self.delivery_repo.get_pending_deliveries(limit)

        sent_count = 0
        for delivery in pending_deliveries:
            if self.send_delivery(str(delivery.delivery_id)):
                sent_count += 1

        logger.info(f"Sent {sent_count}/{len(pending_deliveries)} pending deliveries")
        return sent_count
