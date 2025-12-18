"""
Utility functions for django-iyzico.

Contains helper functions for payment processing, data validation, card masking,
and data transformation.
"""

import hashlib
import hmac
import ipaddress
import logging
import time
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from .exceptions import ValidationError

logger = logging.getLogger(__name__)


# Comprehensive list of sensitive field names to mask/remove
SENSITIVE_CARD_FIELDS = frozenset(
    {
        # Card numbers
        "cardNumber",
        "card_number",
        "number",
        "cardNo",
        "card_no",
        "pan",
        "PAN",
        "primaryAccountNumber",
        # Security codes
        "cvc",
        "cvv",
        "cvv2",
        "cvc2",
        "securityCode",
        "security_code",
        "cid",
        "CID",
        "cardSecurityCode",
        "card_security_code",
        # Expiry dates
        "expireMonth",
        "expire_month",
        "expiryMonth",
        "expiry_month",
        "expireYear",
        "expire_year",
        "expiryYear",
        "expiry_year",
        "expiry",
        "expirationDate",
        "expiration_date",
        "exp",
        # PIN and passwords
        "pin",
        "PIN",
        "password",
        "passwd",
        # Tokens (might need to keep for recurring payments, handle carefully)
        # 'cardToken' - NOT in this list as it may be needed
    }
)

# Fields that are safe to keep (non-sensitive)
SAFE_CARD_FIELDS = frozenset(
    {
        "cardType",
        "card_type",
        "cardFamily",
        "card_family",
        "cardAssociation",
        "card_association",
        "cardBankName",
        "card_bank_name",
        "cardBankCode",
        "card_bank_code",
        "cardHolderName",
        "holderName",
        "lastFourDigits",
        "last_four",
        "binNumber",
        "bin_number",
        "cardToken",
        "cardUserKey",  # Tokens are safe (references, not actual data)
    }
)


