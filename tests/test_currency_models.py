"""
Tests for multi-currency model methods.

Tests currency-related methods on AbstractIyzicoPayment model.
"""

import pytest
from decimal import Decimal

from django_iyzico.currency import CurrencyConverter


# ============================================================================
# Mock Payment Model for Testing
# ============================================================================


class MockCurrencyPayment:
    """Mock payment model with currency methods."""

    def __init__(self, **kwargs):
        """Initialize mock payment."""
        self.payment_id = kwargs.get("payment_id", "test-123")
        self.amount = kwargs.get("amount", Decimal("100.00"))
        self.paid_amount = kwargs.get("paid_amount", None)
        self.currency = kwargs.get("currency", "TRY")

    def get_formatted_amount(self, show_symbol=True, show_code=False):
        """Get formatted amount with currency symbol."""
        from django_iyzico.currency import format_amount

        return format_amount(self.amount, self.currency, show_symbol, show_code)

    def get_formatted_paid_amount(self, show_symbol=True, show_code=False):
        """Get formatted paid amount."""
        from django_iyzico.currency import format_amount

        amount = self.paid_amount if self.paid_amount else self.amount
        return format_amount(amount, self.currency, show_symbol, show_code)

    def get_currency_symbol(self):
        """Get currency symbol."""
        from django_iyzico.currency import get_currency_symbol

        return get_currency_symbol(self.currency)

    def get_currency_name(self):
        """Get currency name."""
        from django_iyzico.currency import get_currency_name

        return get_currency_name(self.currency)

    def convert_to_currency(self, target_currency, converter=None):
        """Convert to another currency."""
        if not converter:
            converter = CurrencyConverter()
        return converter.convert(self.amount, self.currency, target_currency)

    def is_currency(self, currency_code):
        """Check if payment is in specific currency."""
        return self.currency.upper() == currency_code.upper()

    def get_amount_in_try(self, converter=None):
        """Get amount in TRY."""
        if self.is_currency("TRY"):
            return self.amount
        return self.convert_to_currency("TRY", converter)

    def get_currency_info(self):
        """Get currency information."""
        from django_iyzico.currency import get_currency_info

        return get_currency_info(self.currency)


# ============================================================================
# Model Currency Method Tests
# ============================================================================


