"""Router cho TradingView Webhook"""
from ninja import Router
from datetime import datetime
import logging
import requests
from apps.notification.schemas import TradingViewWebhookSchema
from apps.notification.services.notification_utils import send_symbol_signal_to_subscribers
from apps.notification.repositories.notification_repository import WebhookLogRepository
from apps.notification.models import WebhookSource

logger = logging.getLogger('app')

router = Router(tags=["notification-webhooks"], auth=None)


@router.post("/webhook/tradingview", response={200: dict, 400: dict, 404: dict})
def tradingview_webhook(request, payload: TradingViewWebhookSchema):
    """
    Webhook nhận tín hiệu từ TradingView
    Tự động gửi thông báo cho users đã đăng ký symbol và có license active
    """
    print("Received TradingView webhook:", payload.dict())
    print("Payload details:", request.body)

    webhook_repo = WebhookLogRepository()
    symbol_name = payload.Symbol.upper()

    try:
        from apps.stock.models import Symbol

        try:
            symbol = Symbol.objects.get(name=symbol_name)
        except Symbol.DoesNotExist:
            webhook_repo.create(
                source=WebhookSource.TRADINGVIEW,
                symbol=symbol_name,
                payload=payload.dict(),
                status_code=404,
                error_message=f"Symbol {symbol_name} not found in database",
                users_notified=0
            )
            return 404, {"error": f"Symbol {symbol_name} not found in database"}

        timestamp_str = datetime.fromtimestamp(payload.CheckDate / 1000).strftime('%Y-%m-%d %H:%M:%S')

        description_parts = [
            f"Bot: {payload.botName}",
            f"Action: {payload.Action}",
        ]

        if payload.Direction:
            description_parts.append(f"Direction: {payload.Direction}")
        if payload.TP:
            description_parts.append(f"TP: {payload.TP}")
        if payload.SL:
            description_parts.append(f"SL: {payload.SL}")
        if payload.Profit is not None:
            description_parts.append(f"Profit: {payload.Profit}")
        if payload.WinLossStatus:
            description_parts.append(f"Status: {payload.WinLossStatus}")

        description = " | ".join(description_parts)

        metadata = {
            "raw_payload": payload.dict(),  
            "trans_id": payload.TransId,
            "bot_name": payload.botName,
            "action": payload.Action,
            "type": payload.Type,
            "direction": payload.Direction,
            "max_price": payload.MaxPrice,
            "min_price": payload.MinPrice,
            "tp": payload.TP,
            "sl": payload.SL,
            "exit_price": payload.ExitPrice,
            "position_size": payload.PositionSize,
            "profit": payload.Profit,
            "max_drawdown": payload.MaxDrawdown,
            "trade_duration": payload.TradeDuration,
            "win_loss_status": payload.WinLossStatus,
            "distance_to_sl": payload.DistanceToSL,
            "distance_to_tp": payload.DistanceToTP,
            "volatility_adjusted_profit": payload.VolatilityAdjustedProfit,
        }
        url = "https://backtest.togogo.vn/api/v10/BackTest/wh"
        response = requests.post(
            url,
            json=metadata,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print("Posted to backtest.togogo.vn, response:", response.status_code, response.text)
        result = send_symbol_signal_to_subscribers(
            symbol_id=symbol.id,
            symbol_name=symbol_name,
            signal_type=payload.Type.lower(),
            price=str(payload.Price),
            timestamp=timestamp_str,
            description=description,
            metadata=metadata
        )

        response_data = {
            "success": True,
            "symbol": symbol_name,
            "signal_type": payload.Type,
            "total_users": result['total_users'],
            "sent_count": result['sent_count'],
            "failed_count": result['failed_count'],
            "message": f"Sent to {result['sent_count']} users"
        }

        webhook_repo.create(
            source=WebhookSource.TRADINGVIEW,
            symbol=symbol_name,
            payload=payload.dict(),
            status_code=200,
            response_data=response_data,
            users_notified=result['sent_count']
        )

        return response_data

    except Exception as e:
        logger.error(f"Error processing TradingView webhook: {e}")

        # Lưu webhook log với lỗi
        webhook_repo.create(
            source=WebhookSource.TRADINGVIEW,
            symbol=symbol_name,
            payload=payload.dict(),
            status_code=400,
            error_message=str(e),
            users_notified=0
        )

        return 400, {"error": str(e)}