def mask_card_data(payment_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive card data before storage (PCI DSS compliance).

    This function comprehensively masks all sensitive payment card data
    to ensure PCI DSS compliance. It handles various field naming conventions
    used by different payment systems.

    Keeps only:
    - Last 4 digits of card number
    - Cardholder name
    - Card metadata (type, family, association)
    - BIN number (first 6 digits - not sensitive)
    - Card tokens (secure references)

    Removes:
    - Full card number
    - CVC/CVV/Security codes
    - Full expiry dates
    - PIN numbers

    Args:
        payment_details: Dictionary containing card and payment information

    Returns:
        Dictionary with sensitive data removed/masked

    Example:
        >>> payment = {
        ...     'card': {
        ...         'cardNumber': '5528790000000008',
        ...         'cvc': '123',
        ...         'expireMonth': '12',
        ...         'expireYear': '2030'
        ...     }
        ... }
        >>> safe = mask_card_data(payment)
        >>> safe['card']['lastFourDigits']
        '0008'
        >>> 'cardNumber' in safe['card']
        False
        >>> 'cvc' in safe['card']
        False
    """
    if not isinstance(payment_details, dict):
        logger.warning("mask_card_data received non-dict input")
        return {}

    safe_data = _mask_dict_recursive(payment_details)

    # Handle the 'card' key specially
    if "card" in safe_data and isinstance(safe_data["card"], dict):
        card = payment_details.get("card", {})  # Get original card data

        # Extract card number from various possible field names
        card_number = ""
        for field in ["cardNumber", "card_number", "number", "pan"]:
            if field in card:
                card_number = str(card[field])
                break

        # Extract last 4 digits
        if len(card_number) >= 4:
            last_four = card_number[-4:]
        else:
            last_four = card_number if card_number.isdigit() else ""

        # Extract BIN (first 6 digits) - this is not sensitive
        bin_number = ""
        if len(card_number) >= 6:
            bin_number = card_number[:6]

        # Build safe card data
        safe_card = {
            "lastFourDigits": last_four,
            "binNumber": bin_number,
        }

        # Copy safe fields from original
        for field in SAFE_CARD_FIELDS:
            if field in card:
                safe_card[field] = card[field]

        # Get cardholder name from various possible fields
        holder_name = (
            card.get("cardHolderName")
            or card.get("holderName")
            or card.get("card_holder_name")
            or card.get("name")
            or ""
        )
        if holder_name:
            safe_card["cardHolderName"] = holder_name

        safe_data["card"] = safe_card

        # Log masking activity
        if last_four:
            logger.debug(f"Masked card data - BIN: {bin_number[:2]}****, Last 4: {last_four}")

    # Handle 'paymentCard' key (Iyzico SDK format)
    if "paymentCard" in safe_data:
        safe_data["paymentCard"] = _mask_dict_recursive(safe_data["paymentCard"])

    return safe_data


def _mask_dict_recursive(data: Any) -> Any:
    """
    Recursively mask sensitive fields in a dictionary.

    Args:
        data: Dictionary or other value to mask.

    Returns:
        Masked data with sensitive fields replaced with '***REDACTED***'.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in SENSITIVE_CARD_FIELDS:
                # Replace sensitive data
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = _mask_dict_recursive(value)
            elif isinstance(value, list):
                result[key] = [_mask_dict_recursive(item) for item in value]
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return [_mask_dict_recursive(item) for item in data]
    else:
        return data


# Currency-specific validation limits
# These prevent potentially fraudulent or erroneous transactions
CURRENCY_LIMITS: Dict[str, Dict[str, Decimal]] = {
    "TRY": {
        "min": Decimal("0.01"),
        "max": Decimal("1000000.00"),  # 1 million TRY
    },
    "USD": {
        "min": Decimal("0.01"),
        "max": Decimal("50000.00"),  # 50k USD
    },
    "EUR": {
        "min": Decimal("0.01"),
        "max": Decimal("50000.00"),  # 50k EUR
    },
    "GBP": {
        "min": Decimal("0.01"),
        "max": Decimal("50000.00"),  # 50k GBP
    },
    # Default limits for other currencies
    "DEFAULT": {
        "min": Decimal("0.01"),
        "max": Decimal("100000.00"),  # 100k default
    },
}


def validate_amount(
    amount: Any,
    currency: str = "TRY",
    custom_max: Optional[Decimal] = None,
) -> Decimal:
    """
    Validate and convert payment amount to Decimal with currency-specific limits.

    This function ensures amounts are within acceptable ranges to prevent:
    - Accidental high-value transactions
    - Potential fraud attempts
    - Micro-transaction spam

    Args:
        amount: Amount to validate (can be str, int, float, Decimal)
        currency: Currency code (default: TRY)
        custom_max: Optional custom maximum amount (overrides currency default)

    Returns:
        Validated Decimal amount

    Raises:
        ValidationError: If amount is invalid, too low, or too high

    Example:
        >>> validate_amount("100.50")
        Decimal('100.50')
        >>> validate_amount(0)
        Traceback (most recent call last):
        ...
        ValidationError: Amount must be greater than zero
        >>> validate_amount("999999999")
        Traceback (most recent call last):
        ...
        ValidationError: Amount exceeds maximum allowed for TRY
    """
    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid amount format: {amount}",
            error_code="INVALID_AMOUNT_FORMAT",
        ) from e

    # Validate amount is positive
    if decimal_amount <= 0:
        raise ValidationError(
            "Amount must be greater than zero",
            error_code="INVALID_AMOUNT",
        )

    # Validate decimal places (max 2 for most currencies)
    if decimal_amount.as_tuple().exponent < -2:
        raise ValidationError(
            "Amount cannot have more than 2 decimal places",
            error_code="INVALID_AMOUNT_PRECISION",
        )

    # Get currency-specific limits
    currency_upper = currency.upper()
    limits = CURRENCY_LIMITS.get(currency_upper, CURRENCY_LIMITS["DEFAULT"])
    min_amount = limits["min"]
    max_amount = custom_max if custom_max is not None else limits["max"]

    # Check minimum amount
    if decimal_amount < min_amount:
        raise ValidationError(
            f"Amount must be at least {min_amount} {currency_upper}",
            error_code="AMOUNT_TOO_LOW",
        )

    # Check maximum amount
    if decimal_amount > max_amount:
        raise ValidationError(
            f"Amount exceeds maximum allowed for {currency_upper} ({max_amount}). "
            f"If this is intentional, contact support for approval.",
            error_code="AMOUNT_TOO_HIGH",
        )

    # Log validation for high-value transactions (for monitoring)
    warning_threshold = max_amount * Decimal("0.5")  # 50% of max
    if decimal_amount > warning_threshold:
        logger.info(
            f"High-value amount validation: {decimal_amount} {currency_upper} "
            f"(above 50% of {max_amount} limit)"
        )

    logger.debug(f"Validated amount: {decimal_amount} {currency_upper}")
    return decimal_amount


