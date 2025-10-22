from ninja import Router
from django.shortcuts import get_object_or_404
from typing import List

from .models import Bot, Trade
from .schemas import BotSchema, BotDetailSchema, TradeSchema

router = Router()


@router.get("/bots", response=List[BotSchema], tags=["Bots"])
def list_bots(request):
    """Get all bots"""
    bots = Bot.objects.select_related('symbol').all()
    return [
        {
            'id': bot.id,
            'name': bot.name,
            'symbol_id': bot.symbol_id,
            'symbol_name': bot.symbol.name if bot.symbol else None
        }
        for bot in bots
    ]


@router.get("/bots/{bot_id}", response=BotDetailSchema, tags=["Bots"])
def get_bot(request, bot_id: int):
    """Get bot detail with trades"""
    bot = get_object_or_404(
        Bot.objects.select_related('symbol').prefetch_related('trades'),
        id=bot_id
    )

    return {
        'id': bot.id,
        'name': bot.name,
        'symbol_id': bot.symbol_id,
        'symbol_name': bot.symbol.name if bot.symbol else None,
        'trades': list(bot.trades.all().order_by('-entry_date'))
    }


@router.get("/bots/{bot_id}/trades", response=List[TradeSchema], tags=["Bots"])
def list_bot_trades(request, bot_id: int):
    """Get all trades for a specific bot"""
    bot = get_object_or_404(Bot, id=bot_id)
    trades = Trade.objects.filter(bot=bot).order_by('-entry_date')
    return list(trades)


@router.get("/trades", response=List[TradeSchema], tags=["Bots"])
def list_all_trades(request, bot_id: int = None, symbol: str = None):
    """Get all trades with optional filters"""
    trades = Trade.objects.select_related('bot', 'bot__symbol').all()

    if bot_id:
        trades = trades.filter(bot_id=bot_id)

    if symbol:
        trades = trades.filter(bot__symbol__name=symbol)

    return list(trades.order_by('-entry_date'))


@router.get("/trades/{trade_id}", response=TradeSchema, tags=["Bots"])
def get_trade(request, trade_id: str):
    """Get single trade by ID"""
    trade = get_object_or_404(Trade, id=trade_id)
    return trade