class TestPaymentCurrencyMethods:
    """Test payment model currency methods."""

    def test_get_formatted_amount_try(self):
        """Test formatted amount in TRY."""
        payment = MockCurrencyPayment(amount=Decimal("1234.56"), currency="TRY")

        result = payment.get_formatted_amount()

        assert "₺" in result
        assert "1234" in result or "1.234" in result

    def test_get_formatted_amount_usd(self):
        """Test formatted amount in USD."""
        payment = MockCurrencyPayment(amount=Decimal("1234.56"), currency="USD")

        result = payment.get_formatted_amount()

        assert "$" in result
        assert "1,234.56" in result

    def test_get_formatted_amount_no_symbol(self):
        """Test formatted amount without symbol."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="EUR")

        result = payment.get_formatted_amount(show_symbol=False)

        assert "€" not in result

    def test_get_formatted_amount_with_code(self):
        """Test formatted amount with code."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="GBP")

        result = payment.get_formatted_amount(show_code=True)

        assert "GBP" in result

    def test_get_formatted_paid_amount(self):
        """Test formatted paid amount."""
        payment = MockCurrencyPayment(
            amount=Decimal("100.00"), paid_amount=Decimal("95.00"), currency="USD"
        )

        result = payment.get_formatted_paid_amount()

        assert "$" in result
        assert "95" in result

    def test_get_formatted_paid_amount_none(self):
        """Test formatted paid amount when none set."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        result = payment.get_formatted_paid_amount()

        # Should use amount when paid_amount is None
        assert "100" in result

    def test_get_currency_symbol_try(self):
        """Test getting TRY symbol."""
        payment = MockCurrencyPayment(currency="TRY")

        result = payment.get_currency_symbol()

        assert result == "₺"

    def test_get_currency_symbol_usd(self):
        """Test getting USD symbol."""
        payment = MockCurrencyPayment(currency="USD")

        result = payment.get_currency_symbol()

        assert result == "$"

    def test_get_currency_symbol_eur(self):
        """Test getting EUR symbol."""
        payment = MockCurrencyPayment(currency="EUR")

        result = payment.get_currency_symbol()

        assert result == "€"

    def test_get_currency_symbol_gbp(self):
        """Test getting GBP symbol."""
        payment = MockCurrencyPayment(currency="GBP")

        result = payment.get_currency_symbol()

        assert result == "£"

    def test_get_currency_name_try(self):
        """Test getting TRY name."""
        payment = MockCurrencyPayment(currency="TRY")

        result = payment.get_currency_name()

        assert result == "Turkish Lira"

    def test_get_currency_name_usd(self):
        """Test getting USD name."""
        payment = MockCurrencyPayment(currency="USD")

        result = payment.get_currency_name()

        assert result == "US Dollar"

    def test_convert_to_currency_same(self):
        """Test converting to same currency."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        result = payment.convert_to_currency("USD")

        assert result == Decimal("100.00")

    def test_convert_to_currency_different(self):
        """Test converting to different currency."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        result = payment.convert_to_currency("TRY")

        # Should be more TRY (since TRY is worth less)
        assert result > Decimal("100.00")

    def test_convert_to_currency_custom_converter(self):
        """Test converting with custom converter."""
        custom_rates = {
            "TRY": Decimal("1.00"),
            "USD": Decimal("0.05"),
        }
        converter = CurrencyConverter(rates=custom_rates)

        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="TRY")

        result = payment.convert_to_currency("USD", converter=converter)

        # With custom rate of 0.05, 100 TRY = 5 USD
        assert result == Decimal("5.00")

    def test_is_currency_match(self):
        """Test currency check - match."""
        payment = MockCurrencyPayment(currency="USD")

        assert payment.is_currency("USD") is True

    def test_is_currency_no_match(self):
        """Test currency check - no match."""
        payment = MockCurrencyPayment(currency="USD")

        assert payment.is_currency("EUR") is False

    def test_is_currency_case_insensitive(self):
        """Test currency check is case-insensitive."""
        payment = MockCurrencyPayment(currency="USD")

        assert payment.is_currency("usd") is True
        assert payment.is_currency("Usd") is True

    def test_get_amount_in_try_already_try(self):
        """Test getting TRY amount when already in TRY."""
        payment = MockCurrencyPayment(amount=Decimal("500.00"), currency="TRY")

        result = payment.get_amount_in_try()

        assert result == Decimal("500.00")

    def test_get_amount_in_try_from_usd(self):
        """Test getting TRY amount from USD."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        result = payment.get_amount_in_try()

        # Should convert to more TRY
        assert result > Decimal("100.00")

    def test_get_amount_in_try_custom_converter(self):
        """Test getting TRY amount with custom converter."""
        custom_rates = {
            "TRY": Decimal("1.00"),
            "USD": Decimal("0.04"),
        }
        converter = CurrencyConverter(rates=custom_rates)

        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        result = payment.get_amount_in_try(converter=converter)

        # With rate 0.04, 100 USD should convert to 2500 TRY
        assert result == Decimal("2500.00")

    def test_get_currency_info(self):
        """Test getting currency info."""
        payment = MockCurrencyPayment(currency="EUR")

        info = payment.get_currency_info()

        assert info["code"] == "EUR"
        assert info["symbol"] == "€"
        assert info["name"] == "Euro"
        assert info["decimal_places"] == 2


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestCurrencyModelEdgeCases:
    """Test edge cases for model currency methods."""

    def test_zero_amount_formatting(self):
        """Test formatting zero amount."""
        payment = MockCurrencyPayment(amount=Decimal("0.00"), currency="USD")

        result = payment.get_formatted_amount()

        assert "0" in result

    def test_negative_amount_formatting(self):
        """Test formatting negative amount."""
        payment = MockCurrencyPayment(amount=Decimal("-100.00"), currency="EUR")

        result = payment.get_formatted_amount()

        assert "-" in result

    def test_very_large_amount_formatting(self):
        """Test formatting very large amount."""
        payment = MockCurrencyPayment(amount=Decimal("1000000.00"), currency="GBP")

        result = payment.get_formatted_amount()

        assert "1" in result
        assert "000" in result

    def test_very_small_amount_formatting(self):
        """Test formatting very small amount."""
        payment = MockCurrencyPayment(amount=Decimal("0.01"), currency="TRY")

        result = payment.get_formatted_amount()

        assert "0" in result
        assert "01" in result

    def test_conversion_zero_amount(self):
        """Test converting zero amount."""
        payment = MockCurrencyPayment(amount=Decimal("0.00"), currency="USD")

        result = payment.convert_to_currency("EUR")

        assert result == Decimal("0.00")

    def test_conversion_negative_amount(self):
        """Test converting negative amount."""
        payment = MockCurrencyPayment(amount=Decimal("-100.00"), currency="TRY")

        result = payment.convert_to_currency("USD")

        assert result < Decimal("0.00")


