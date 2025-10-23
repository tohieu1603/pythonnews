from ninja import Router
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from ninja.errors import HttpError
from typing import List

from core.jwt_auth import JWTAuth
from apps.stock.models import Symbol
from .models import Bot, Trade
from .schemas import BotSchema, BotDetailSchema, TradeSchema, SymbolBotsSchema
from .permissions import user_has_symbol_access, user_can_access_bot

router = Router()


@router.get("/symbols/{symbol_id}/bots", response=SymbolBotsSchema, tags=["Bots"], auth=JWTAuth())
def get_symbol_bots(request: HttpRequest, symbol_id: int):
    """Get 3 bots (Ngắn hạn, Trung hạn, Dài hạn) for a symbol with trades - requires purchase"""
    user = request.auth

    # Check if user has purchased this symbol
    if not user_has_symbol_access(user, symbol_id):
        raise HttpError(403, "Bạn cần mua mã này để xem bot")

    symbol = get_object_or_404(Symbol, id=symbol_id)
    bots = Bot.objects.filter(symbol=symbol).select_related('symbol').prefetch_related('trades').order_by('bot_type')

    return {
        'symbol_id': symbol.id,
        'symbol_name': symbol.name,
        'bots': bots
    }


@router.get("/bots", response=List[BotSchema], tags=["Bots"], auth=JWTAuth())
def list_bots(request: HttpRequest):
    """Get all bots that the authenticated user has purchased"""
    user = request.auth

    # Get all bots
    all_bots = Bot.objects.select_related('symbol').all()

    # Filter bots based on user's symbol licenses
    accessible_bots = [
        bot
        for bot in all_bots
        if user_has_symbol_access(user, bot.symbol_id)
    ]

    return accessible_bots


@router.get("/bots/{bot_id}", response=BotDetailSchema, tags=["Bots"], auth=JWTAuth())
def get_bot(request: HttpRequest, bot_id: int):
    """Get bot detail with trades - requires user to have purchased the symbol"""
    user = request.auth

    bot = get_object_or_404(
        Bot.objects.select_related('symbol').prefetch_related('trades'),
        id=bot_id
    )

    # Check if user has access to this bot's symbol
    if not user_can_access_bot(user, bot):
        raise HttpError(403, f"Bạn cần mua mã '{bot.symbol.name}' để xem bot này")

    return bot


@router.get("/bots/{bot_id}/trades", response=List[TradeSchema], tags=["Bots"], auth=JWTAuth())
def list_bot_trades(request: HttpRequest, bot_id: int):
    """Get all trades for a specific bot - requires user to have purchased the symbol"""
    user = request.auth

    bot = get_object_or_404(Bot, id=bot_id)

    # Check if user has access to this bot's symbol
    if not user_can_access_bot(user, bot):
        raise HttpError(403, f"You need to purchase symbol to access these trades")

    trades = Trade.objects.filter(bot=bot).order_by('-entry_date')
    return list(trades)

@router.get("/trades", response=List[TradeSchema], tags=["Bots"], auth=JWTAuth())
def list_all_trades(request: HttpRequest, bot_id: int = None, symbol_id: int = None):
    """Get all trades for symbols the user has purchased"""
    user = request.auth

    trades = Trade.objects.select_related('bot', 'bot__symbol').all()

    if bot_id:
        trades = trades.filter(bot_id=bot_id)
        # Check access for specific bot
        bot = get_object_or_404(Bot, id=bot_id)
        if not user_can_access_bot(user, bot):
            raise HttpError(403, "You need to purchase this symbol to access these trades")

    if symbol_id:
        # Check access for specific symbol
        if not user_has_symbol_access(user, symbol_id):
            raise HttpError(403, "You need to purchase this symbol to access these trades")
        trades = trades.filter(bot__symbol_id=symbol_id)

    # Filter trades to only show those from bots the user has access to
    accessible_trades = [
        trade for trade in trades
        if user_has_symbol_access(user, trade.bot.symbol_id)
    ]

    return sorted(accessible_trades, key=lambda t: t.entry_date, reverse=True)


@router.get("/trades/{trade_id}", response=TradeSchema, tags=["Bots"], auth=JWTAuth())
def get_trade(request: HttpRequest, trade_id: str):
    """Get single trade by ID - requires user to have purchased the symbol"""
    user = request.auth

    trade = get_object_or_404(
        Trade.objects.select_related('bot'),
        id=trade_id
    )

    # Check if user has access to this trade's bot's symbol
    if not user_can_access_bot(user, trade.bot):
        raise HttpError(403, "You need to purchase this symbol to access this trade")

    return trade
