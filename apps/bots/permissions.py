from django.utils import timezone
from apps.seapay.models import PayUserSymbolLicense, LicenseStatus


def user_has_symbol_access(user, symbol_id: int) -> bool:
    """
    Check if user has active license for a symbol.

    Args:
        user: Django User instance
        symbol_id: Symbol ID to check access for

    Returns:
        bool: True if user has active license, False otherwise
    """
    if not user or not user.is_authenticated:
        return False

    # Check if user has any active license for this symbol
    active_licenses = PayUserSymbolLicense.objects.filter(
        user=user,
        symbol_id=symbol_id,
        status=LicenseStatus.ACTIVE
    )

    # Check if any license is currently valid
    now = timezone.now()
    for license in active_licenses:
        # If end_at is None, it's a lifetime license
        if license.end_at is None:
            return True
        # If end_at is in the future, license is still valid
        if license.end_at > now:
            return True

    return False


def user_can_access_bot(user, bot) -> bool:
    """
    Check if user can access a specific bot.

    Args:
        user: Django User instance
        bot: Bot instance

    Returns:
        bool: True if user can access the bot, False otherwise
    """
    return user_has_symbol_access(user, bot.symbol_id)
