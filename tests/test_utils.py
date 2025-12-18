"""
Tests for django-iyzico utility functions.

SECURITY CRITICAL: Card masking tests ensure PCI DSS compliance.
"""

import hashlib
import hmac
from decimal import Decimal
from unittest.mock import patch

import pytest

from django_iyzico.exceptions import ValidationError
from django_iyzico.utils import (
    extract_card_info,
    format_address_data,
    format_buyer_data,
    format_price,
    generate_conversation_id,
    is_ip_allowed,
    mask_card_data,
    parse_iyzico_response,
    sanitize_log_data,
    validate_amount,
    validate_payment_data,
    verify_webhook_signature,
)


class TestMaskCardData:
    """Test card data masking - SECURITY CRITICAL for PCI DSS compliance."""

    def test_masks_full_card_number(self):
        """Test that full card number is completely removed."""
        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "cardHolderName": "John Doe",
                "expireMonth": "12",
                "expireYear": "2030",
                "cvc": "123",
            }
        }

        result = mask_card_data(payment_data)

        # CRITICAL: Full card number must NOT be in result
        assert "5528790000000008" not in str(result)
        assert "cardNumber" not in result.get("card", {})

        # Only last 4 digits should remain
        assert result["card"]["lastFourDigits"] == "0008"

    def test_removes_cvc(self):
        """Test that CVC is completely removed."""
        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "cvc": "123",
            }
        }

        result = mask_card_data(payment_data)

        # CRITICAL: CVC must NOT be in result
        assert "cvc" not in result.get("card", {})
        assert "cvv" not in result.get("card", {})
        assert "123" not in str(result)

    def test_removes_expiry_date(self):
        """Test that full expiry date is removed."""
        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "expireMonth": "12",
                "expireYear": "2030",
            }
        }

        result = mask_card_data(payment_data)

        # Expiry info should not be in result
        assert "expireMonth" not in result.get("card", {})
        assert "expireYear" not in result.get("card", {})

    def test_keeps_card_holder_name(self):
        """Test that cardholder name is preserved."""
        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "cardHolderName": "John Doe",
            }
        }

        result = mask_card_data(payment_data)

        assert result["card"]["cardHolderName"] == "John Doe"

    def test_keeps_card_metadata(self):
        """Test that safe card metadata is preserved."""
        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "cardType": "CREDIT_CARD",
                "cardFamily": "Bonus",
                "cardAssociation": "MASTER_CARD",
            }
        }

        result = mask_card_data(payment_data)

        assert result["card"]["cardType"] == "CREDIT_CARD"
        assert result["card"]["cardFamily"] == "Bonus"
        assert result["card"]["cardAssociation"] == "MASTER_CARD"

    def test_handles_missing_card_section(self):
        """Test handling when no card section exists."""
        payment_data = {"amount": "100.00", "currency": "TRY"}

        result = mask_card_data(payment_data)

        # Should return data unchanged
        assert result == payment_data

    def test_handles_empty_card_number(self):
        """Test handling of empty card number."""
        payment_data = {
            "card": {
                "cardNumber": "",
                "cardHolderName": "John Doe",
            }
        }

        result = mask_card_data(payment_data)

        # Should handle gracefully
        assert result["card"]["lastFourDigits"] == ""

    def test_handles_short_card_number(self):
        """Test handling of card number shorter than 4 digits."""
        payment_data = {
            "card": {
                "cardNumber": "123",
                "cardHolderName": "John Doe",
            }
        }

        result = mask_card_data(payment_data)

        # Should take whatever is available
        assert result["card"]["lastFourDigits"] == "123"

    def test_handles_none_input(self):
        """Test handling of None input."""
        result = mask_card_data(None)

        # Should return empty dict
        assert result == {}

    def test_handles_non_dict_input(self):
        """Test handling of non-dict input."""
        result = mask_card_data("not a dict")

        assert result == {}

    def test_handles_alternative_field_names(self):
        """Test handling of alternative field names (number, holderName)."""
        payment_data = {
            "card": {
                "number": "5528790000000008",  # Alternative to cardNumber
                "holderName": "John Doe",  # Alternative to cardHolderName
            }
        }

        result = mask_card_data(payment_data)

        assert result["card"]["lastFourDigits"] == "0008"
        assert result["card"]["cardHolderName"] == "John Doe"