def get_currency_limits(currency: str) -> Dict[str, Decimal]:
    """
    Get the validation limits for a specific currency.

    Args:
        currency: Currency code (e.g., 'TRY', 'USD', 'EUR')

    Returns:
        Dictionary with 'min' and 'max' Decimal values

    Example:
        >>> limits = get_currency_limits('USD')
        >>> limits['max']
        Decimal('50000.00')
    """
    currency_upper = currency.upper()
    return CURRENCY_LIMITS.get(currency_upper, CURRENCY_LIMITS["DEFAULT"]).copy()


def validate_payment_data(payment_data: Dict[str, Any]) -> None:
    """
    Validate payment request data before sending to Iyzico.

    Args:
        payment_data: Payment data dictionary

    Raises:
        ValidationError: If validation fails

    Example:
        >>> data = {'price': '100', 'paidPrice': '100', 'currency': 'TRY'}
        >>> validate_payment_data(data)
        >>> # No exception means validation passed
    """
    if not isinstance(payment_data, dict):
        raise ValidationError(
            "Payment data must be a dictionary",
            error_code="INVALID_DATA_TYPE",
        )

    # Required fields
    required_fields = ["price", "paidPrice", "currency"]
    missing_fields = [f for f in required_fields if f not in payment_data]

    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            error_code="MISSING_REQUIRED_FIELDS",
        )

    # Validate amounts
    try:
        price = validate_amount(payment_data["price"], payment_data["currency"])
        paid_price = validate_amount(payment_data["paidPrice"], payment_data["currency"])

        # paidPrice should typically be >= price (can be higher with installments)
        if paid_price < price:
            logger.warning(f"Paid price ({paid_price}) is less than price ({price})")

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(
            f"Amount validation failed: {str(e)}",
            error_code="AMOUNT_VALIDATION_ERROR",
        ) from e

    logger.debug("Payment data validation passed")


def format_price(amount: Any) -> str:
    """
    Format amount for Iyzico API (string with 2 decimal places).

    Args:
        amount: Amount to format

    Returns:
        Formatted price string

    Example:
        >>> format_price(100)
        '100.00'
        >>> format_price(Decimal('99.9'))
        '99.90'
        >>> format_price('150.5')
        '150.50'
    """
    try:
        decimal_amount = Decimal(str(amount))
        # Format with exactly 2 decimal places
        return f"{decimal_amount:.2f}"
    except (InvalidOperation, ValueError, TypeError):
        logger.error(f"Failed to format price: {amount}")
        return "0.00"


def generate_conversation_id(prefix: str = "") -> str:
    """
    Generate unique conversation ID for Iyzico request.

    Args:
        prefix: Optional prefix for the conversation ID

    Returns:
        Unique conversation ID

    Example:
        >>> cid = generate_conversation_id("order")
        >>> cid.startswith("order-")
        True
        >>> len(cid) > 10
        True
    """
    unique_id = str(uuid.uuid4())
    if prefix:
        return f"{prefix}-{unique_id}"
    return unique_id


