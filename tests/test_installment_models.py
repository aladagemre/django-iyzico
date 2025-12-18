"""
Tests for installment-related model methods and admin functionality.

Tests model helper methods and admin display methods for installments.
"""

from decimal import Decimal

from django.test import TestCase

from django_iyzico.models import PaymentStatus

# ============================================================================
# Mock Payment Model for Testing
# ============================================================================


class MockPayment:
    """Mock payment model for testing installment methods."""

    def __init__(self, **kwargs):
        """Initialize mock payment."""
        self.payment_id = kwargs.get("payment_id", "test-payment-123")
        self.status = kwargs.get("status", PaymentStatus.SUCCESS)
        self.amount = kwargs.get("amount", Decimal("100.00"))
        self.currency = kwargs.get("currency", "TRY")
        self.installment = kwargs.get("installment", 1)
        self.installment_rate = kwargs.get("installment_rate", None)
        self.monthly_installment_amount = kwargs.get("monthly_installment_amount", None)
        self.total_with_installment = kwargs.get("total_with_installment", None)
        self.bin_number = kwargs.get("bin_number", None)

    def has_installment(self):
        """Check if payment has installment."""
        return (
            self.installment is not None
            and self.installment > 1
            and self.monthly_installment_amount is not None
        )

    def get_installment_display(self):
        """Get installment display string."""
        if not self.has_installment():
            return "Single payment"

        return f"{self.installment}x {self.monthly_installment_amount} {self.currency}"

    def get_installment_fee(self):
        """Calculate installment fee."""
        if not self.has_installment() or not self.total_with_installment:
            return Decimal("0.00")

        return self.total_with_installment - self.amount

    def get_installment_details(self):
        """Get detailed installment information."""
        if not self.has_installment():
            return None

        details = {
            "installment_count": self.installment,
            "base_amount": self.amount,
            "monthly_payment": self.monthly_installment_amount,
        }

        if self.installment_rate is not None:
            details["installment_rate"] = self.installment_rate

        if self.total_with_installment is not None:
            details["total_with_fees"] = self.total_with_installment
            details["total_fee"] = self.get_installment_fee()

        return details

    def is_zero_interest_installment(self):
        """Check if installment is zero interest."""
        if not self.has_installment():
            return False

        return self.installment_rate == Decimal("0.00")


# ============================================================================
# Model Method Tests
# ============================================================================


class TestPaymentInstallmentMethods(TestCase):
    """Test installment-related model methods."""

    def test_has_installment_single_payment(self):
        """Test has_installment for single payment."""
        payment = MockPayment(installment=1)

        assert payment.has_installment() is False

    def test_has_installment_with_installment(self):
        """Test has_installment with installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
        )

        assert payment.has_installment() is True

    def test_has_installment_missing_monthly_amount(self):
        """Test has_installment with missing monthly amount."""
        payment = MockPayment(installment=3)

        assert payment.has_installment() is False

    def test_get_installment_display_single_payment(self):
        """Test display for single payment."""
        payment = MockPayment(installment=1)

        result = payment.get_installment_display()

        assert result == "Single payment"

    def test_get_installment_display_with_installment(self):
        """Test display with installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            currency="TRY",
        )

        result = payment.get_installment_display()

        assert result == "3x 34.33 TRY"

    def test_get_installment_display_different_currency(self):
        """Test display with different currency."""
        payment = MockPayment(
            installment=6,
            monthly_installment_amount=Decimal("17.50"),
            currency="USD",
        )

        result = payment.get_installment_display()

        assert result == "6x 17.50 USD"

    def test_get_installment_fee_single_payment(self):
        """Test fee calculation for single payment."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=1,
        )

        result = payment.get_installment_fee()

        assert result == Decimal("0.00")

    def test_get_installment_fee_zero_interest(self):
        """Test fee calculation for zero interest."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            total_with_installment=Decimal("100.00"),
        )

        result = payment.get_installment_fee()

        assert result == Decimal("0.00")

    def test_get_installment_fee_with_interest(self):
        """Test fee calculation with interest."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            total_with_installment=Decimal("103.00"),
        )

        result = payment.get_installment_fee()

        assert result == Decimal("3.00")

    def test_get_installment_details_single_payment(self):
        """Test getting details for single payment."""
        payment = MockPayment(installment=1)

        result = payment.get_installment_details()

        assert result is None

    def test_get_installment_details_basic(self):
        """Test getting basic installment details."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
        )

        result = payment.get_installment_details()

        assert result is not None
        assert result["installment_count"] == 3
        assert result["base_amount"] == Decimal("100.00")
        assert result["monthly_payment"] == Decimal("34.33")

    def test_get_installment_details_with_rate(self):
        """Test getting details with rate."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
        )

        result = payment.get_installment_details()

        assert result["installment_rate"] == Decimal("3.00")

    def test_get_installment_details_with_total(self):
        """Test getting details with total."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            total_with_installment=Decimal("103.00"),
        )

        result = payment.get_installment_details()

        assert result["total_with_fees"] == Decimal("103.00")
        assert result["total_fee"] == Decimal("3.00")

    def test_is_zero_interest_installment_true(self):
        """Test identifying zero interest installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            installment_rate=Decimal("0.00"),
        )

        assert payment.is_zero_interest_installment() is True

    def test_is_zero_interest_installment_false(self):
        """Test identifying non-zero interest installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
        )

        assert payment.is_zero_interest_installment() is False

    def test_is_zero_interest_installment_single_payment(self):
        """Test zero interest check for single payment."""
        payment = MockPayment(installment=1)

        assert payment.is_zero_interest_installment() is False