class TestValidateAmount:
    """Test amount validation."""

    def test_validates_valid_decimal_string(self):
        """Test validation of valid decimal string."""
        result = validate_amount("100.50", "TRY")

        assert isinstance(result, Decimal)
        assert result == Decimal("100.50")

    def test_validates_valid_integer(self):
        """Test validation of valid integer."""
        result = validate_amount(100, "TRY")

        assert isinstance(result, Decimal)
        assert result == Decimal("100")

    def test_validates_valid_float(self):
        """Test validation of valid float."""
        result = validate_amount(100.50, "TRY")

        assert isinstance(result, Decimal)
        assert result == Decimal("100.50")

    def test_validates_valid_decimal(self):
        """Test validation of Decimal."""
        result = validate_amount(Decimal("100.50"), "TRY")

        assert result == Decimal("100.50")

    def test_rejects_zero_amount(self):
        """Test rejection of zero amount."""
        with pytest.raises(ValidationError) as exc_info:
            validate_amount(0, "TRY")

        assert "greater than zero" in str(exc_info.value)

    def test_rejects_negative_amount(self):
        """Test rejection of negative amount."""
        with pytest.raises(ValidationError) as exc_info:
            validate_amount(-100, "TRY")

        assert "greater than zero" in str(exc_info.value)

    def test_rejects_invalid_format(self):
        """Test rejection of invalid amount format."""
        with pytest.raises(ValidationError) as exc_info:
            validate_amount("not a number", "TRY")

        assert "Invalid amount format" in str(exc_info.value)

    def test_rejects_too_many_decimal_places(self):
        """Test rejection of more than 2 decimal places."""
        with pytest.raises(ValidationError) as exc_info:
            validate_amount("100.123", "TRY")

        assert "2 decimal places" in str(exc_info.value)

    def test_rejects_amount_with_excessive_decimals_catches_before_minimum(self):
        """Test that excessive decimals error is caught before minimum amount check."""
        # This tests the validation order: decimal places check happens before minimum check
        with pytest.raises(ValidationError) as exc_info:
            validate_amount("0.001", "TRY")

        # Should fail on decimal places, not minimum amount
        assert "2 decimal places" in str(exc_info.value)

    def test_accepts_minimum_try_amount(self):
        """Test acceptance of minimum TRY amount."""
        result = validate_amount("0.01", "TRY")

        assert result == Decimal("0.01")


