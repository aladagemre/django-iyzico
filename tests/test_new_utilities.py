"""
Tests for new utility functions added in Phase 3.
"""

import time
from decimal import Decimal

import pytest

from django_iyzico.exceptions import ValidationError
from django_iyzico.utils import (
    calculate_installment_amount,
    generate_basket_id,
    calculate_paid_price_with_installments,
)


class TestCalculateInstallmentAmount:
    """Test calculate_installment_amount function."""

    def test_single_installment(self):
        """Test calculation with single installment."""
        result = calculate_installment_amount(Decimal("1000"), 1)
        assert result == Decimal("1000.00")

    def test_multiple_installments_no_interest(self):
        """Test calculation with multiple installments and no interest."""
        result = calculate_installment_amount(Decimal("1000"), 10)
        assert result == Decimal("100.00")

        result = calculate_installment_amount(Decimal("999.99"), 3)
        assert result == Decimal("333.33")

    def test_installments_with_interest(self):
        """Test calculation with interest."""
        # 1000 TRY, 10 installments, 2% interest per installment
        # Total = 1000 * (1 + 0.02 * 10) = 1200
        # Monthly = 1200 / 10 = 120
        result = calculate_installment_amount(Decimal("1000"), 10, Decimal("2"))
        assert result == Decimal("120.00")

        # 500 TRY, 6 installments, 1.5% interest
        # Total = 500 * (1 + 0.015 * 6) = 545
        # Monthly = 545 / 6 = 90.83
        result = calculate_installment_amount(Decimal("500"), 6, Decimal("1.5"))
        assert result == Decimal("90.83")

    def test_zero_amount_raises_error(self):
        """Test that zero amount raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            calculate_installment_amount(Decimal("0"), 10)
        assert "greater than zero" in str(exc_info.value)

    def test_negative_amount_raises_error(self):
        """Test that negative amount raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            calculate_installment_amount(Decimal("-100"), 10)
        assert "greater than zero" in str(exc_info.value)

    def test_zero_installments_raises_error(self):
        """Test that zero installments raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            calculate_installment_amount(Decimal("1000"), 0)
        assert "at least 1" in str(exc_info.value)

    def test_negative_interest_rate_raises_error(self):
        """Test that negative interest rate raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            calculate_installment_amount(Decimal("1000"), 10, Decimal("-1"))
        assert "cannot be negative" in str(exc_info.value)

    def test_decimal_precision(self):
        """Test that result is rounded to 2 decimal places."""
        result = calculate_installment_amount(Decimal("100"), 3)
        assert result.as_tuple().exponent == -2  # 2 decimal places

    def test_edge_case_small_amount(self):
        """Test with very small amounts."""
        result = calculate_installment_amount(Decimal("1.00"), 3)
        assert result == Decimal("0.33")


class TestGenerateBasketId:
    """Test generate_basket_id function."""

    def test_default_prefix(self):
        """Test basket ID generation with default prefix."""
        basket_id = generate_basket_id()
        assert basket_id.startswith("B")
        assert len(basket_id) > 10

    def test_custom_prefix(self):
        """Test basket ID generation with custom prefix."""
        basket_id = generate_basket_id("ORDER")
        assert basket_id.startswith("ORDER")

    def test_empty_prefix(self):
        """Test basket ID generation with empty prefix."""
        basket_id = generate_basket_id("")
        assert basket_id.startswith("B")  # Falls back to default

    def test_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = set()
        for _ in range(100):
            basket_id = generate_basket_id()
            ids.add(basket_id)

        # All IDs should be unique
        assert len(ids) == 100

    def test_contains_timestamp(self):
        """Test that basket ID contains timestamp."""
        before = int(time.time())
        basket_id = generate_basket_id()
        after = int(time.time())

        # Extract timestamp from basket ID (after prefix)
        # Format: {prefix}{timestamp}{uuid}
        # Timestamp is 10 digits
        timestamp_str = basket_id[1:11]  # Skip "B" prefix
        timestamp = int(timestamp_str)

        assert before <= timestamp <= after

    def test_format(self):
        """Test basket ID format."""
        basket_id = generate_basket_id("B")

        # Should be: B + 10-digit timestamp + 8-char UUID
        assert len(basket_id) >= 19  # B + 10 + 8
        assert basket_id[0] == "B"

        # UUID part should be uppercase (any letters should be uppercase)
        uuid_part = basket_id[11:]
        # Check that uuid_part is 8 characters of hexadecimal
        assert len(uuid_part) == 8
        assert all(c in "0123456789ABCDEF" for c in uuid_part)


