"""
Currency support for django-iyzico.

Provides constants, validation, and utilities for multi-currency payments.

Supported Currencies:
    - TRY: Turkish Lira (primary)
    - USD: US Dollar
    - EUR: Euro
    - GBP: British Pound Sterling
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# Currency Constants
# ============================================================================


class Currency(str, Enum):
    """
    Supported currency codes.

    Based on Iyzico API documentation and ISO 4217 standard.
    """

    TRY = "TRY"  # Turkish Lira (default)
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro
    GBP = "GBP"  # British Pound Sterling

    @classmethod
    def choices(cls) -> List[Tuple[str, str]]:
        """
        Get currency choices for Django field.

        Returns:
            List of (value, label) tuples
        """
        return [
            (cls.TRY.value, "Turkish Lira (TRY)"),
            (cls.USD.value, "US Dollar (USD)"),
            (cls.EUR.value, "Euro (EUR)"),
            (cls.GBP.value, "British Pound Sterling (GBP)"),
        ]

    @classmethod
    def values(cls) -> List[str]:
        """Get list of currency codes."""
        return [c.value for c in cls]

    @classmethod
    def default(cls) -> str:
        """Get default currency (TRY)."""
        return cls.TRY.value


# Currency display information
CURRENCY_INFO = {
    Currency.TRY: {
        "code": "TRY",
        "name": "Turkish Lira",
        "symbol": "₺",
        "decimal_places": 2,
        "thousands_separator": ".",
        "decimal_separator": ",",
    },
    Currency.USD: {
        "code": "USD",
        "name": "US Dollar",
        "symbol": "$",
        "decimal_places": 2,
        "thousands_separator": ",",
        "decimal_separator": ".",
    },
    Currency.EUR: {
        "code": "EUR",
        "name": "Euro",
        "symbol": "€",
        "decimal_places": 2,
        "thousands_separator": ".",
        "decimal_separator": ",",
    },
    Currency.GBP: {
        "code": "GBP",
        "name": "British Pound Sterling",
        "symbol": "£",
        "decimal_places": 2,
        "thousands_separator": ",",
        "decimal_separator": ".",
    },
}


# ============================================================================
# Validation Functions
# ============================================================================


def is_valid_currency(currency: str) -> bool:
    """
    Check if currency code is valid.

    Args:
        currency: Currency code (e.g., 'TRY', 'USD')

    Returns:
        True if valid, False otherwise

    Example:
        >>> is_valid_currency('TRY')
        True
        >>> is_valid_currency('JPY')
        False
    """
    return currency in Currency.values()


def validate_currency(currency: str) -> str:
    """
    Validate and normalize currency code.

    Args:
        currency: Currency code to validate

    Returns:
        Normalized currency code (uppercase)

    Raises:
        ValueError: If currency code is invalid

    Example:
        >>> validate_currency('try')
        'TRY'
        >>> validate_currency('JPY')
        ValueError: Unsupported currency: JPY
    """
    if not currency:
        raise ValueError("Currency code is required")

    normalized = currency.upper().strip()

    if not is_valid_currency(normalized):
        supported = ", ".join(Currency.values())
        raise ValueError(f"Unsupported currency: {currency}. " f"Supported currencies: {supported}")

    return normalized


def get_currency_info(currency: str) -> Dict[str, Any]:
    """
    Get currency display information.

    Args:
        currency: Currency code

    Returns:
        Dictionary with currency information

    Raises:
        ValueError: If currency is invalid

    Example:
        >>> info = get_currency_info('USD')
        >>> print(info['symbol'])
        $
    """
    normalized = validate_currency(currency)
    return CURRENCY_INFO[Currency(normalized)].copy()


# ============================================================================
# Formatting Functions
# ============================================================================


def format_amount(
    amount: Decimal,
    currency: str,
    show_symbol: bool = True,
    show_code: bool = False,
) -> str:
    """
    Format amount with currency symbol/code.

    Args:
        amount: Amount to format
        currency: Currency code
        show_symbol: Whether to show currency symbol
        show_code: Whether to show currency code

    Returns:
        Formatted amount string

    Example:
        >>> format_amount(Decimal('1234.56'), 'USD')
        '$1,234.56'
        >>> format_amount(Decimal('1234.56'), 'TRY', show_code=True)
        '₺1.234,56 TRY'
    """
    info = get_currency_info(currency)

    # Round to currency's decimal places
    decimal_places = info["decimal_places"]
    rounded = amount.quantize(Decimal(10) ** -decimal_places, rounding=ROUND_HALF_UP)

    # Format with separators
    amount_str = str(abs(rounded))
    parts = amount_str.split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else "0" * decimal_places

    # Add thousands separator
    thousands_sep = info["thousands_separator"]
    formatted_integer = ""
    for i, digit in enumerate(reversed(integer_part)):
        if i > 0 and i % 3 == 0:
            formatted_integer = thousands_sep + formatted_integer
        formatted_integer = digit + formatted_integer

    # Combine with decimal separator
    decimal_sep = info["decimal_separator"]
    formatted = f"{formatted_integer}{decimal_sep}{decimal_part[:decimal_places]}"

    # Add negative sign if needed
    if amount < 0:
        formatted = f"-{formatted}"

    # Add symbol/code
    result = formatted
    if show_symbol:
        symbol = info["symbol"]
        # Symbol placement varies by currency
        if currency in [Currency.USD, Currency.GBP]:
            result = f"{symbol}{formatted}"
        else:  # TRY, EUR
            result = f"{symbol}{formatted}"

    if show_code:
        result = f"{result} {currency}"

    return result


def parse_amount(amount_str: str, currency: str) -> Decimal:
    """
    Parse formatted amount string to Decimal.

    Args:
        amount_str: Formatted amount string
        currency: Currency code

    Returns:
        Decimal amount

    Raises:
        ValueError: If amount string is invalid

    Example:
        >>> parse_amount('$1,234.56', 'USD')
        Decimal('1234.56')
        >>> parse_amount('₺1.234,56', 'TRY')
        Decimal('1234.56')
    """
    info = get_currency_info(currency)

    # Remove currency symbol and code
    cleaned = amount_str.strip()
    for symbol in ["₺", "$", "€", "£"]:
        cleaned = cleaned.replace(symbol, "")
    for code in Currency.values():
        cleaned = cleaned.replace(code, "")
    cleaned = cleaned.strip()

    # Remove thousands separator
    thousands_sep = info["thousands_separator"]
    cleaned = cleaned.replace(thousands_sep, "")

    # Replace decimal separator with standard '.'
    decimal_sep = info["decimal_separator"]
    cleaned = cleaned.replace(decimal_sep, ".")

    try:
        return Decimal(cleaned)
    except (ValueError, TypeError, InvalidOperation) as e:
        raise ValueError(f"Invalid amount format: {amount_str}") from e


# ============================================================================
# Conversion Functions
# ============================================================================


class CurrencyConverter:
    """
    Currency conversion utilities.

    Note: This is a simple implementation. For production use,
    integrate with a real-time exchange rate API.
    """

    # Sample exchange rates (TRY base)
    # In production, fetch from API like fixer.io, exchangerate.host, etc.
    DEFAULT_RATES = {
        Currency.TRY: Decimal("1.00"),
        Currency.USD: Decimal("0.033"),  # 1 TRY ≈ 0.033 USD
        Currency.EUR: Decimal("0.030"),  # 1 TRY ≈ 0.030 EUR
        Currency.GBP: Decimal("0.026"),  # 1 TRY ≈ 0.026 GBP
    }

    def __init__(self, rates: Optional[Dict[str, Decimal]] = None):
        """
        Initialize converter with exchange rates.

        Args:
            rates: Dictionary of exchange rates (TRY base)
                   If None, uses default rates
        """
        self.rates = rates if rates else self.DEFAULT_RATES.copy()

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Converted amount

        Raises:
            ValueError: If currencies are invalid

        Example:
            >>> converter = CurrencyConverter()
            >>> converter.convert(Decimal('100.00'), 'USD', 'TRY')
            Decimal('3030.30')
        """
        from_curr = validate_currency(from_currency)
        to_curr = validate_currency(to_currency)

        # Same currency - no conversion needed
        if from_curr == to_curr:
            return amount

        # Convert to TRY first, then to target currency
        from_rate = self.rates[Currency(from_curr)]
        to_rate = self.rates[Currency(to_curr)]

        # amount in TRY = amount / from_rate
        # amount in target = amount_in_try * to_rate
        try_amount = amount / from_rate
        result = try_amount * to_rate

        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Exchange rate

        Example:
            >>> converter = CurrencyConverter()
            >>> rate = converter.get_rate('USD', 'TRY')
            >>> print(f"1 USD = {rate} TRY")
        """
        from_curr = validate_currency(from_currency)
        to_curr = validate_currency(to_currency)

        if from_curr == to_curr:
            return Decimal("1.00")

        from_rate = self.rates[Currency(from_curr)]
        to_rate = self.rates[Currency(to_curr)]

        rate = to_rate / from_rate
        return rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def update_rates(self, rates: Dict[str, Decimal]) -> None:
        """
        Update exchange rates.

        Args:
            rates: Dictionary of new rates (TRY base)

        Example:
            >>> converter = CurrencyConverter()
            >>> converter.update_rates({
            ...     'USD': Decimal('0.034'),
            ...     'EUR': Decimal('0.031'),
            ... })
        """
        for currency, rate in rates.items():
            normalized = validate_currency(currency)
            self.rates[Currency(normalized)] = rate


# ============================================================================
# Helper Functions
# ============================================================================


def get_currency_symbol(currency: str) -> str:
    """
    Get currency symbol.

    Args:
        currency: Currency code

    Returns:
        Currency symbol

    Example:
        >>> get_currency_symbol('USD')
        '$'
    """
    info = get_currency_info(currency)
    return info["symbol"]


def get_currency_name(currency: str) -> str:
    """
    Get full currency name.

    Args:
        currency: Currency code

    Returns:
        Currency name

    Example:
        >>> get_currency_name('EUR')
        'Euro'
    """
    info = get_currency_info(currency)
    return info["name"]


def get_all_currencies() -> List[Dict[str, Any]]:
    """
    Get information for all supported currencies.

    Returns:
        List of currency information dictionaries

    Example:
        >>> currencies = get_all_currencies()
        >>> for curr in currencies:
        ...     print(f"{curr['code']}: {curr['name']}")
        TRY: Turkish Lira
        USD: US Dollar
        ...
    """
    return [{"code": code, **info} for code, info in CURRENCY_INFO.items()]


def compare_amounts(
    amount1: Decimal,
    currency1: str,
    amount2: Decimal,
    currency2: str,
    converter: Optional[CurrencyConverter] = None,
) -> int:
    """
    Compare two amounts in different currencies.

    Args:
        amount1: First amount
        currency1: First currency
        amount2: Second amount
        currency2: Second currency
        converter: Currency converter (uses default if None)

    Returns:
        -1 if amount1 < amount2, 0 if equal, 1 if amount1 > amount2

    Example:
        >>> compare_amounts(Decimal('100'), 'USD', Decimal('3000'), 'TRY')
        1  # $100 > 3000 TRY
    """
    if not converter:
        converter = CurrencyConverter()

    # Convert both to TRY for comparison
    amount1_try = converter.convert(amount1, currency1, Currency.TRY)
    amount2_try = converter.convert(amount2, currency2, Currency.TRY)

    if amount1_try < amount2_try:
        return -1
    elif amount1_try > amount2_try:
        return 1
    else:
        return 0
