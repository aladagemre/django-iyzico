"""
Installment payment client for django-iyzico.

Handles installment info retrieval and payment processing with
installment options.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from django.core.cache import cache
from django.conf import settings

from .client import IyzicoClient
from .exceptions import IyzicoAPIException, IyzicoValidationException

logger = logging.getLogger(__name__)


# Known invalid/test BIN prefixes that should be rejected in production
INVALID_TEST_BINS: Set[str] = frozenset(
    {
        "000000",
        "111111",
        "222222",
        "333333",
        "444444",
        "555555",
        "666666",
        "777777",
        "888888",
        "999999",
        "123456",
        "654321",
        "012345",
        "543210",
    }
)

# Valid Major Industry Identifier (MII) first digits for payment cards
# 3 = Travel/Entertainment (Amex, Diners)
# 4 = Visa
# 5 = Mastercard
# 6 = Discover, China UnionPay
VALID_MII_DIGITS: Set[str] = frozenset({"3", "4", "5", "6"})


def validate_bin_number(bin_number: str, allow_test_bins: bool = False) -> str:
    """
    Comprehensive BIN (Bank Identification Number) validation.

    Validates the first 6 digits of a card number according to payment
    industry standards including MII (Major Industry Identifier) validation.

    Args:
        bin_number: The 6-digit BIN number to validate.
        allow_test_bins: If True, allows known test BINs (for development/testing).

    Returns:
        The validated BIN number (stripped of whitespace).

    Raises:
        IyzicoValidationException: If the BIN number is invalid.

    Example:
        >>> validate_bin_number('554960')  # Valid Mastercard BIN
        '554960'
        >>> validate_bin_number('123456')  # Test BIN - raises exception
        IyzicoValidationException: Invalid test BIN number

    Security Note:
        This function helps prevent:
        - Injection attacks via malformed BIN inputs
        - Processing with known test/invalid card numbers
        - Requests with impossible card number prefixes
    """
    # Check for None or empty
    if not bin_number:
        raise IyzicoValidationException(
            "BIN number is required",
            error_code="BIN_REQUIRED",
        )

    # Clean the input - remove whitespace only
    bin_number = bin_number.strip()

    # Check exact length
    if len(bin_number) != 6:
        raise IyzicoValidationException(
            "BIN number must be exactly 6 digits",
            error_code="BIN_INVALID_LENGTH",
        )

    # Check that it contains only digits
    if not bin_number.isdigit():
        raise IyzicoValidationException(
            "BIN number must contain only digits",
            error_code="BIN_INVALID_CHARACTERS",
        )

    # Check against known invalid/test BINs
    if not allow_test_bins and bin_number in INVALID_TEST_BINS:
        raise IyzicoValidationException(
            "Invalid test BIN number - not accepted for transactions",
            error_code="BIN_TEST_NUMBER",
        )

    # Validate MII (Major Industry Identifier) - first digit
    first_digit = bin_number[0]
    if first_digit not in VALID_MII_DIGITS:
        raise IyzicoValidationException(
            f"Invalid BIN: first digit '{first_digit}' does not correspond to a valid "
            f"payment card issuer. Valid first digits are: {', '.join(sorted(VALID_MII_DIGITS))}",
            error_code="BIN_INVALID_MII",
        )

    # Additional validation: check for sequential/repetitive patterns
    # that are unlikely to be real BINs
    if len(set(bin_number)) == 1:
        raise IyzicoValidationException(
            "Invalid BIN: repetitive digit pattern detected",
            error_code="BIN_REPETITIVE_PATTERN",
        )

    # Check for simple sequential patterns
    if bin_number in ("345678", "456789", "234567"):
        raise IyzicoValidationException(
            "Invalid BIN: sequential digit pattern detected",
            error_code="BIN_SEQUENTIAL_PATTERN",
        )

    logger.debug(f"BIN validation passed for {bin_number[:2]}****")
    return bin_number


@dataclass
class InstallmentOption:
    """
    Represents a single installment option.

    Attributes:
        installment_number: Number of installments (1-12)
        base_price: Original price without fees
        total_price: Total price with installment fees
        monthly_price: Price per month
        installment_rate: Fee rate as percentage
    """

    installment_number: int
    base_price: Decimal
    total_price: Decimal
    monthly_price: Decimal
    installment_rate: Decimal = Decimal("0.00")

    @property
    def is_zero_interest(self) -> bool:
        """Check if this is a 0% interest installment."""
        return self.installment_rate == Decimal("0.00")

    @property
    def total_fee(self) -> Decimal:
        """Calculate total installment fee."""
        return self.total_price - self.base_price

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "installment_number": self.installment_number,
            "base_price": str(self.base_price),
            "total_price": str(self.total_price),
            "monthly_price": str(self.monthly_price),
            "installment_rate": str(self.installment_rate),
            "total_fee": str(self.total_fee),
            "is_zero_interest": self.is_zero_interest,
        }


@dataclass
class BankInstallmentInfo:
    """
    Represents installment options for a specific bank.

    Attributes:
        bank_name: Name of the bank
        bank_code: Bank code identifier
        installment_options: List of available installment options
    """

    bank_name: str
    bank_code: int
    installment_options: List[InstallmentOption]

    def get_option(self, installment_number: int) -> Optional[InstallmentOption]:
        """Get specific installment option by number."""
        for option in self.installment_options:
            if option.installment_number == installment_number:
                return option
        return None

    def get_zero_interest_options(self) -> List[InstallmentOption]:
        """Get all 0% interest installment options."""
        return [opt for opt in self.installment_options if opt.is_zero_interest]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bank_name": self.bank_name,
            "bank_code": self.bank_code,
            "installment_options": [opt.to_dict() for opt in self.installment_options],
        }


class InstallmentClient:
    """
    Client for Iyzico installment payment operations.

    Handles retrieving installment options and processing
    installment payments with built-in rate limiting and caching.

    Settings:
        IYZICO_INSTALLMENT_CACHE_TIMEOUT: Cache duration in seconds (default: 300)
        IYZICO_INSTALLMENT_RATE_LIMIT: Max requests per window (default: 100)
        IYZICO_INSTALLMENT_RATE_WINDOW: Rate limit window in seconds (default: 60)
        IYZICO_ALLOW_TEST_BINS: Allow test BIN numbers (default: DEBUG setting)

    Example:
        >>> client = InstallmentClient()
        >>> options = client.get_installment_info(
        ...     bin_number='554960',
        ...     amount=Decimal('100.00'),
        ... )
        >>> for bank in options:
        ...     print(f"{bank.bank_name}: {len(bank.installment_options)} options")
    """

    # Rate limit settings
    DEFAULT_RATE_LIMIT = 100  # requests
    DEFAULT_RATE_WINDOW = 60  # seconds

    def __init__(self, client: Optional[IyzicoClient] = None):
        """
        Initialize installment client.

        Args:
            client: Optional IyzicoClient instance. If not provided,
                   a new one will be created.
        """
        self.client = client or IyzicoClient()
        self.cache_timeout = getattr(
            settings,
            "IYZICO_INSTALLMENT_CACHE_TIMEOUT",
            300,  # 5 minutes default
        )
        # Rate limiting configuration
        self.rate_limit_requests = getattr(
            settings,
            "IYZICO_INSTALLMENT_RATE_LIMIT",
            self.DEFAULT_RATE_LIMIT,
        )
        self.rate_limit_window = getattr(
            settings,
            "IYZICO_INSTALLMENT_RATE_WINDOW",
            self.DEFAULT_RATE_WINDOW,
        )
        self.rate_limiting_enabled = getattr(
            settings,
            "IYZICO_RATE_LIMITING_ENABLED",
            True,
        )

    def _check_rate_limit(self, identifier: str) -> bool:
        """
        Check if the rate limit has been exceeded for an identifier.

        Uses a sliding window counter pattern stored in cache.

        Args:
            identifier: Unique identifier for rate limiting (e.g., IP, user ID, BIN).

        Returns:
            True if request is allowed, False if rate limited.

        Note:
            Rate limiting is disabled in DEBUG mode by default.
        """
        if not self.rate_limiting_enabled:
            return True

        if settings.DEBUG and not getattr(settings, "IYZICO_RATE_LIMIT_IN_DEBUG", False):
            return True

        cache_key = f"iyzico_installment_ratelimit_{identifier}"

        try:
            current_count = cache.get(cache_key, 0)

            if current_count >= self.rate_limit_requests:
                logger.warning(
                    f"Rate limit exceeded for identifier {identifier[:20]}...: "
                    f"{current_count}/{self.rate_limit_requests} requests"
                )
                return False

            # Increment counter with sliding window
            # Use cache.add for atomic operation where supported
            new_count = current_count + 1
            cache.set(cache_key, new_count, self.rate_limit_window)

            return True

        except Exception as e:
            # If cache fails, allow the request but log the error
            logger.error(f"Rate limit check failed: {e}")
            return True

    def _increment_rate_limit(self, identifier: str) -> None:
        """
        Increment the rate limit counter for an identifier.

        Called after a successful (non-cached) API request.

        Args:
            identifier: Unique identifier for rate limiting.
        """
        if not self.rate_limiting_enabled:
            return

        if settings.DEBUG and not getattr(settings, "IYZICO_RATE_LIMIT_IN_DEBUG", False):
            return

        cache_key = f"iyzico_installment_ratelimit_{identifier}"

        try:
            current_count = cache.get(cache_key, 0)
            cache.set(cache_key, current_count + 1, self.rate_limit_window)
        except Exception as e:
            logger.error(f"Failed to increment rate limit counter: {e}")

    def get_installment_info(
        self,
        bin_number: str,
        amount: Decimal,
        use_cache: bool = True,
    ) -> List[BankInstallmentInfo]:
        """
        Retrieve installment options for a card BIN and amount.

        Args:
            bin_number: First 6 digits of card number (BIN)
            amount: Payment amount
            use_cache: Whether to use cached results

        Returns:
            List of BankInstallmentInfo with available options

        Raises:
            IyzicoValidationException: If BIN or amount is invalid
            IyzicoAPIException: If API call fails

        Example:
            >>> options = client.get_installment_info('554960', Decimal('100.00'))
            >>> for bank in options:
            ...     for opt in bank.installment_options:
            ...         print(f"{opt.installment_number}x: {opt.monthly_price}")
        """
        # Validate inputs using comprehensive BIN validation
        allow_test = getattr(settings, "IYZICO_ALLOW_TEST_BINS", settings.DEBUG)
        bin_number = validate_bin_number(bin_number, allow_test_bins=allow_test)

        if amount <= 0:
            raise IyzicoValidationException(
                "Amount must be greater than zero",
                error_code="INVALID_AMOUNT",
            )

        # Check cache first (before rate limiting - cached responses don't count)
        cache_key = f"iyzico_installments_{bin_number}_{amount}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Returning cached installment info for BIN {bin_number}")
                return cached

        # Check rate limit (only for non-cached API calls)
        if not self._check_rate_limit(bin_number):
            raise IyzicoAPIException(
                "Rate limit exceeded. Please try again later.",
                error_code="RATE_LIMIT_EXCEEDED",
            )

        # Call Iyzico API
        try:
            import iyzipay
            from .utils import parse_iyzico_response

            request_data = {
                "binNumber": bin_number,
                "price": str(amount),
                "locale": self.client.settings.locale,
            }

            logger.info(f"Fetching installment info for BIN {bin_number}, " f"amount {amount}")

            # Use official iyzipay SDK
            installment_info_request = iyzipay.InstallmentInfo()
            raw_response = installment_info_request.retrieve(
                request_data, self.client.get_options()
            )

            # Parse response
            response = parse_iyzico_response(raw_response)

            # Check for errors
            if response.get("status") != "success":
                raise IyzicoAPIException(
                    f"Failed to retrieve installment info: {response.get('errorMessage', 'Unknown error')}"
                )

            installment_info = self._parse_installment_response(response, amount)

            # Cache result and register the key for safe cleanup
            if use_cache:
                cache.set(cache_key, installment_info, self.cache_timeout)
                self._register_cache_key(cache_key)

            logger.info(
                f"Retrieved {len(installment_info)} bank installment options "
                f"for BIN {bin_number}"
            )

            return installment_info

        except IyzicoAPIException as e:
            logger.error(f"Failed to get installment info: {e}")
            raise

        except Exception as e:
            logger.exception(f"Unexpected error getting installment info: {e}")
            raise IyzicoAPIException(
                f"Failed to retrieve installment info: {str(e)}",
                error_code="INSTALLMENT_FETCH_ERROR",
            ) from e

    def _parse_installment_response(
        self,
        response: Dict,
        base_amount: Decimal,
    ) -> List[BankInstallmentInfo]:
        """
        Parse Iyzico installment API response.

        Args:
            response: Raw API response
            base_amount: Base payment amount

        Returns:
            List of BankInstallmentInfo objects
        """
        bank_info_list = []

        installment_details = response.get("installmentDetails", [])

        for bank_data in installment_details:
            bank_name = bank_data.get("bankName", "Unknown")
            bank_code = bank_data.get("bankCode", 0)

            installment_prices = bank_data.get("installmentPrices", [])
            installment_options = []

            for price_data in installment_prices:
                installment_number = price_data.get("installmentNumber", 1)
                total_price = Decimal(str(price_data.get("totalPrice", "0.00")))
                monthly_price = Decimal(str(price_data.get("installmentPrice", "0.00")))

                # Calculate installment rate
                if installment_number > 1 and total_price > base_amount:
                    installment_rate = (total_price - base_amount) / base_amount * 100
                else:
                    installment_rate = Decimal("0.00")

                option = InstallmentOption(
                    installment_number=installment_number,
                    base_price=base_amount,
                    total_price=total_price,
                    monthly_price=monthly_price,
                    installment_rate=installment_rate,
                )

                installment_options.append(option)

            bank_info = BankInstallmentInfo(
                bank_name=bank_name,
                bank_code=bank_code,
                installment_options=installment_options,
            )

            bank_info_list.append(bank_info)

        return bank_info_list

    def validate_installment_option(
        self,
        bin_number: str,
        amount: Decimal,
        installment_number: int,
    ) -> Optional[InstallmentOption]:
        """
        Validate that an installment option is available.

        Args:
            bin_number: Card BIN
            amount: Payment amount
            installment_number: Requested installment count

        Returns:
            InstallmentOption if valid, None otherwise

        Example:
            >>> option = client.validate_installment_option(
            ...     '554960',
            ...     Decimal('100.00'),
            ...     3,
            ... )
            >>> if option:
            ...     print(f"Valid: {option.monthly_price}/month")
        """
        try:
            banks = self.get_installment_info(bin_number, amount)

            # Check all banks for the requested installment option
            for bank in banks:
                option = bank.get_option(installment_number)
                if option:
                    return option

            logger.warning(
                f"Installment option {installment_number} not available for "
                f"BIN {bin_number}, amount {amount}"
            )
            return None

        except Exception as e:
            logger.error(f"Error validating installment option: {e}")
            return None

    def get_best_installment_options(
        self,
        bin_number: str,
        amount: Decimal,
        max_options: int = 5,
    ) -> List[InstallmentOption]:
        """
        Get the best installment options across all banks.

        Returns options sorted by installment number, prioritizing
        0% interest options.

        Args:
            bin_number: Card BIN
            amount: Payment amount
            max_options: Maximum number of options to return

        Returns:
            List of best InstallmentOption objects

        Example:
            >>> best_options = client.get_best_installment_options(
            ...     '554960',
            ...     Decimal('100.00'),
            ...     max_options=3,
            ... )
            >>> for opt in best_options:
            ...     print(f"{opt.installment_number}x - {opt.monthly_price}/month")
        """
        banks = self.get_installment_info(bin_number, amount)

        # Collect all unique installment options
        all_options: Dict[int, InstallmentOption] = {}

        for bank in banks:
            for option in bank.installment_options:
                number = option.installment_number

                # Prefer 0% interest options
                if number not in all_options or option.is_zero_interest:
                    all_options[number] = option

        # Sort by installment number
        sorted_options = sorted(all_options.values(), key=lambda x: x.installment_number)

        return sorted_options[:max_options]

    def calculate_installment_total(
        self,
        base_amount: Decimal,
        installment_number: int,
        installment_rate: Decimal,
    ) -> Dict[str, Decimal]:
        """
        Calculate installment payment breakdown.

        Args:
            base_amount: Base payment amount
            installment_number: Number of installments
            installment_rate: Fee rate as percentage

        Returns:
            Dictionary with payment breakdown

        Example:
            >>> breakdown = client.calculate_installment_total(
            ...     Decimal('100.00'),
            ...     3,
            ...     Decimal('3.00'),  # 3% fee
            ... )
            >>> print(f"Monthly: {breakdown['monthly_price']}")
        """
        # Calculate total with fees
        total_fee = base_amount * (installment_rate / 100)
        total_price = base_amount + total_fee

        # Calculate monthly payment
        monthly_price = total_price / installment_number

        return {
            "base_amount": base_amount,
            "installment_rate": installment_rate,
            "total_fee": total_fee,
            "total_price": total_price,
            "installment_number": installment_number,
            "monthly_price": monthly_price.quantize(Decimal("0.01")),
        }

    # Cache key tracking key name
    CACHE_KEYS_REGISTRY = "iyzico_installment_cache_keys"

    def _register_cache_key(self, cache_key: str) -> None:
        """
        Register a cache key for later cleanup.

        Args:
            cache_key: The cache key to register.
        """
        # Get current registered keys
        registered_keys = cache.get(self.CACHE_KEYS_REGISTRY) or set()
        if isinstance(registered_keys, list):
            registered_keys = set(registered_keys)
        registered_keys.add(cache_key)
        # Store with no expiry (or very long expiry)
        cache.set(self.CACHE_KEYS_REGISTRY, registered_keys, timeout=86400 * 7)  # 7 days

    def _unregister_cache_key(self, cache_key: str) -> None:
        """
        Unregister a cache key from the registry.

        Args:
            cache_key: The cache key to unregister.
        """
        registered_keys = cache.get(self.CACHE_KEYS_REGISTRY) or set()
        if isinstance(registered_keys, list):
            registered_keys = set(registered_keys)
        registered_keys.discard(cache_key)
        cache.set(self.CACHE_KEYS_REGISTRY, registered_keys, timeout=86400 * 7)

    def clear_cache(self, bin_number: Optional[str] = None) -> int:
        """
        Clear cached installment data safely without using cache patterns.

        This method uses explicit key tracking instead of pattern-based deletion
        to prevent potential cache injection vulnerabilities.

        Args:
            bin_number: Optional BIN to clear. If None, clears all registered keys.

        Returns:
            Number of cache keys deleted.
        """
        deleted_count = 0

        if bin_number:
            # Validate BIN to prevent any injection attempts
            if not bin_number.isdigit() or len(bin_number) != 6:
                logger.warning(f"Invalid BIN format for cache clear: {bin_number}")
                return 0

            # Clear specific BIN - iterate through common amount values
            # This is safer than pattern matching
            common_amounts = [
                "0.01",
                "1",
                "10",
                "50",
                "100",
                "200",
                "500",
                "1000",
                "2000",
                "5000",
                "10000",
                "25000",
                "50000",
                "100000",
            ]
            for amount in common_amounts:
                cache_key = f"iyzico_installments_{bin_number}_{amount}"
                if cache.delete(cache_key):
                    self._unregister_cache_key(cache_key)
                    deleted_count += 1

            logger.info(f"Cleared {deleted_count} cache entries for BIN {bin_number}")

        else:
            # Clear all registered installment cache keys
            registered_keys = cache.get(self.CACHE_KEYS_REGISTRY) or set()
            if isinstance(registered_keys, list):
                registered_keys = set(registered_keys)

            for key in list(registered_keys):
                # Only delete keys that match our expected pattern
                if key.startswith("iyzico_installments_"):
                    if cache.delete(key):
                        deleted_count += 1

            # Clear the registry itself
            cache.delete(self.CACHE_KEYS_REGISTRY)
            logger.info(f"Cleared {deleted_count} total installment cache entries")

        return deleted_count


def get_installment_display(
    installment_number: int,
    monthly_price: Decimal,
    total_price: Decimal,
    base_price: Decimal,
) -> str:
    """
    Format installment option for display.

    Args:
        installment_number: Number of installments
        monthly_price: Price per month
        total_price: Total price with fees
        base_price: Original price

    Returns:
        Formatted display string

    Example:
        >>> display = get_installment_display(3, Decimal('34.33'), Decimal('103.00'), Decimal('100.00'))
        >>> print(display)
        '3x 34.33 TL (Total: 103.00 TL +3.00 TL fee)'
    """
    fee = total_price - base_price

    if fee == 0:
        return f"{installment_number}x {monthly_price} TL (0% Interest)"
    else:
        return (
            f"{installment_number}x {monthly_price} TL " f"(Total: {total_price} TL +{fee} TL fee)"
        )
