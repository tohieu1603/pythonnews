from typing import Optional
from datetime import datetime
from ninja import Schema
from pydantic import Field, field_validator


class UserEndpointCreateSchema(Schema):
    """Schema để tạo endpoint mới"""
    channel: str = Field(..., description="telegram | zalo | email")
    address: str = Field(..., description="Telegram chat_id | Zalo user_id | email")
    details: Optional[dict] = Field(None, description="Thông tin phụ")
    is_primary: bool = Field(False, description="Endpoint mặc định")

    @field_validator('channel')
    def validate_channel(cls, v):
        allowed = ['telegram', 'zalo', 'email']
        if v not in allowed:
            raise ValueError(f"Channel must be one of {allowed}")
        return v


class UserEndpointUpdateSchema(Schema):
    """Schema để update endpoint"""
    is_primary: Optional[bool] = None
    verified: Optional[bool] = None
    details: Optional[dict] = None


class UserEndpointSchema(Schema):
    """Schema để trả về endpoint"""
    endpoint_id: str
    channel: str
    address: str
    details: Optional[dict]
    is_primary: bool
    verified: bool
    created_at: datetime

    @staticmethod
    def from_orm(endpoint):
        return UserEndpointSchema(
            endpoint_id=str(endpoint.endpoint_id),
            channel=endpoint.channel,
            address=endpoint.address,
            details=endpoint.details,
            is_primary=endpoint.is_primary,
            verified=endpoint.verified,
            created_at=endpoint.created_at
        )


class NotificationEventCreateSchema(Schema):
    """Schema để tạo notification event"""
    event_type: str
    payload: dict
    subject_id: Optional[str] = None


class NotificationEventSchema(Schema):
    """Schema để trả về notification event"""
    event_id: str
    event_type: str
    subject_id: Optional[str]
    payload: Optional[dict]
    created_at: datetime
    processed: bool

    @staticmethod
    def from_orm(event):
        return NotificationEventSchema(
            event_id=str(event.event_id),
            event_type=event.event_type,
            subject_id=str(event.subject_id) if event.subject_id else None,
            payload=event.payload,
            created_at=event.created_at,
            processed=event.processed
        )


class NotificationDeliverySchema(Schema):
    """Schema để trả về delivery"""
    delivery_id: str
    channel: str
    status: str
    sent_at: Optional[datetime]
    error_message: Optional[str]

    @staticmethod
    def from_orm(delivery):
        return NotificationDeliverySchema(
            delivery_id=str(delivery.delivery_id),
            channel=delivery.channel,
            status=delivery.status,
            sent_at=delivery.sent_at,
            error_message=delivery.error_message
        )


class VerifyEndpointSchema(Schema):
    """Schema để verify endpoint (OTP hoặc start command)"""
    verification_code: Optional[str] = Field(None, description="OTP code nếu dùng OTP")
    auto_verify: bool = Field(False, description="Auto verify (dùng cho Telegram /start)")


class BroadcastSignalSchema(Schema):
    """Schema để broadcast signal cho tất cả users có license"""
    symbol_id: int = Field(..., description="ID của symbol")
    symbol_name: str = Field(..., description="Tên mã CK (VNM, HPG, etc.)")
    signal_type: str = Field(..., description="Loại tín hiệu: buy, sell, hold")
    price: str = Field(..., description="Giá hiện tại")
    timestamp: str = Field(..., description="Thời gian phát sinh tín hiệu")
    description: Optional[str] = Field("", description="Mô tả chi tiết")
    metadata: Optional[dict] = Field(None, description="Thông tin bổ sung")


class TradingViewWebhookSchema(Schema):
    """Schema cho webhook từ TradingView"""
    Type: str = Field(..., description="BUY hoặc SELL")
    TransId: int
    Action: str = Field(..., description="Open, Close, etc.")
    botName: str
    Symbol: str = Field(..., description="Mã chứng khoán")
    Price: float
    CheckDate: int = Field(..., description="Timestamp in milliseconds")
    MaxPrice: Optional[float] = None
    MinPrice: Optional[float] = None
    TP: Optional[float] = None
    SL: Optional[float] = None
    ExitPrice: Optional[float] = None
    Direction: Optional[str] = None
    PositionSize: Optional[float] = None
    Profit: Optional[float] = None
    MaxDrawdown: Optional[float] = None
    TradeDuration: Optional[int] = None
    WinLossStatus: Optional[str] = None
    DistanceToSL: Optional[float] = None
    DistanceToTP: Optional[float] = None
    VolatilityAdjustedProfit: Optional[float] = None