# ============================================================================
# Integration Tests
# ============================================================================


class TestCurrencyModelIntegration:
    """Integration tests for model currency functionality."""

    def test_full_currency_workflow(self):
        """Test complete currency workflow."""
        # Create payment in USD
        payment = MockCurrencyPayment(amount=Decimal("250.00"), currency="USD")

        # Get formatted display
        formatted = payment.get_formatted_amount(show_symbol=True, show_code=True)
        assert "$" in formatted
        assert "USD" in formatted

        # Get symbol and name
        symbol = payment.get_currency_symbol()
        name = payment.get_currency_name()
        assert symbol == "$"
        assert name == "US Dollar"

        # Check currency
        assert payment.is_currency("USD") is True
        assert payment.is_currency("EUR") is False

        # Convert to other currencies
        eur_amount = payment.convert_to_currency("EUR")
        gbp_amount = payment.convert_to_currency("GBP")
        try_amount = payment.convert_to_currency("TRY")

        assert all(amt > Decimal("0.00") for amt in [eur_amount, gbp_amount, try_amount])

        # Get amount in TRY
        try_amount2 = payment.get_amount_in_try()
        assert try_amount2 == try_amount

        # Get currency info
        info = payment.get_currency_info()
        assert info["symbol"] == "$"
        assert info["code"] == "USD"

    def test_multi_currency_comparison(self):
        """Test comparing payments in different currencies."""
        payment_usd = MockCurrencyPayment(amount=Decimal("100.00"), currency="USD")

        payment_try = MockCurrencyPayment(amount=Decimal("3000.00"), currency="TRY")

        # Convert both to TRY for comparison
        usd_in_try = payment_usd.get_amount_in_try()
        try_amount = payment_try.get_amount_in_try()

        # Both should be similar in value
        assert abs(usd_in_try - try_amount) < Decimal("100.00")

    def test_currency_chain_conversion(self):
        """Test chain of currency conversions."""
        payment = MockCurrencyPayment(amount=Decimal("100.00"), currency="TRY")

        # Convert TRY -> USD
        usd = payment.convert_to_currency("USD")

        # Create new payment in USD
        payment_usd = MockCurrencyPayment(amount=usd, currency="USD")

        # Convert back to TRY
        try_back = payment_usd.convert_to_currency("TRY")

        # Should be approximately the same
        difference = abs(try_back - payment.amount)
        assert difference < Decimal("1.00")  # Within 1 TRY
