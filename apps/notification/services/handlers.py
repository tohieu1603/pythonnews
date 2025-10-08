import logging
from abc import ABC, abstractmethod
from typing import Optional
import requests
from django.conf import settings

from apps.notification.models import NotificationDelivery, NotificationChannel

logger = logging.getLogger('app')


class NotificationHandler(ABC):
    """Base class cho các notification handlers"""

    @abstractmethod
    def send(self, delivery: NotificationDelivery) -> bool:
        """
        Gửi notification
        Returns: True nếu thành công, False nếu thất bại
        """
        pass

    @abstractmethod
    def format_message(self, delivery: NotificationDelivery) -> str:
        """Format message từ payload"""
        pass


class TelegramHandler(NotificationHandler):
    """Handler để gửi notification qua Telegram"""

    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send(self, delivery: NotificationDelivery) -> bool:
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            delivery.error_message = "TELEGRAM_BOT_TOKEN not configured"
            return False

        try:
            chat_id = delivery.endpoint.address
            message = self.format_message(delivery)

            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )

            delivery.response_raw = response.json()

            if response.status_code == 200 and response.json().get('ok'):
                logger.info(f"Sent Telegram notification to {chat_id}")
                return True
            else:
                error_msg = response.json().get('description', 'Unknown error')
                logger.error(f"Failed to send Telegram notification: {error_msg}")
                delivery.error_message = error_msg
                return False

        except Exception as e:
            logger.exception(f"Error sending Telegram notification: {e}")
            delivery.error_message = str(e)
            return False

    def format_message(self, delivery: NotificationDelivery) -> str:
        """Format message cho Telegram (HTML format)"""
        event = delivery.event
        payload = event.payload or {}

        # Format theo loại event
        if event.event_type == 'symbol_signal':
            symbol = payload.get('symbol', 'N/A')
            signal_type = payload.get('signal_type', 'N/A')
            price = payload.get('price', 'N/A')
            message = f"""
<b>📈 Tín hiệu {signal_type.upper()}: {symbol}</b>

Giá: {price}
Thời gian: {payload.get('timestamp', 'N/A')}

{payload.get('description', '')}
"""
        elif event.event_type == 'payment_success':
            message = f"""
<b>✅ Thanh toán thành công</b>

Số tiền: {payload.get('amount', 'N/A')}
Mã giao dịch: {payload.get('transaction_id', 'N/A')}
"""
        else:
            message = f"""
<b>🔔 Thông báo</b>

{payload.get('message', 'Bạn có một thông báo mới')}
"""

        return message.strip()


class ZaloHandler(NotificationHandler):
    """Handler để gửi notification qua Zalo OA"""

    def __init__(self):
        self.oa_access_token = getattr(settings, 'ZALO_OA_ACCESS_TOKEN', None)
        self.base_url = "https://openapi.zalo.me/v3.0/oa"

    def send(self, delivery: NotificationDelivery) -> bool:
        if not self.oa_access_token:
            logger.error("ZALO_OA_ACCESS_TOKEN not configured")
            delivery.error_message = "ZALO_OA_ACCESS_TOKEN not configured"
            return False

        try:
            user_id = delivery.endpoint.address
            message = self.format_message(delivery)

            response = requests.post(
                f"{self.base_url}/message/cs",
                headers={
                    "access_token": self.oa_access_token,
                    "Content-Type": "application/json"
                },
                json={
                    "recipient": {
                        "user_id": user_id
                    },
                    "message": {
                        "text": message
                    }
                },
                timeout=10
            )

            delivery.response_raw = response.json()

            if response.status_code == 200 and response.json().get('error') == 0:
                logger.info(f"Sent Zalo notification to {user_id}")
                return True
            else:
                error_msg = response.json().get('message', 'Unknown error')
                logger.error(f"Failed to send Zalo notification: {error_msg}")
                delivery.error_message = error_msg
                return False

        except Exception as e:
            logger.exception(f"Error sending Zalo notification: {e}")
            delivery.error_message = str(e)
            return False

    def format_message(self, delivery: NotificationDelivery) -> str:
        """Format message cho Zalo"""
        event = delivery.event
        payload = event.payload or {}

        if event.event_type == 'symbol_signal':
            symbol = payload.get('symbol', 'N/A')
            signal_type = payload.get('signal_type', 'N/A')
            price = payload.get('price', 'N/A')
            message = f"""📈 Tín hiệu {signal_type.upper()}: {symbol}

Giá: {price}
Thời gian: {payload.get('timestamp', 'N/A')}

{payload.get('description', '')}"""
        elif event.event_type == 'payment_success':
            message = f"""✅ Thanh toán thành công

Số tiền: {payload.get('amount', 'N/A')}
Mã giao dịch: {payload.get('transaction_id', 'N/A')}"""
        else:
            message = f"""🔔 Thông báo

{payload.get('message', 'Bạn có một thông báo mới')}"""

        return message.strip()


class EmailHandler(NotificationHandler):
    """Handler để gửi notification qua Email"""

    def send(self, delivery: NotificationDelivery) -> bool:
        from django.core.mail import send_mail
        from django.conf import settings

        try:
            email = delivery.endpoint.address
            subject = self.get_subject(delivery)
            message = self.format_message(delivery)

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            logger.info(f"Sent email notification to {email}")
            delivery.response_raw = {"status": "sent", "email": email}
            return True

        except Exception as e:
            logger.exception(f"Error sending email notification: {e}")
            delivery.error_message = str(e)
            return False

    def get_subject(self, delivery: NotificationDelivery) -> str:
        """Lấy subject cho email"""
        event = delivery.event
        payload = event.payload or {}

        if event.event_type == 'symbol_signal':
            symbol = payload.get('symbol', 'N/A')
            signal_type = payload.get('signal_type', 'N/A')
            return f"Tín hiệu {signal_type.upper()}: {symbol}"
        elif event.event_type == 'payment_success':
            return "Thanh toán thành công"
        else:
            return payload.get('subject', 'Thông báo từ PyNews')

    def format_message(self, delivery: NotificationDelivery) -> str:
        """Format message cho Email"""
        event = delivery.event
        payload = event.payload or {}

        if event.event_type == 'symbol_signal':
            symbol = payload.get('symbol', 'N/A')
            signal_type = payload.get('signal_type', 'N/A')
            price = payload.get('price', 'N/A')
            message = f"""Xin chào,

Bạn có tín hiệu mới từ PyNews:

Loại tín hiệu: {signal_type.upper()}
Mã CK: {symbol}
Giá: {price}
Thời gian: {payload.get('timestamp', 'N/A')}

{payload.get('description', '')}

---
Trân trọng,
PyNews Team"""
        elif event.event_type == 'payment_success':
            message = f"""Xin chào,

Thanh toán của bạn đã được xử lý thành công.

Số tiền: {payload.get('amount', 'N/A')}
Mã giao dịch: {payload.get('transaction_id', 'N/A')}

---
Trân trọng,
PyNews Team"""
        else:
            message = f"""{payload.get('message', 'Bạn có một thông báo mới từ PyNews')}

---
Trân trọng,
PyNews Team"""

        return message.strip()


# Handler registry
HANDLERS = {
    NotificationChannel.TELEGRAM: TelegramHandler,
    NotificationChannel.ZALO: ZaloHandler,
    NotificationChannel.EMAIL: EmailHandler,
}


def get_handler(channel: str) -> Optional[NotificationHandler]:
    """Lấy handler tương ứng với channel"""
    handler_class = HANDLERS.get(channel)
    if handler_class:
        return handler_class()
    return None
