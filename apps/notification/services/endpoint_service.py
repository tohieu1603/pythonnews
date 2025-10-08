"""Service layer cho user endpoints - xử lý business logic"""
import logging
from typing import Optional

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

        return self.endpoint_repo.create(
            user_id=user_id,
            channel=channel,
            address=address,
            details=details,
            is_primary=is_primary
        )

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

        return self.endpoint_repo.update(
            endpoint,
            is_primary=is_primary,
            verified=verified,
            details=details
        )

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

        # TODO: 
        if auto_verify:
            return self.endpoint_repo.update(endpoint, verified=True)
        else:
            if not verification_code:
                raise ValueError("verification_code is required")

            # TODO:
            return self.endpoint_repo.update(endpoint, verified=True)