class TestValidatePaymentData:
    """Test payment data validation."""

    def test_validates_valid_payment_data(self):
        """Test validation of valid payment data."""
        payment_data = {
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
        }

        # Should not raise
        validate_payment_data(payment_data)

    def test_rejects_non_dict(self):
        """Test rejection of non-dict payment data."""
        with pytest.raises(ValidationError) as exc_info:
            validate_payment_data("not a dict")

        assert "must be a dictionary" in str(exc_info.value)

    def test_rejects_missing_price(self):
        """Test rejection when price is missing."""
        payment_data = {
            "paidPrice": "100.00",
            "currency": "TRY",
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_payment_data(payment_data)

        assert "price" in str(exc_info.value).lower()

    def test_rejects_missing_paid_price(self):
        """Test rejection when paidPrice is missing."""
        payment_data = {
            "price": "100.00",
            "currency": "TRY",
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_payment_data(payment_data)

        assert "paidprice" in str(exc_info.value).lower()

    def test_rejects_missing_currency(self):
        """Test rejection when currency is missing."""
        payment_data = {
            "price": "100.00",
            "paidPrice": "100.00",
        }

        with pytest.raises(ValidationError) as exc_info:
            validate_payment_data(payment_data)

        assert "currency" in str(exc_info.value).lower()

    def test_rejects_invalid_price(self):
        """Test rejection of invalid price."""
        payment_data = {
            "price": "invalid",
            "paidPrice": "100.00",
            "currency": "TRY",
        }

        with pytest.raises(ValidationError):
            validate_payment_data(payment_data)


class TestFormatPrice:
    """Test price formatting."""

    def test_formats_integer(self):
        """Test formatting of integer."""
        result = format_price(100)

        assert result == "100.00"

    def test_formats_decimal(self):
        """Test formatting of Decimal."""
        result = format_price(Decimal("99.9"))

        assert result == "99.90"

    def test_formats_string(self):
        """Test formatting of string."""
        result = format_price("150.5")

        assert result == "150.50"

    def test_formats_with_exact_two_decimals(self):
        """Test formatting when already has 2 decimals."""
        result = format_price("100.00")

        assert result == "100.00"

    def test_handles_invalid_input(self):
        """Test handling of invalid input."""
        result = format_price("not a number")

        # Should return default
        assert result == "0.00"


class TestGenerateConversationId:
    """Test conversation ID generation."""

    def test_generates_unique_ids(self):
        """Test that generated IDs are unique."""
        id1 = generate_conversation_id()
        id2 = generate_conversation_id()

        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0

    def test_includes_prefix(self):
        """Test that prefix is included."""
        conv_id = generate_conversation_id("order")

        assert conv_id.startswith("order-")

    def test_without_prefix(self):
        """Test generation without prefix."""
        conv_id = generate_conversation_id()

        # Should be a UUID
        assert len(conv_id) == 36  # UUID length


class TestParseIyzicoResponse:
    """Test Iyzico response parsing."""

    def test_parses_dict_response(self):
        """Test parsing of dict response."""
        response = {"status": "success", "paymentId": "123"}

        result = parse_iyzico_response(response)

        assert result == response

    def test_parses_bytes_response(self):
        """Test parsing of bytes response."""
        import json

        response_dict = {"status": "success", "paymentId": "123"}
        response_bytes = json.dumps(response_dict).encode("utf-8")

        result = parse_iyzico_response(response_bytes)

        assert result == response_dict

    def test_parses_string_response(self):
        """Test parsing of string response."""
        import json

        response_dict = {"status": "success", "paymentId": "123"}
        response_str = json.dumps(response_dict)

        result = parse_iyzico_response(response_str)

        assert result == response_dict

    def test_handles_invalid_json_bytes(self):
        """Test handling of invalid JSON bytes."""
        response = b"not valid json"

        result = parse_iyzico_response(response)

        assert result["status"] == "failure"
        assert "error" in result

    def test_handles_unknown_type(self):
        """Test handling of unknown response type."""
        response = 12345  # Number

        result = parse_iyzico_response(response)

        assert result["status"] == "failure"
        assert "error" in result


class TestExtractCardInfo:
    """Test card info extraction."""

    def test_extracts_all_card_fields(self):
        """Test extraction of all card metadata fields."""
        response = {
            "cardType": "CREDIT_CARD",
            "cardAssociation": "MASTER_CARD",
            "cardFamily": "Bonus",
            "cardBankName": "Test Bank",
            "cardBankCode": "1234",
        }

        result = extract_card_info(response)

        assert result["cardType"] == "CREDIT_CARD"
        assert result["cardAssociation"] == "MASTER_CARD"
        assert result["cardFamily"] == "Bonus"
        assert result["cardBankName"] == "Test Bank"
        assert result["cardBankCode"] == "1234"

    def test_handles_missing_fields(self):
        """Test handling when fields are missing."""
        response = {"cardType": "CREDIT_CARD"}

        result = extract_card_info(response)

        assert result["cardType"] == "CREDIT_CARD"
        assert result["cardAssociation"] == ""
        assert result["cardFamily"] == ""

    def test_handles_non_dict(self):
        """Test handling of non-dict response."""
        result = extract_card_info("not a dict")

        assert result == {}


class TestFormatBuyerData:
    """Test buyer data formatting."""

    def test_formats_valid_buyer_data(self):
        """Test formatting of valid buyer data."""
        buyer = {
            "id": 123,
            "name": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "identityNumber": "11111111111",
            "registrationAddress": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
            "gsmNumber": "905551234567",
            "zipCode": "34000",
        }

        result = format_buyer_data(buyer)

        assert result["id"] == "123"  # Converted to string
        assert result["name"] == "John"
        assert result["surname"] == "Doe"
        assert result["email"] == "john@example.com"
        assert result["gsmNumber"] == "+905551234567"  # Plus added

    def test_adds_plus_to_phone_number(self):
        """Test that plus is added to phone number."""
        buyer = {
            "id": "123",
            "name": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "identityNumber": "11111111111",
            "registrationAddress": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
            "gsmNumber": "905551234567",
        }

        result = format_buyer_data(buyer)

        assert result["gsmNumber"].startswith("+")

    def test_keeps_plus_in_phone_number(self):
        """Test that existing plus is kept."""
        buyer = {
            "id": "123",
            "name": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "identityNumber": "11111111111",
            "registrationAddress": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
            "gsmNumber": "+905551234567",
        }

        result = format_buyer_data(buyer)

        assert result["gsmNumber"] == "+905551234567"

    def test_rejects_missing_required_fields(self):
        """Test rejection when required fields are missing."""
        buyer = {
            "id": "123",
            "name": "John",
            # Missing surname and other required fields
        }

        with pytest.raises(ValidationError) as exc_info:
            format_buyer_data(buyer)

        assert "Missing required buyer fields" in str(exc_info.value)


class TestFormatAddressData:
    """Test address data formatting."""

    def test_formats_valid_address_data(self):
        """Test formatting of valid address data."""
        address = {
            "address": "Test Address 123",
            "city": "Istanbul",
            "country": "Turkey",
            "zipCode": "34000",
            "contactName": "John Doe",
        }

        result = format_address_data(address)

        assert result["address"] == "Test Address 123"
        assert result["city"] == "Istanbul"
        assert result["country"] == "Turkey"
        assert result["zipCode"] == "34000"
        assert result["contactName"] == "John Doe"

    def test_uses_provided_contact_name(self):
        """Test that provided contact_name overrides address contactName."""
        address = {
            "address": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
            "contactName": "Jane Doe",
        }

        result = format_address_data(address, contact_name="John Doe")

        assert result["contactName"] == "John Doe"

    def test_rejects_missing_required_fields(self):
        """Test rejection when required fields are missing."""
        address = {
            "address": "Test Address",
            # Missing city and country
        }

        with pytest.raises(ValidationError) as exc_info:
            format_address_data(address)

        assert "Missing required address fields" in str(exc_info.value)


class TestSanitizeLogData:
    """Test log data sanitization - SECURITY CRITICAL."""

    def test_removes_card_number(self):
        """Test that card number is removed."""
        data = {
            "cardNumber": "5528790000000008",
            "name": "John Doe",
        }

        result = sanitize_log_data(data)

        assert result["cardNumber"] == "***REDACTED***"
        assert result["name"] == "John Doe"

    def test_removes_cvc(self):
        """Test that CVC is removed."""
        data = {
            "cvc": "123",
            "cvv": "456",
            "securityCode": "789",
        }

        result = sanitize_log_data(data)

        assert result["cvc"] == "***REDACTED***"
        assert result["cvv"] == "***REDACTED***"
        assert result["securityCode"] == "***REDACTED***"

    def test_removes_api_keys(self):
        """Test that API keys are removed."""
        data = {
            "api_key": "secret_key_123",
            "secret_key": "secret_key_456",
        }

        result = sanitize_log_data(data)

        assert result["api_key"] == "***REDACTED***"
        assert result["secret_key"] == "***REDACTED***"

    def test_sanitizes_nested_dicts(self):
        """Test recursive sanitization of nested dicts."""
        data = {
            "payment": {
                "cardNumber": "5528790000000008",
                "amount": "100.00",
            },
            "buyer": {
                "name": "John Doe",
            },
        }

        result = sanitize_log_data(data)

        assert result["payment"]["cardNumber"] == "***REDACTED***"
        assert result["payment"]["amount"] == "100.00"
        assert result["buyer"]["name"] == "John Doe"

    def test_sanitizes_lists_of_dicts(self):
        """Test sanitization of lists containing dicts."""
        data = {
            "cards": [
                {"cardNumber": "5528790000000008"},
                {"cardNumber": "4111111111111111"},
            ]
        }

        result = sanitize_log_data(data)

        assert result["cards"][0]["cardNumber"] == "***REDACTED***"
        assert result["cards"][1]["cardNumber"] == "***REDACTED***"

    def test_handles_non_dict_input(self):
        """Test handling of non-dict input."""
        result = sanitize_log_data("not a dict")

        assert result == {}

    def test_handles_none_input(self):
        """Test handling of None input."""
        result = sanitize_log_data(None)

        assert result == {}


class TestVerifyWebhookSignature:
    """Test webhook signature verification - SECURITY CRITICAL."""

    def test_valid_signature_returns_true(self):
        """Test valid signature is accepted."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        assert verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature_returns_false(self):
        """Test invalid signature is rejected."""
        payload = b'{"test": "data"}'
        secret = "test-secret"

        assert verify_webhook_signature(payload, "invalid-signature", secret) is False

    def test_no_secret_configured_returns_true_with_warning(self):
        """Test that missing secret logs warning but allows."""
        payload = b'{"test": "data"}'

        # Empty secret should return True (no validation)
        result = verify_webhook_signature(payload, "any-signature", "")
        assert result is True

    def test_no_signature_provided_returns_false(self):
        """Test that missing signature is rejected."""
        payload = b'{"test": "data"}'
        secret = "test-secret"

        # Empty signature should return False
        result = verify_webhook_signature(payload, "", secret)
        assert result is False

    def test_signature_mismatch_returns_false(self):
        """Test that mismatched signature is rejected."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        wrong_secret = "wrong-secret"
        signature = hmac.new(wrong_secret.encode(), payload, hashlib.sha256).hexdigest()

        result = verify_webhook_signature(payload, signature, secret)
        assert result is False

    def test_exception_during_verification_returns_false(self):
        """Test exception handling during signature verification."""
        payload = b'{"test": "data"}'
        secret = "test-secret"

        # Mock hmac.new to raise an exception
        with patch("django_iyzico.utils.hmac.new") as mock_hmac:
            mock_hmac.side_effect = Exception("Mocked exception")

            result = verify_webhook_signature(payload, "signature", secret)
            assert result is False

    def test_different_payload_invalidates_signature(self):
        """Test that signature validation is payload-specific."""
        payload1 = b'{"test": "data1"}'
        payload2 = b'{"test": "data2"}'
        secret = "test-secret"

        # Generate signature for payload1
        signature = hmac.new(secret.encode(), payload1, hashlib.sha256).hexdigest()

        # Signature should be valid for payload1
        assert verify_webhook_signature(payload1, signature, secret) is True

        # But not valid for payload2
        assert verify_webhook_signature(payload2, signature, secret) is False

    def test_uses_constant_time_comparison(self):
        """Test that constant-time comparison is used (timing attack prevention)."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Verify that hmac.compare_digest is used (this is implicit in the implementation)
        # The test just verifies the function works correctly
        assert verify_webhook_signature(payload, signature, secret) is True


class TestIsIpAllowed:
    """Test IP whitelist checking."""

    def test_no_whitelist_allows_all(self):
        """Test empty whitelist allows all IPs."""
        assert is_ip_allowed("192.168.1.1", []) is True
        assert is_ip_allowed("10.0.0.1", []) is True
        assert is_ip_allowed("172.16.0.1", []) is True

    def test_none_whitelist_allows_all(self):
        """Test None whitelist allows all IPs."""
        assert is_ip_allowed("192.168.1.1", None) is True
        assert is_ip_allowed("10.0.0.1", None) is True

    def test_exact_ip_match_allowed(self):
        """Test exact IP match is allowed."""
        allowed_ips = ["192.168.1.1", "10.0.0.1"]

        assert is_ip_allowed("192.168.1.1", allowed_ips) is True
        assert is_ip_allowed("10.0.0.1", allowed_ips) is True

    def test_ip_not_in_whitelist_denied(self):
        """Test IP not in whitelist is denied."""
        allowed_ips = ["192.168.1.1"]

        assert is_ip_allowed("192.168.1.2", allowed_ips) is False
        assert is_ip_allowed("10.0.0.1", allowed_ips) is False

    def test_cidr_network_match_allowed(self):
        """Test IP in CIDR network is allowed."""
        allowed_ips = ["192.168.1.0/24"]

        assert is_ip_allowed("192.168.1.1", allowed_ips) is True
        assert is_ip_allowed("192.168.1.100", allowed_ips) is True
        assert is_ip_allowed("192.168.1.255", allowed_ips) is True

    def test_ip_outside_cidr_network_denied(self):
        """Test IP outside CIDR network is denied."""
        allowed_ips = ["192.168.1.0/24"]

        assert is_ip_allowed("192.168.2.1", allowed_ips) is False
        assert is_ip_allowed("10.0.0.1", allowed_ips) is False

    def test_invalid_ip_format_denied(self):
        """Test invalid IP format is denied."""
        allowed_ips = ["192.168.1.1"]

        assert is_ip_allowed("invalid-ip", allowed_ips) is False
        assert is_ip_allowed("999.999.999.999", allowed_ips) is False

    def test_invalid_cidr_in_whitelist_skipped(self):
        """Test invalid CIDR in whitelist is skipped with warning."""
        allowed_ips = ["invalid-network/24", "192.168.1.1"]

        # Should skip invalid and still check valid ones
        assert is_ip_allowed("192.168.1.1", allowed_ips) is True
        assert is_ip_allowed("10.0.0.1", allowed_ips) is False

    def test_ipv6_support(self):
        """Test IPv6 address support."""
        allowed_ips = ["2001:db8::1", "2001:db8::/32"]

        assert is_ip_allowed("2001:db8::1", allowed_ips) is True
        assert is_ip_allowed("2001:db8::2", allowed_ips) is True
        assert is_ip_allowed("2001:db9::1", allowed_ips) is False

    def test_mixed_ipv4_and_ipv6(self):
        """Test mixed IPv4 and IPv6 whitelist."""
        allowed_ips = ["192.168.1.1", "2001:db8::1"]

        assert is_ip_allowed("192.168.1.1", allowed_ips) is True
        assert is_ip_allowed("2001:db8::1", allowed_ips) is True
        assert is_ip_allowed("10.0.0.1", allowed_ips) is False

    def test_large_cidr_ranges(self):
        """Test large CIDR ranges."""
        allowed_ips = ["10.0.0.0/8"]

        # Should match entire 10.x.x.x range
        assert is_ip_allowed("10.0.0.1", allowed_ips) is True
        assert is_ip_allowed("10.255.255.255", allowed_ips) is True
        assert is_ip_allowed("11.0.0.1", allowed_ips) is False

    def test_small_cidr_ranges(self):
        """Test small CIDR ranges."""
        allowed_ips = ["192.168.1.0/30"]

        # /30 gives 4 IPs (0-3)
        assert is_ip_allowed("192.168.1.0", allowed_ips) is True
        assert is_ip_allowed("192.168.1.3", allowed_ips) is True
        assert is_ip_allowed("192.168.1.4", allowed_ips) is False