def parse_iyzico_response(raw_response: Any) -> Dict[str, Any]:
    """
    Parse Iyzico API response (handles both bytes and dict).

    The iyzipay SDK sometimes returns bytes, sometimes dict.
    This normalizes to dict.

    Args:
        raw_response: Response from iyzipay SDK

    Returns:
        Parsed response dictionary

    Example:
        >>> parse_iyzico_response({'status': 'success'})
        {'status': 'success'}
        >>> import json
        >>> parse_iyzico_response(json.dumps({'status': 'success'}).encode())
        {'status': 'success'}
    """
    if isinstance(raw_response, dict):
        return raw_response

    if isinstance(raw_response, bytes):
        import json

        try:
            return json.loads(raw_response.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to parse bytes response: {e}")
            return {"error": "Failed to parse response", "status": "failure"}

    if isinstance(raw_response, str):
        import json

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse string response: {e}")
            return {"error": "Failed to parse response", "status": "failure"}

    # Unknown type
    logger.error(f"Unknown response type: {type(raw_response)}")
    return {"error": "Unknown response type", "status": "failure"}


def extract_card_info(payment_response: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract safe card information from Iyzico payment response.

    Args:
        payment_response: Response from Iyzico API

    Returns:
        Dictionary with safe card information

    Example:
        >>> response = {
        ...     'cardType': 'CREDIT_CARD',
        ...     'cardAssociation': 'MASTER_CARD',
        ...     'cardFamily': 'Bonus'
        ... }
        >>> info = extract_card_info(response)
        >>> info['cardType']
        'CREDIT_CARD'
    """
    if not isinstance(payment_response, dict):
        return {}

    return {
        "cardType": payment_response.get("cardType", ""),
        "cardAssociation": payment_response.get("cardAssociation", ""),
        "cardFamily": payment_response.get("cardFamily", ""),
        "cardBankName": payment_response.get("cardBankName", ""),
        "cardBankCode": payment_response.get("cardBankCode", ""),
    }


def format_buyer_data(buyer: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format buyer data for Iyzico API.

    Ensures all required fields are present and properly formatted.

    Args:
        buyer: Buyer information dictionary

    Returns:
        Formatted buyer data

    Raises:
        ValidationError: If required buyer fields are missing
    """
    required_fields = [
        "id",
        "name",
        "surname",
        "email",
        "identityNumber",
        "registrationAddress",
        "city",
        "country",
    ]

    missing_fields = [f for f in required_fields if not buyer.get(f)]
    if missing_fields:
        raise ValidationError(
            f"Missing required buyer fields: {', '.join(missing_fields)}",
            error_code="MISSING_BUYER_FIELDS",
        )

    # Format phone number (ensure it starts with +)
    gsm_number = buyer.get("gsmNumber", "")
    if gsm_number and not gsm_number.startswith("+"):
        gsm_number = f"+{gsm_number}"

    return {
        "id": str(buyer["id"]),
        "name": buyer["name"],
        "surname": buyer["surname"],
        "gsmNumber": gsm_number,
        "email": buyer["email"],
        "identityNumber": buyer["identityNumber"],
        "registrationAddress": buyer["registrationAddress"],
        "city": buyer["city"],
        "country": buyer["country"],
        "zipCode": buyer.get("zipCode", ""),
    }


def format_address_data(
    address: Dict[str, Any], contact_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format address data for Iyzico API.

    Args:
        address: Address information dictionary
        contact_name: Contact name for the address

    Returns:
        Formatted address data

    Raises:
        ValidationError: If required address fields are missing
    """
    required_fields = ["address", "city", "country"]

    missing_fields = [f for f in required_fields if not address.get(f)]
    if missing_fields:
        raise ValidationError(
            f"Missing required address fields: {', '.join(missing_fields)}",
            error_code="MISSING_ADDRESS_FIELDS",
        )

    return {
        "contactName": contact_name or address.get("contactName", ""),
        "city": address["city"],
        "country": address["country"],
        "address": address["address"],
        "zipCode": address.get("zipCode", ""),
    }


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize data for logging (remove sensitive information).

    Args:
        data: Data to sanitize

    Returns:
        Sanitized data safe for logging
    """
    if not isinstance(data, dict):
        return {}

    sanitized = data.copy()

    # Remove sensitive fields
    sensitive_fields = [
        "cardNumber",
        "number",
        "cvc",
        "cvv",
        "securityCode",
        "expireMonth",
        "expireYear",
        "expiryMonth",
        "expiryYear",
        "api_key",
        "secret_key",
        "apiKey",
        "secretKey",
    ]

    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = "***REDACTED***"

    # Recursively sanitize nested dicts
    for key, value in sanitized.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_log_data(item) if isinstance(item, dict) else item for item in value
            ]

    return sanitized


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook HMAC-SHA256 signature.

    Args:
        payload: Raw request body as bytes
        signature: Signature from request header
        secret: Webhook secret key

    Returns:
        True if signature is valid, False otherwise

    Example:
        >>> import hashlib
        >>> import hmac
        >>> payload = b'{"event": "payment.success"}'
        >>> secret = "my-secret-key"
        >>> sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        >>> verify_webhook_signature(payload, sig, secret)
        True
        >>> verify_webhook_signature(payload, "invalid", secret)
        False
    """
    if not secret:
        # If no secret is configured, skip validation
        logger.warning("Webhook secret not configured, skipping signature validation")
        return True

    if not signature:
        logger.warning("Webhook signature missing")
        return False

    try:
        # Compute expected signature
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(signature, expected)

        if not is_valid:
            logger.warning("Webhook signature mismatch")

        return is_valid

    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


def is_ip_allowed(ip_address: str, allowed_ips: List[str]) -> bool:
    """
    Check if IP address is in whitelist.

    Supports both individual IPs and CIDR notation.

    Args:
        ip_address: IP address to check
        allowed_ips: List of allowed IP addresses/ranges

    Returns:
        True if IP is allowed, False otherwise

    Example:
        >>> is_ip_allowed("127.0.0.1", ["127.0.0.1", "192.168.1.0/24"])
        True
        >>> is_ip_allowed("10.0.0.1", ["127.0.0.1"])
        False
        >>> is_ip_allowed("192.168.1.50", ["192.168.1.0/24"])
        True
    """
    if not allowed_ips:
        # If no IP whitelist is configured, allow all
        logger.debug("No IP whitelist configured, allowing all IPs")
        return True

    try:
        ip = ipaddress.ip_address(ip_address)

        for allowed in allowed_ips:
            try:
                # Try as network (CIDR)
                if "/" in allowed:
                    network = ipaddress.ip_network(allowed, strict=False)
                    if ip in network:
                        logger.debug(f"IP {ip_address} allowed by network {allowed}")
                        return True
                # Try as individual IP
                else:
                    if ip == ipaddress.ip_address(allowed):
                        logger.debug(f"IP {ip_address} allowed")
                        return True
            except ValueError as e:
                logger.warning(f"Invalid IP/network in whitelist: {allowed} - {e}")
                continue

        logger.warning(f"IP {ip_address} not in whitelist")
        return False

    except ValueError as e:
        logger.error(f"Invalid IP address: {ip_address} - {e}")
        return False


def calculate_installment_amount(
    total_amount: Decimal,
    installments: int,
    interest_rate: Decimal = Decimal("0"),
) -> Decimal:
    """
    Calculate monthly installment amount.

    Args:
        total_amount: Total payment amount
        installments: Number of installments
        interest_rate: Interest rate per installment as percentage (default: 0)

    Returns:
        Monthly installment amount (rounded to 2 decimal places)

    Raises:
        ValidationError: If parameters are invalid

    Example:
        >>> calculate_installment_amount(Decimal("1000"), 1)
        Decimal('1000.00')
        >>> calculate_installment_amount(Decimal("1000"), 10)
        Decimal('100.00')
        >>> calculate_installment_amount(Decimal("1000"), 10, Decimal("2"))
        Decimal('120.00')
    """
    # Validate inputs
    if total_amount <= 0:
        raise ValidationError(
            "Total amount must be greater than zero",
            error_code="INVALID_AMOUNT",
        )

    if installments < 1:
        raise ValidationError(
            "Installments must be at least 1",
            error_code="INVALID_INSTALLMENTS",
        )

    if interest_rate < 0:
        raise ValidationError(
            "Interest rate cannot be negative",
            error_code="INVALID_INTEREST_RATE",
        )

    # Single payment (no installments)
    if installments == 1:
        return total_amount.quantize(Decimal("0.01"))

    # Calculate with interest
    if interest_rate > 0:
        # Convert percentage to decimal (e.g., 2% -> 0.02)
        rate_decimal = interest_rate / 100
        # Calculate total with interest: total + (total * rate * installments)
        total_with_interest = total_amount * (1 + rate_decimal * installments)
        monthly_amount = total_with_interest / installments
    else:
        # Without interest, simply divide
        monthly_amount = total_amount / installments

    return monthly_amount.quantize(Decimal("0.01"))


def generate_basket_id(prefix: str = "B") -> str:
    """
    Generate unique basket ID for transactions.

    Args:
        prefix: Prefix for basket ID (default: "B")

    Returns:
        Unique basket ID in format: {prefix}{timestamp}{uuid}

    Example:
        >>> basket_id = generate_basket_id("B")
        >>> basket_id.startswith("B")
        True
        >>> len(basket_id) > 10
        True
        >>> basket_id1 = generate_basket_id()
        >>> basket_id2 = generate_basket_id()
        >>> basket_id1 != basket_id2
        True
    """
    if not prefix:
        prefix = "B"

    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8].upper()

    return f"{prefix}{timestamp}{unique_id}"


def calculate_paid_price_with_installments(
    base_price: Decimal,
    installments: int,
    installment_rates: Optional[Dict[int, Decimal]] = None,
) -> Decimal:
    """
    Calculate total paid price including installment fees.

    Args:
        base_price: Base payment amount
        installments: Number of installments
        installment_rates: Dictionary mapping installments to interest rates
                          (e.g., {3: Decimal("1.5"), 6: Decimal("2.0")})

    Returns:
        Total paid price with installment fees

    Example:
        >>> rates = {3: Decimal("1.5"), 6: Decimal("2.0")}
        >>> calculate_paid_price_with_installments(Decimal("1000"), 1, rates)
        Decimal('1000.00')
        >>> calculate_paid_price_with_installments(Decimal("1000"), 3, rates)
        Decimal('1045.00')
        >>> calculate_paid_price_with_installments(Decimal("1000"), 6, rates)
        Decimal('1120.00')
    """
    if installments <= 1:
        return base_price.quantize(Decimal("0.01"))

    if not installment_rates or installments not in installment_rates:
        # No interest rate defined, return base price
        return base_price.quantize(Decimal("0.01"))

    # Get interest rate for this installment count
    rate = installment_rates[installments]

    # Calculate total: base_price * (1 + rate/100 * installments)
    total = base_price * (1 + (rate / 100) * installments)

    return total.quantize(Decimal("0.01"))


def get_client_ip(request, trust_xff: Optional[bool] = None) -> str:
    """
    Get client IP address from Django request.

    This is the centralized IP extraction function that respects the
    IYZICO_TRUST_X_FORWARDED_FOR setting. All code in the package
    should use this function for consistent security behavior.

    Args:
        request: Django HttpRequest object
        trust_xff: Whether to trust X-Forwarded-For header.
                   If None, uses iyzico_settings.trust_x_forwarded_for.
                   Set to False to always use REMOTE_ADDR.

    Returns:
        Client IP address string (empty string if not available)

    Security Note:
        Only set trust_xff=True if your application is behind a trusted
        reverse proxy that properly sets the X-Forwarded-For header.
        Otherwise, attackers can spoof their IP address.

    Example:
        >>> from django_iyzico.utils import get_client_ip
        >>> ip = get_client_ip(request)
        >>> refund_response = payment.process_refund(ip_address=ip)
    """
    from .settings import iyzico_settings

    if trust_xff is None:
        trust_xff = iyzico_settings.trust_x_forwarded_for

    if trust_xff:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Take the first IP in the chain (client IP)
            ip = x_forwarded_for.split(",")[0].strip()
            return ip

    return request.META.get("REMOTE_ADDR", "")