# ============================================================================
# Admin Display Method Tests
# ============================================================================


class MockAdmin:
    """Mock admin class for testing admin methods."""

    def get_installment_display_admin(self, obj):
        """Display installment information in list view."""
        if not hasattr(obj, "has_installment") or not obj.has_installment():
            return "-"

        if hasattr(obj, "get_installment_display"):
            display = obj.get_installment_display()

            # Add badge for zero-interest
            if hasattr(obj, "installment_rate") and obj.installment_rate == 0:
                return f"{display} [0% Interest]"

            return display

        return "-"

    def get_installment_details_admin(self, obj):
        """Display detailed installment information in detail view."""
        if not hasattr(obj, "has_installment") or not obj.has_installment():
            return "No installment applied - single payment"

        if hasattr(obj, "get_installment_details"):
            details = obj.get_installment_details()
        else:
            return "Installment details not available"

        if not details:
            return "Installment details not available"

        # Build text representation
        lines = []

        if "installment_count" in details:
            lines.append(f"Installment Count: {details['installment_count']}x")

        if "monthly_payment" in details:
            currency = obj.currency if hasattr(obj, "currency") else "TRY"
            lines.append(f"Monthly Payment: {details['monthly_payment']} {currency}")

        if "total_with_fees" in details:
            currency = obj.currency if hasattr(obj, "currency") else "TRY"
            lines.append(f"Total: {details['total_with_fees']} {currency}")

        if "installment_rate" in details:
            rate = details["installment_rate"]
            if rate == 0:
                lines.append("Rate: 0.00% (Zero Interest)")
            else:
                lines.append(f"Rate: {rate}%")

        return "\n".join(lines)


class TestAdminDisplayMethods(TestCase):
    """Test admin display methods for installments."""

    def setUp(self):
        """Set up test fixtures."""
        self.admin = MockAdmin()

    def test_admin_display_single_payment(self):
        """Test admin display for single payment."""
        payment = MockPayment(installment=1)

        result = self.admin.get_installment_display_admin(payment)

        assert result == "-"

    def test_admin_display_with_installment(self):
        """Test admin display with installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
        )

        result = self.admin.get_installment_display_admin(payment)

        assert "3x 34.33 TRY" in result

    def test_admin_display_zero_interest_badge(self):
        """Test admin display shows zero interest badge."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            installment_rate=Decimal("0.00"),
        )

        result = self.admin.get_installment_display_admin(payment)

        assert "0% Interest" in result

    def test_admin_display_with_interest(self):
        """Test admin display with interest."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
        )

        result = self.admin.get_installment_display_admin(payment)

        assert "3x 34.33 TRY" in result
        assert "0% Interest" not in result

    def test_admin_details_single_payment(self):
        """Test admin details for single payment."""
        payment = MockPayment(installment=1)

        result = self.admin.get_installment_details_admin(payment)

        assert "No installment" in result or "single payment" in result

    def test_admin_details_with_installment(self):
        """Test admin details with installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("34.33"),
            total_with_installment=Decimal("103.00"),
            installment_rate=Decimal("3.00"),
        )

        result = self.admin.get_installment_details_admin(payment)

        assert "3x" in result
        assert "34.33" in result
        assert "3.00%" in result or "3%" in result

    def test_admin_details_zero_interest(self):
        """Test admin details for zero interest."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            total_with_installment=Decimal("100.00"),
            installment_rate=Decimal("0.00"),
        )

        result = self.admin.get_installment_details_admin(payment)

        assert "Zero Interest" in result or "0.00%" in result


# ============================================================================
# Edge Cases and Validation Tests
# ============================================================================


class TestInstallmentEdgeCases(TestCase):
    """Test edge cases for installment functionality."""

    def test_high_installment_count(self):
        """Test with high installment count."""
        payment = MockPayment(
            amount=Decimal("1000.00"),
            installment=12,
            monthly_installment_amount=Decimal("85.00"),
            total_with_installment=Decimal("1020.00"),
        )

        assert payment.has_installment() is True
        assert payment.get_installment_fee() == Decimal("20.00")

    def test_very_small_amount(self):
        """Test with very small amount."""
        payment = MockPayment(
            amount=Decimal("10.00"),
            installment=3,
            monthly_installment_amount=Decimal("3.33"),
            total_with_installment=Decimal("10.00"),
        )

        assert payment.has_installment() is True
        assert payment.get_installment_fee() == Decimal("0.00")

    def test_large_amount(self):
        """Test with large amount."""
        payment = MockPayment(
            amount=Decimal("50000.00"),
            installment=12,
            monthly_installment_amount=Decimal("4250.00"),
            total_with_installment=Decimal("51000.00"),
        )

        result = payment.get_installment_details()

        assert result["base_amount"] == Decimal("50000.00")
        assert result["total_fee"] == Decimal("1000.00")

    def test_installment_with_none_values(self):
        """Test with None values."""
        payment = MockPayment(
            installment=None,
            monthly_installment_amount=None,
        )

        assert payment.has_installment() is False
        assert payment.get_installment_display() == "Single payment"

    def test_installment_rate_none(self):
        """Test with None installment rate."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            installment_rate=None,
        )

        details = payment.get_installment_details()

        assert "installment_rate" not in details

    def test_total_with_installment_none(self):
        """Test with None total_with_installment."""
        payment = MockPayment(
            installment=3,
            monthly_installment_amount=Decimal("33.33"),
            total_with_installment=None,
        )

        fee = payment.get_installment_fee()

        assert fee == Decimal("0.00")

    def test_decimal_precision(self):
        """Test decimal precision in calculations."""
        payment = MockPayment(
            amount=Decimal("99.99"),
            installment=7,
            monthly_installment_amount=Decimal("14.29"),
            total_with_installment=Decimal("100.03"),
        )

        fee = payment.get_installment_fee()

        # Fee should be calculated with proper precision
        assert fee == Decimal("0.04")

    def test_rounding_edge_case(self):
        """Test rounding edge case."""
        payment = MockPayment(
            amount=Decimal("100.00"),
            installment=3,
            monthly_installment_amount=Decimal("33.34"),  # Rounded up
            total_with_installment=Decimal("100.02"),
        )

        fee = payment.get_installment_fee()

        assert fee == Decimal("0.02")


