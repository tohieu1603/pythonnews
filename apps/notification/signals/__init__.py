"""
Signal handlers để tự động gửi notification khi có sự kiện
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.seapay.models import PaySymbolOrder, OrderStatus

from apps.notification.models import AppEventType
from apps.notification.services.notification_service import NotificationService

logger = logging.getLogger('app')


@receiver(post_save, sender=PaySymbolOrder)
def send_order_notification(sender, instance, created, **kwargs):
    """
    Gửi notification khi order được tạo hoặc status thay đổi
    """
    try:
        service = NotificationService()

        if created:
            service.create_and_process_event(
                user_id=instance.user.id,
                event_type=AppEventType.ORDER_CREATED,
                payload={
                    'order_id': str(instance.order_id),
                    'total_amount': str(instance.total_amount),
                    'status': instance.status,
                    'message': f'Đơn hàng mới #{str(instance.order_id)[:8]} đã được tạo với tổng giá trị {instance.total_amount} VNĐ'
                },
                subject_id=str(instance.order_id)
            )
            logger.info(f"Created notification event for new order {instance.order_id}")

        elif instance.status == OrderStatus.PAID:
            service.create_and_process_event(
                user_id=instance.user.id,
                event_type=AppEventType.PAYMENT_SUCCESS,
                payload={
                    'order_id': str(instance.order_id),
                    'amount': str(instance.total_amount),
                    'transaction_id': str(instance.order_id),
                    'message': f'Thanh toán đơn hàng #{str(instance.order_id)[:8]} thành công với số tiền {instance.total_amount} VNĐ'
                },
                subject_id=str(instance.order_id)
            )
            logger.info(f"Created notification event for paid order {instance.order_id}")

        elif instance.status == OrderStatus.FAILED:
            service.create_and_process_event(
                user_id=instance.user.id,
                event_type=AppEventType.PAYMENT_FAILED,
                payload={
                    'order_id': str(instance.order_id),
                    'amount': str(instance.total_amount),
                    'message': f'Thanh toán đơn hàng #{str(instance.order_id)[:8]} thất bại'
                },
                subject_id=str(instance.order_id)
            )
            logger.info(f"Created notification event for failed order {instance.order_id}")

    except Exception as e:
        logger.error(f"Error creating notification for order {instance.order_id}: {e}")
