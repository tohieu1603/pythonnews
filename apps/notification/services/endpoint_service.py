"""Service layer cho user endpoints - xử lý business logic"""
import logging
import secrets
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.notification.models import NotificationChannel
from apps.notification.repositories.notification_repository import UserEndpointRepository

logger = logging.getLogger('app')


class EndpointService:
    """Service để quản lý user endpoints"""

    def __init__(self):
        self.endpoint_repo = UserEndpointRepository()

    def list_endpoints(self, user_id: int):
        """Lấy danh sách endpoints của user"""
        return self.endpoint_repo.get_by_user(user_id)

    def get_endpoint(self, endpoint_id: str, user_id: int):
        """Lấy endpoint theo ID"""
        return self.endpoint_repo.get_by_id(endpoint_id, user_id)

    def create_endpoint(
        self,
        user_id: int,
        channel: str,
        address: str,
        details: Optional[dict] = None,
        is_primary: bool = False
    ):
        """
        Tạo endpoint mới cho user
        Nếu is_primary=True, unset các endpoint khác của cùng channel
        """
        if self.endpoint_repo.exists(user_id, channel, address):
            raise ValueError("Endpoint already exists")

        if is_primary:
            self.endpoint_repo.unset_primary_for_channel(user_id, channel)

        endpoint = self.endpoint_repo.create(
            user_id=user_id,
            channel=channel,
            address=address,
            details=details,
            is_primary=is_primary
        )

        if channel == NotificationChannel.EMAIL:
            try:
                self._issue_email_verification(endpoint)
            except Exception as exc:
                logger.exception("Failed to send verification email: %s", exc)
                raise ValueError("Unable to send verification email, please try again later")

        return endpoint

    def update_endpoint(
        self,
        endpoint_id: str,
        user_id: int,
        is_primary: Optional[bool] = None,
        verified: Optional[bool] = None,
        details: Optional[dict] = None
    ):
        """
        Cập nhật endpoint
        Nếu set is_primary=True, unset các endpoint khác cùng channel
        """
        endpoint = self.endpoint_repo.get_by_id(endpoint_id, user_id)
        if not endpoint:
            raise ValueError("Endpoint not found")

        if is_primary is True:
            self.endpoint_repo.unset_primary_for_channel(
                user_id,
                endpoint.channel,
                exclude_id=endpoint_id
            )

        update_payload = {
            'is_primary': is_primary,
            'details': details,
        }

        if verified is not None:
            if endpoint.channel == NotificationChannel.EMAIL and verified:
                raise ValueError("Email endpoint must be verified via OTP")
            update_payload['verified'] = verified

        updated = self.endpoint_repo.update(
            endpoint,
            **update_payload
        )

        if updated.channel == NotificationChannel.EMAIL and updated.verified:
            # Nếu admin set verified bằng tay, xóa thông tin mã cũ
            updated.verification_code = None
            updated.verification_expires_at = None
            updated.save(update_fields=['verification_code', 'verification_expires_at'])

        return updated

    def delete_endpoint(self, endpoint_id: str, user_id: int) -> bool:
        """Xóa endpoint"""
        endpoint = self.endpoint_repo.get_by_id(endpoint_id, user_id)
        if not endpoint:
            return False

        self.endpoint_repo.delete(endpoint)
        return True

    def verify_endpoint(
        self,
        endpoint_id: str,
        user_id: int,
        auto_verify: bool = False,
        verification_code: Optional[str] = None
    ):
        """
        Verify endpoint (OTP hoặc auto-verify cho Telegram /start)
        """
        endpoint = self.endpoint_repo.get_by_id(endpoint_id, user_id)
        if not endpoint:
            raise ValueError("Endpoint not found")

        if endpoint.verified:
            raise ValueError("Endpoint already verified")

        if endpoint.channel == NotificationChannel.EMAIL:
            return self._verify_email_endpoint(endpoint, auto_verify, verification_code)

        if auto_verify:
            endpoint.verified = True
            endpoint.save(update_fields=['verified'])
            return endpoint

        if not verification_code:
            raise ValueError("verification_code is required")

        # TODO: implement OTP verification cho các kênh khác
        endpoint.verified = True
        endpoint.save(update_fields=['verified'])
        return endpoint

    def resend_email_verification(self, endpoint_id: str, user_id: int):
        """Tạo lại mã xác thực email và gửi lại"""
        endpoint = self.endpoint_repo.get_by_id(endpoint_id, user_id)
        if not endpoint:
            raise ValueError("Endpoint not found")

        if endpoint.channel != NotificationChannel.EMAIL:
            raise ValueError("Only email endpoints support resending verification code")

        if endpoint.verified:
            raise ValueError("Endpoint already verified")

        self._issue_email_verification(endpoint)
        return endpoint

    def _generate_verification_code(self) -> str:
        """Sinh mã xác thực 6 chữ số"""
        return f"{secrets.randbelow(1_000_000):06d}"

    def _issue_email_verification(self, endpoint):
        """Sinh mã xác thực email và gửi tới user"""
        code = self._generate_verification_code()
        expires_at = timezone.now() + timedelta(minutes=2)

        endpoint.verification_code = code
        endpoint.verification_expires_at = expires_at
        endpoint.verified = False
        endpoint.save(update_fields=['verification_code', 'verification_expires_at', 'verified'])

        subject = "Xác thực email nhận thông báo PyNews"
        message = (
            "Xin chào,\n\n"
            "Bạn vừa đăng ký nhận thông báo qua email cho tài khoản PyNews.\n"
            f"Mã xác thực của bạn là: {code}\n"
            "Mã sẽ hết hạn sau 2 phút kể từ khi email này được gửi.\n\n"
            "Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.\n\n"
            "Trân trọng,\n"
            "PyNews Team"
        )

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)
        if not from_email:
            logger.error("DEFAULT_FROM_EMAIL is not configured")
            raise ValueError("Email sender is not configured")

        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[endpoint.address],
            fail_silently=False,
        )

    def _verify_email_endpoint(
        self,
        endpoint,
        auto_verify: bool,
        verification_code: Optional[str]
    ):
        """Thực hiện xác thực bằng mã OTP cho email endpoint"""
        if auto_verify:
            raise ValueError("Email endpoint requires verification code")

        if not verification_code:
            raise ValueError("verification_code is required")

        if not endpoint.verification_code or not endpoint.verification_expires_at:
            raise ValueError("Verification code not generated. Please recreate endpoint.")

        if timezone.now() > endpoint.verification_expires_at:
            raise ValueError("Verification code has expired. Please request a new code.")

        if str(verification_code).strip() != endpoint.verification_code:
            raise ValueError("Invalid verification code")

        endpoint.verified = True
        endpoint.verification_code = None
        endpoint.verification_expires_at = None
        endpoint.save(update_fields=['verified', 'verification_code', 'verification_expires_at'])
        return endpoint
