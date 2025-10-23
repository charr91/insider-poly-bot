"""
Shared Formatting Utilities
Common formatting functions used across Discord and Telegram formatters
"""

from typing import Dict


def _format_single_price(price: float) -> str:
    """
    Format a single price value

    Args:
        price: Price as decimal (0.0 to 1.0+ range)

    Returns:
        Formatted price string like "4¢", "0.25¢", or "$1.02"
    """
    price_cents = price * 100

    if price >= 1.0:
        # $1.00 or more - show as dollars with 2 decimals
        return f"${price:.2f}"
    elif price_cents < 1.0:
        # Less than 1¢ - show with 2 decimals for precision
        return f"{price_cents:.2f}¢"
    else:
        # 1¢ to 99¢ - show whole cents (rounded)
        return f"{round(price_cents)}¢"


def format_market_price(market_data: Dict) -> str:
    """
    Format market prices as whole cents or dollars

    Formatting rules:
    - < 1¢: show as "0¢"
    - 1¢ to 99¢: show as "4¢", "96¢" (whole numbers)
    - ≥ $1.00: show as "$1.02" (dollar format)

    Args:
        market_data: Market data dict containing outcomePrices or lastTradePrice

    Returns:
        Formatted price string like "4¢ YES / 96¢ NO" or "0¢ YES / 100¢ NO"
    """
    # Try to get both YES and NO prices from outcomePrices array
    outcome_prices = market_data.get('outcomePrices')
    if outcome_prices and isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
        # Display both YES and NO prices
        try:
            yes_price = float(outcome_prices[0])
            no_price = float(outcome_prices[1])

            # Format each price individually
            yes_str = _format_single_price(yes_price)
            no_str = _format_single_price(no_price)

            return f"{yes_str} YES / {no_str} NO"
        except (ValueError, TypeError):
            return "Price unavailable"
    else:
        # Fallback to lastTradePrice if outcomePrices not available
        last_price = market_data.get('lastTradePrice', 0)
        if last_price > 0:
            return f"{_format_single_price(last_price)} YES"
        else:
            return "Price unavailable"


def format_volume(volume_24hr: float) -> str:
    """
    Format volume with K/M suffix

    Args:
        volume_24hr: 24-hour volume as float

    Returns:
        Formatted volume string like "$127K" or "$1.5M"
    """
    if volume_24hr >= 1000000:
        return f"${volume_24hr/1000000:.1f}M"
    elif volume_24hr >= 1000:
        return f"${volume_24hr/1000:.0f}K"
    else:
        return f"${volume_24hr:.0f}"


def extract_outcome_name(question: str) -> str:
    """
    Extract short outcome name from market question

    Examples:
        "Will 3 Fed rate cuts happen in 2025?" → "3 Fed rate cuts"
        "Will Bitcoin reach $200k?" → "Bitcoin reach $200k"

    Args:
        question: Full market question

    Returns:
        Short outcome description (max 50 chars)
    """
    import re

    # Remove "Will" at the start and trailing "?"
    cleaned = re.sub(r'^\s*Will\s+', '', question, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*\?+\s*$', '', cleaned)

    # Remove "happen in YEAR" suffix
    cleaned = re.sub(r'\s+happen\s+in\s+\d{4}', '', cleaned, flags=re.IGNORECASE)

    # Remove "in YEAR" suffix
    cleaned = re.sub(r'\s+in\s+\d{4}', '', cleaned, flags=re.IGNORECASE)

    # Clean up extra whitespace
    cleaned = ' '.join(cleaned.split())

    # Shorten if too long
    if len(cleaned) <= 50:
        return cleaned
    else:
        return cleaned[:47] + "..."
