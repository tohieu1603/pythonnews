from ninja import Schema
from datetime import datetime
from typing import Optional
from decimal import Decimal


class TradeSchema(Schema):
    """Schema for Trade response"""
    id: str
    trans_id: int
    trade_type: str
    direction: Optional[str] = None
    price: Optional[Decimal] = None
    entry_date: datetime
    exit_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    position_size: Optional[float] = None
    profit: Optional[float] = None
    max_duration: Optional[int] = None
    win_loss_status: Optional[str] = None
    action: str
    created_at: datetime

    class Config:
        from_attributes = True


class BotSchema(Schema):
    """Schema for Bot response"""
    id: int
    name: str
    bot_type: str
    bot_type_display: Optional[str] = None
    symbol_id: int
    symbol_name: Optional[str] = None

    @staticmethod
    def resolve_bot_type_display(obj):
        return obj.get_bot_type_display()

    @staticmethod
    def resolve_symbol_name(obj):
        return obj.symbol.name if obj.symbol else None

    class Config:
        from_attributes = True


class BotDetailSchema(BotSchema):
    """Schema for Bot detail with trades"""
    trades: list[TradeSchema] = []

    @staticmethod
    def resolve_trades(obj):
        return list(obj.trades.all().order_by('-entry_date'))

    class Config:
        from_attributes = True


class SymbolBotsSchema(Schema):
    """Schema for Symbol with its 3 bots"""
    symbol_id: int
    symbol_name: str
    bots: list[BotSchema]
