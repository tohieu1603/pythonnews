"""Router cho User Endpoints Management"""
from typing import List
from ninja import Router
from django.shortcuts import get_object_or_404

from core.jwt_auth import cookie_or_bearer_jwt_auth
from apps.notification.models import UserEndpoint
from apps.notification.schemas import (
    UserEndpointCreateSchema,
    UserEndpointUpdateSchema,
    UserEndpointSchema,
    VerifyEndpointSchema
)
from apps.notification.services.endpoint_service import EndpointService

router = Router(tags=["notification-endpoints"], auth=cookie_or_bearer_jwt_auth)


@router.get("/endpoints", response=List[UserEndpointSchema])
def list_endpoints(request):
    """Lấy danh sách endpoints của user hiện tại"""
    service = EndpointService()
    endpoints = service.list_endpoints(request.auth.id)
    return [UserEndpointSchema.from_orm(ep) for ep in endpoints]


@router.post("/endpoints", response={201: UserEndpointSchema, 400: dict})
def create_endpoint(request, payload: UserEndpointCreateSchema):
    """Tạo endpoint mới cho user"""
    try:
        service = EndpointService()
        endpoint = service.create_endpoint(
            user_id=request.auth.id,
            channel=payload.channel,
            address=payload.address,
            details=payload.details,
            is_primary=payload.is_primary
        )
        return 201, UserEndpointSchema.from_orm(endpoint)
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:
        return 400, {"error": str(e)}


@router.get("/endpoints/{endpoint_id}", response={200: UserEndpointSchema, 404: dict})
def get_endpoint(request, endpoint_id: str):
    """Lấy thông tin một endpoint"""
    endpoint = get_object_or_404(
        UserEndpoint,
        endpoint_id=endpoint_id,
        user=request.auth
    )
    return UserEndpointSchema.from_orm(endpoint)


@router.patch("/endpoints/{endpoint_id}", response={200: UserEndpointSchema, 404: dict, 400: dict})
def update_endpoint(request, endpoint_id: str, payload: UserEndpointUpdateSchema):
    """Cập nhật endpoint"""
    try:
        service = EndpointService()
        endpoint = service.update_endpoint(
            endpoint_id=endpoint_id,
            user_id=request.auth.id,
            is_primary=payload.is_primary,
            verified=payload.verified,
            details=payload.details
        )
        return UserEndpointSchema.from_orm(endpoint)
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:
        return 400, {"error": str(e)}


@router.delete("/endpoints/{endpoint_id}", response={204: None, 404: dict})
def delete_endpoint(request, endpoint_id: str):
    """Xóa endpoint"""
    service = EndpointService()
    success = service.delete_endpoint(endpoint_id, request.auth.id)
    if not success:
        return 404, {"error": "Endpoint not found"}
    return 204, None


@router.post("/endpoints/{endpoint_id}/verify", response={200: UserEndpointSchema, 400: dict, 404: dict})
def verify_endpoint(request, endpoint_id: str, payload: VerifyEndpointSchema):
    """Verify endpoint (OTP hoặc auto-verify cho Telegram /start)"""
    try:
        service = EndpointService()
        endpoint = service.verify_endpoint(
            endpoint_id=endpoint_id,
            user_id=request.auth.id,
            auto_verify=payload.auto_verify,
            verification_code=payload.verification_code
        )
        return UserEndpointSchema.from_orm(endpoint)
    except ValueError as e:
        return 400, {"error": str(e)}
    except Exception as e:
        return 400, {"error": str(e)}