class TestCalculatePaidPriceWithInstallments:
    """Test calculate_paid_price_with_installments function."""

    def test_single_installment_no_fee(self):
        """Test with single installment (no fees)."""
        result = calculate_paid_price_with_installments(Decimal("1000"), 1)
        assert result == Decimal("1000.00")

    def test_installments_no_rates(self):
        """Test with installments but no rates defined."""
        result = calculate_paid_price_with_installments(Decimal("1000"), 3)
        assert result == Decimal("1000.00")

        result = calculate_paid_price_with_installments(Decimal("1000"), 6, {})
        assert result == Decimal("1000.00")

    def test_installments_with_rates(self):
        """Test with installment rates."""
        rates = {
            3: Decimal("1.5"),  # 1.5% per installment
            6: Decimal("2.0"),  # 2.0% per installment
            12: Decimal("2.5"),  # 2.5% per installment
        }

        # 3 installments: 1000 * (1 + 0.015 * 3) = 1045
        result = calculate_paid_price_with_installments(Decimal("1000"), 3, rates)
        assert result == Decimal("1045.00")

        # 6 installments: 1000 * (1 + 0.02 * 6) = 1120
        result = calculate_paid_price_with_installments(Decimal("1000"), 6, rates)
        assert result == Decimal("1120.00")

        # 12 installments: 1000 * (1 + 0.025 * 12) = 1300
        result = calculate_paid_price_with_installments(Decimal("1000"), 12, rates)
        assert result == Decimal("1300.00")

    def test_installments_rate_not_defined(self):
        """Test with installment count not in rates dict."""
        rates = {
            3: Decimal("1.5"),
            6: Decimal("2.0"),
        }

        # 9 installments not in rates, should return base price
        result = calculate_paid_price_with_installments(Decimal("1000"), 9, rates)
        assert result == Decimal("1000.00")

    def test_decimal_precision(self):
        """Test that result has exactly 2 decimal places."""
        rates = {3: Decimal("1.5")}
        result = calculate_paid_price_with_installments(Decimal("1000"), 3, rates)

        assert result.as_tuple().exponent == -2

    def test_realistic_scenario(self):
        """Test with realistic bank rates."""
        # Typical Turkish bank installment rates
        rates = {
            2: Decimal("0.5"),
            3: Decimal("1.2"),
            6: Decimal("2.4"),
            9: Decimal("3.6"),
            12: Decimal("4.8"),
        }

        base_price = Decimal("2500.00")

        # 6 installments with 2.4% rate
        # Total = 2500 * (1 + 0.024 * 6) = 2500 * 1.144 = 2860
        result = calculate_paid_price_with_installments(base_price, 6, rates)
        assert result == Decimal("2860.00")

    def test_zero_rate(self):
        """Test with zero rate (interest-free installments)."""
        rates = {
            3: Decimal("0"),
        }

        result = calculate_paid_price_with_installments(Decimal("1000"), 3, rates)
        assert result == Decimal("1000.00")

    def test_complex_amounts(self):
        """Test with complex decimal amounts."""
        rates = {3: Decimal("1.5")}

        # 999.99 * (1 + 0.015 * 3) = 999.99 * 1.045 = 1044.99
        result = calculate_paid_price_with_installments(Decimal("999.99"), 3, rates)
        assert result == Decimal("1044.99")

        # 1234.56 * (1 + 0.015 * 3) = 1234.56 * 1.045 = 1290.12
        result = calculate_paid_price_with_installments(Decimal("1234.56"), 3, rates)
        assert result == Decimal("1290.12")


class TestUtilitiesIntegration:
    """Integration tests for utility functions."""

    def test_basket_and_installment_together(self):
        """Test using basket ID and installment calculation together."""
        basket_id = generate_basket_id("ORDER")
        total_amount = Decimal("5000")
        installments = 12
        monthly_amount = calculate_installment_amount(
            total_amount, installments, Decimal("2.5")
        )

        # Should work together without errors
        assert basket_id.startswith("ORDER")
        assert monthly_amount > Decimal("416.66")  # Base amount per month

    def test_installment_and_paid_price_consistency(self):
        """Test consistency between installment calculation and paid price."""
        base_price = Decimal("1000")
        installments = 6
        rate = Decimal("2.0")

        # Calculate monthly installment
        monthly = calculate_installment_amount(base_price, installments, rate)

        # Calculate total paid price
        rates = {6: rate}
        total_paid = calculate_paid_price_with_installments(base_price, installments, rates)

        # Total paid should equal monthly * installments (approximately)
        calculated_total = monthly * installments
        assert abs(calculated_total - total_paid) < Decimal("0.10")  # Allow small rounding difference
