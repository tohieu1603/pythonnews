"""
Utility functions để gửi notification cho symbol signals
CHỈ GỬI CHO USER CÓ LICENSE ACTIVE
"""
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone

from apps.notification.models import AppEventType
from apps.notification.services.notification_service import NotificationService
from apps.notification.services.delivery_service import DeliveryService

logger = logging.getLogger('app')


def get_users_with_active_license(symbol_id: int) -> List[int]:
    """
    Lấy danh sách user_id có license ACTIVE cho symbol

    Args:
        symbol_id: ID của symbol

    Returns:
        List[int]: Danh sách user_id có quyền nhận thông báo
    """
    from django.db import models
    from apps.seapay.models import PayUserSymbolLicense, LicenseStatus

    now = timezone.now()

    licenses = PayUserSymbolLicense.objects.filter(
        symbol_id=symbol_id,
        status=LicenseStatus.ACTIVE
    ).filter(
        models.Q(end_at__isnull=True) | models.Q(end_at__gt=now)
    ).values_list('user_id', flat=True).distinct()

    user_ids = list(licenses)
    logger.info(f"Found {len(user_ids)} users with active license for symbol_id={symbol_id}")

    return user_ids


def send_symbol_signal_notification(
    user_id: int,
    symbol: str,
    signal_type: str,
    price: str,
    timestamp: str,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Gửi notification về tín hiệu symbol cho user

    Args:
        user_id: ID của user cần gửi
        symbol: Mã chứng khoán (VD: VNM, HPG)
        signal_type: Loại tín hiệu (buy, sell, hold)
        price: Giá hiện tại
        timestamp: Thời gian phát sinh tín hiệu
        description: Mô tả chi tiết tín hiệu
        metadata: Thông tin bổ sung

    Returns:
        True nếu gửi thành công, False nếu thất bại
    """
    try:
        payload = {
            'symbol': symbol,
            'signal_type': signal_type,
            'price': price,
            'timestamp': timestamp,
            'description': description or f"Tín hiệu {signal_type} cho {symbol}"
        }

        if metadata:
            payload['metadata'] = metadata

        notification_service = NotificationService()
        event, deliveries_count = notification_service.create_and_process_event(
            user_id=user_id,
            event_type=AppEventType.SYMBOL_SIGNAL,
            payload=payload
        )

        logger.info(
            f"Created symbol signal notification for user {user_id}: "
            f"{symbol} {signal_type} - {deliveries_count} deliveries"
        )

        if deliveries_count > 0:
            delivery_service = DeliveryService()
            delivery_service.send_pending_deliveries(limit=deliveries_count)

        return True

    except Exception as e:
        logger.error(f"Error sending symbol signal notification: {e}")
        return False


def send_symbol_signal_to_subscribers(
    symbol_id: int,
    symbol_name: str,
    signal_type: str,
    price: str,
    timestamp: str,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Gửi tín hiệu symbol cho TẤT CẢ users có license active

    Args:
        symbol_id: ID của symbol
        symbol_name: Tên mã CK (VNM, HPG, etc.)
        signal_type: Loại tín hiệu (buy, sell, hold)
        price: Giá hiện tại
        timestamp: Thời gian phát sinh tín hiệu
        description: Mô tả chi tiết
        metadata: Thông tin bổ sung

    Returns:
        Dict với thông tin:
        - total_users: Tổng số users có license
        - sent_count: Số notifications gửi thành công
        - failed_count: Số thất bại
    """
    user_ids = get_users_with_active_license(symbol_id)

    if not user_ids:
        logger.warning(f"No users with active license for symbol {symbol_name} (id={symbol_id})")
        return {
            'total_users': 0,
            'sent_count': 0,
            'failed_count': 0,
            'message': 'No subscribed users'
        }

    sent_count = 0
    failed_count = 0

    for user_id in user_ids:
        try:
            success = send_symbol_signal_notification(
                user_id=user_id,
                symbol=symbol_name,
                signal_type=signal_type,
                price=price,
                timestamp=timestamp,
                description=description,
                metadata=metadata
            )

            if success:
                sent_count += 1
            else:
                failed_count += 1

        except Exception as e:
            logger.error(f"Error sending signal to user {user_id}: {e}")
            failed_count += 1

    logger.info(
        f"Sent {sent_count}/{len(user_ids)} symbol signal notifications for {symbol_name}"
    )

    return {
        'total_users': len(user_ids),
        'sent_count': sent_count,
        'failed_count': failed_count,
        'symbol': symbol_name,
        'symbol_id': symbol_id
    }


def send_subscription_expiring_notification(
    user_id: int,
    symbol: str,
    symbol_id: int,
    expires_at: str,
    days_remaining: int
) -> bool:
    """
    Gửi notification về subscription sắp hết hạn

    Args:
        user_id: ID của user
        symbol: Mã chứng khoán
        symbol_id: ID của symbol
        expires_at: Thời gian hết hạn
        days_remaining: Số ngày còn lại

    Returns:
        True nếu gửi thành công
    """
    try:
        payload = {
            'symbol': symbol,
            'symbol_id': symbol_id,
            'expires_at': expires_at,
            'days_remaining': days_remaining,
            'message': f'Quyền truy cập vào {symbol} sẽ hết hạn sau {days_remaining} ngày (vào {expires_at})'
        }

        notification_service = NotificationService()
        event, deliveries_count = notification_service.create_and_process_event(
            user_id=user_id,
            event_type=AppEventType.SUBSCRIPTION_EXPIRING,
            payload=payload,
            subject_id=str(symbol_id)
        )

        logger.info(
            f"Created subscription expiring notification for user {user_id}: "
            f"{symbol} - {deliveries_count} deliveries"
        )

        if deliveries_count > 0:
            delivery_service = DeliveryService()
            delivery_service.send_pending_deliveries(limit=deliveries_count)

        return True

    except Exception as e:
        logger.error(f"Error sending subscription expiring notification: {e}")
        return False


def send_bulk_symbol_signals(user_symbol_map: Dict[int, Dict[str, Any]]) -> int:
    """
    Gửi hàng loạt tín hiệu symbol cho nhiều users
    (Deprecated - nên dùng send_symbol_signal_to_subscribers)

    Args:
        user_symbol_map: Dict mapping user_id -> signal data

    Returns:
        Số lượng notifications được gửi thành công
    """
    success_count = 0

    for user_id, signal_data in user_symbol_map.items():
        try:
            if send_symbol_signal_notification(
                user_id=user_id,
                symbol=signal_data['symbol'],
                signal_type=signal_data['signal_type'],
                price=signal_data['price'],
                timestamp=signal_data['timestamp'],
                description=signal_data.get('description', ''),
                metadata=signal_data.get('metadata')
            ):
                success_count += 1
        except Exception as e:
            logger.error(f"Error sending signal to user {user_id}: {e}")
            continue

    logger.info(f"Sent {success_count}/{len(user_symbol_map)} symbol signal notifications")
    return success_count