# ============================================================================
# Model Integration Tests
# ============================================================================


class TestInstallmentModelIntegration(TestCase):
    """Integration tests for installment model methods."""

    def test_full_installment_workflow(self):
        """Test complete workflow with installment."""
        # Create payment with installment
        payment = MockPayment(
            amount=Decimal("500.00"),
            installment=6,
            monthly_installment_amount=Decimal("85.00"),
            total_with_installment=Decimal("510.00"),
            installment_rate=Decimal("2.00"),
            bin_number="554960",
        )

        # Verify has installment
        assert payment.has_installment() is True

        # Get display
        display = payment.get_installment_display()
        assert "6x" in display
        assert "85.00" in display

        # Calculate fee
        fee = payment.get_installment_fee()
        assert fee == Decimal("10.00")

        # Get details
        details = payment.get_installment_details()
        assert details["installment_count"] == 6
        assert details["base_amount"] == Decimal("500.00")
        assert details["monthly_payment"] == Decimal("85.00")
        assert details["total_with_fees"] == Decimal("510.00")
        assert details["total_fee"] == Decimal("10.00")
        assert details["installment_rate"] == Decimal("2.00")

        # Check not zero interest
        assert payment.is_zero_interest_installment() is False

    def test_zero_interest_workflow(self):
        """Test workflow with zero interest installment."""
        payment = MockPayment(
            amount=Decimal("300.00"),
            installment=3,
            monthly_installment_amount=Decimal("100.00"),
            total_with_installment=Decimal("300.00"),
            installment_rate=Decimal("0.00"),
        )

        # Verify zero interest
        assert payment.is_zero_interest_installment() is True

        # Verify no fee
        assert payment.get_installment_fee() == Decimal("0.00")

        # Get details
        details = payment.get_installment_details()
        assert details["installment_rate"] == Decimal("0.00")
        assert details["total_fee"] == Decimal("0.00")

    def test_admin_display_workflow(self):
        """Test admin display workflow."""
        admin = MockAdmin()

        payment = MockPayment(
            amount=Decimal("200.00"),
            installment=3,
            monthly_installment_amount=Decimal("68.00"),
            total_with_installment=Decimal("204.00"),
            installment_rate=Decimal("2.00"),
        )

        # Get list display
        list_display = admin.get_installment_display_admin(payment)
        assert "3x 68.00 TRY" in list_display

        # Get detail display
        detail_display = admin.get_installment_details_admin(payment)
        assert "3x" in detail_display
        assert "68.00" in detail_display
        assert "2.00%" in detail_display or "2%" in detail_display
