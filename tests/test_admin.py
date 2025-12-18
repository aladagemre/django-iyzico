"""
Tests for Django admin interface.

Tests the IyzicoPaymentAdminMixin and all admin features.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from django.test import RequestFactory
from django.utils import timezone

from django_iyzico.admin import IyzicoPaymentAdminMixin
from django_iyzico.models import PaymentStatus

from .models import TestPayment

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create admin user for testing."""
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="admin123"
    )


@pytest.fixture
def request_factory():
    """Create request factory."""
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory, admin_user):
    """Create admin request with authenticated user."""
    request = request_factory.get("/admin/")
    request.user = admin_user
    # Add messages framework
    setattr(request, "session", "session")
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)
    return request


@pytest.fixture
def payment_admin():
    """Create PaymentAdmin instance."""

    class TestPaymentAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
        pass

    admin_instance = TestPaymentAdmin(TestPayment, AdminSite())
    return admin_instance


@pytest.fixture
def sample_payment(db):
    """Create sample payment for testing."""
    return TestPayment.objects.create(
        conversation_id="test-conv-123",
        payment_id="test-pay-123",
        status=PaymentStatus.SUCCESS,
        amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        currency="TRY",
        buyer_email="buyer@example.com",
        buyer_name="John",
        buyer_surname="Doe",
        card_last_four_digits="1234",
        card_association="VISA",
        card_type="CREDIT_CARD",
        raw_response={"status": "success", "paymentId": "test-pay-123"},
    )


@pytest.mark.django_db
class TestIyzicoPaymentAdminMixin:
    """Test IyzicoPaymentAdminMixin functionality."""

    def test_list_display_configuration(self, payment_admin):
        """Test list_display is configured correctly."""
        expected_fields = [
            "payment_id",
            "get_status_badge",
            "get_amount_display_admin",
            "buyer_email",
            "get_buyer_name",
            "get_card_display_admin",
            "created_at",
        ]
        assert payment_admin.list_display == expected_fields

    def test_list_filter_configuration(self, payment_admin):
        """Test list_filter is configured correctly."""
        expected_filters = [
            "status",
            "created_at",
            "currency",
            "card_association",
            "card_type",
        ]
        assert payment_admin.list_filter == expected_filters

    def test_search_fields_configuration(self, payment_admin):
        """Test search_fields is configured correctly."""
        expected_fields = [
            "payment_id",
            "conversation_id",
            "buyer_email",
            "buyer_name",
            "buyer_surname",
        ]
        assert payment_admin.search_fields == expected_fields

    def test_readonly_fields_configuration(self, payment_admin):
        """Test readonly_fields is configured correctly."""
        readonly_fields = payment_admin.readonly_fields
        # Check key fields are readonly
        assert "payment_id" in readonly_fields
        assert "conversation_id" in readonly_fields
        assert "amount" in readonly_fields
        assert "created_at" in readonly_fields
        # Status should be editable (not in readonly)
        assert "status" not in readonly_fields

    def test_date_hierarchy(self, payment_admin):
        """Test date_hierarchy is configured correctly."""
        assert payment_admin.date_hierarchy == "created_at"

    def test_ordering(self, payment_admin):
        """Test ordering is configured correctly."""
        assert payment_admin.ordering == ["-created_at"]

    def test_list_per_page(self, payment_admin):
        """Test pagination is configured correctly."""
        assert payment_admin.list_per_page == 50

    def test_fieldsets_configuration(self, payment_admin):
        """Test fieldsets are configured correctly."""
        fieldsets = payment_admin.fieldsets
        assert len(fieldsets) == 6  # 6 sections

        # Check section names
        section_names = [fs[0] for fs in fieldsets]
        assert "Payment Information" in str(section_names)
        assert "Amounts" in str(section_names)
        assert "Buyer Information" in str(section_names)
        assert "Card Information" in str(section_names)
        assert "Status & Errors" in str(section_names)
        assert "Metadata" in str(section_names)

    def test_actions_configuration(self, payment_admin):
        """Test admin actions are configured correctly."""
        assert "refund_payment" in payment_admin.actions
        assert "export_csv" in payment_admin.actions


@pytest.mark.django_db
class TestStatusBadge:
    """Test get_status_badge method."""

    def test_success_status_badge(self, payment_admin, sample_payment):
        """Test success status badge is green."""
        sample_payment.status = PaymentStatus.SUCCESS
        badge_html = payment_admin.get_status_badge(sample_payment)

        assert "Success" in badge_html
        assert "#28a745" in badge_html  # Green color
        assert "background-color" in badge_html

    def test_failed_status_badge(self, payment_admin, sample_payment):
        """Test failed status badge is red."""
        sample_payment.status = PaymentStatus.FAILED
        badge_html = payment_admin.get_status_badge(sample_payment)

        assert "Failed" in badge_html
        assert "#dc3545" in badge_html  # Red color

    def test_pending_status_badge(self, payment_admin, sample_payment):
        """Test pending status badge is yellow."""
        sample_payment.status = PaymentStatus.PENDING
        badge_html = payment_admin.get_status_badge(sample_payment)

        assert "Pending" in badge_html
        assert "#ffc107" in badge_html  # Yellow color

    def test_refunded_status_badge(self, payment_admin, sample_payment):
        """Test refunded status badge is gray."""
        sample_payment.status = PaymentStatus.REFUNDED
        badge_html = payment_admin.get_status_badge(sample_payment)

        assert "Refunded" in badge_html
        assert "#6c757d" in badge_html  # Gray color


@pytest.mark.django_db
class TestAmountDisplay:
    """Test get_amount_display_admin method."""

    def test_amount_display_simple(self, payment_admin, sample_payment):
        """Test amount display without installments."""
        sample_payment.amount = Decimal("100.00")
        sample_payment.paid_amount = Decimal("100.00")

        display = payment_admin.get_amount_display_admin(sample_payment)
        assert "100.00 TRY" in display

    def test_amount_display_with_installments(self, payment_admin, sample_payment):
        """Test amount display with different paid amount."""
        sample_payment.amount = Decimal("100.00")
        sample_payment.paid_amount = Decimal("105.00")

        display = payment_admin.get_amount_display_admin(sample_payment)
        assert "100.00 TRY" in display
        assert "paid: 105.00 TRY" in display


@pytest.mark.django_db
class TestBuyerName:
    """Test get_buyer_name method."""

    def test_buyer_name_full(self, payment_admin, sample_payment):
        """Test buyer name with both first and last name."""
        sample_payment.buyer_name = "John"
        sample_payment.buyer_surname = "Doe"

        name = payment_admin.get_buyer_name(sample_payment)
        assert name == "John Doe"

    def test_buyer_name_only_first(self, payment_admin, sample_payment):
        """Test buyer name with only first name."""
        sample_payment.buyer_name = "John"
        sample_payment.buyer_surname = ""

        name = payment_admin.get_buyer_name(sample_payment)
        assert name == "John"

    def test_buyer_name_empty(self, payment_admin, sample_payment):
        """Test buyer name when empty."""
        sample_payment.buyer_name = ""
        sample_payment.buyer_surname = ""

        name = payment_admin.get_buyer_name(sample_payment)
        assert name == "-"


@pytest.mark.django_db
class TestCardDisplay:
    """Test get_card_display_admin method."""

    def test_card_display_with_data(self, payment_admin, sample_payment):
        """Test card display with card data."""
        sample_payment.card_association = "VISA"
        sample_payment.card_last_four_digits = "1234"

        display = payment_admin.get_card_display_admin(sample_payment)
        assert "VISA" in display
        assert "1234" in display

    def test_card_display_empty(self, payment_admin, sample_payment):
        """Test card display when empty."""
        sample_payment.card_association = ""
        sample_payment.card_last_four_digits = ""

        display = payment_admin.get_card_display_admin(sample_payment)
        # get_card_display() returns "****" when no card data
        assert display == "****"


@pytest.mark.django_db
class TestRawResponseDisplay:
    """Test get_raw_response_display method."""

    def test_raw_response_display_with_data(self, payment_admin, sample_payment):
        """Test raw response display with JSON data."""
        sample_payment.raw_response = {"status": "success", "paymentId": "123"}

        display = payment_admin.get_raw_response_display(sample_payment)
        assert "<pre" in display
        assert "success" in display
        assert "123" in display

    def test_raw_response_display_empty(self, payment_admin, sample_payment):
        """Test raw response display when empty."""
        sample_payment.raw_response = None

        display = payment_admin.get_raw_response_display(sample_payment)
        assert display == "-"


@pytest.mark.django_db
class TestIyzicoDashboardLink:
    """Test get_iyzico_dashboard_link method."""

    def test_dashboard_link_with_payment_id(self, payment_admin, sample_payment):
        """Test dashboard link with payment ID."""
        sample_payment.payment_id = "test-pay-123"

        link = payment_admin.get_iyzico_dashboard_link(sample_payment)
        assert "https://merchant.iyzipay.com/payment/test-pay-123" in link
        assert "<a href=" in link
        assert 'target="_blank"' in link

    def test_dashboard_link_without_payment_id(self, payment_admin, sample_payment):
        """Test dashboard link without payment ID."""
        sample_payment.payment_id = None

        link = payment_admin.get_iyzico_dashboard_link(sample_payment)
        assert link == "-"


@pytest.mark.django_db
class TestRefundAction:
    """Test refund_payment admin action."""

    def test_refund_payment_success(self, payment_admin, admin_request, sample_payment):
        """Test successful payment refund."""
        queryset = TestPayment.objects.filter(id=sample_payment.id)

        # Create a mock for process_refund
        def mock_refund(self):
            self.status = PaymentStatus.REFUNDED
            self.save()

        # Patch the process_refund method on the model class
        with patch.object(TestPayment, "process_refund", mock_refund, create=True):
            payment_admin.refund_payment(admin_request, queryset)

            # Verify payment was refunded
            sample_payment.refresh_from_db()
            assert sample_payment.status == PaymentStatus.REFUNDED

    def test_refund_payment_cannot_refund(self, payment_admin, admin_request, sample_payment):
        """Test refund action on non-refundable payment."""
        sample_payment.status = PaymentStatus.FAILED
        sample_payment.save()

        queryset = TestPayment.objects.filter(id=sample_payment.id)
        payment_admin.refund_payment(admin_request, queryset)

        # Verify no exception was raised (warning message should be shown)

    def test_refund_payment_no_method(self, payment_admin, admin_request, sample_payment):
        """Test refund action when model doesn't have process_refund."""
        # Use patch to remove the method
        from tests.models import TestPayment
        from django_iyzico.models import AbstractIyzicoPayment

        # Save original method
        original_method = AbstractIyzicoPayment.process_refund

        # Delete the method from the parent class temporarily
        delattr(AbstractIyzicoPayment, "process_refund")

        try:
            queryset = TestPayment.objects.filter(id=sample_payment.id)
            payment_admin.refund_payment(admin_request, queryset)

            # Should handle gracefully with error message
        finally:
            # Restore the method
            AbstractIyzicoPayment.process_refund = original_method


@pytest.mark.django_db
class TestExportCSVAction:
    """Test export_csv admin action."""

    def test_export_csv_single_payment(self, payment_admin, admin_request, sample_payment):
        """Test CSV export with single payment."""
        queryset = TestPayment.objects.filter(id=sample_payment.id)
        response = payment_admin.export_csv(admin_request, queryset)

        # Verify response
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]
        assert "iyzico_payments.csv" in response["Content-Disposition"]

        # Verify content
        content = response.content.decode("utf-8")
        assert "Payment ID" in content
        assert "test-pay-123" in content
        assert "buyer@example.com" in content

    def test_export_csv_multiple_payments(self, payment_admin, admin_request, db):
        """Test CSV export with multiple payments."""
        # Create multiple payments
        payments = []
        for i in range(3):
            payment = TestPayment.objects.create(
                conversation_id=f"conv-{i}",
                payment_id=f"pay-{i}",
                status=PaymentStatus.SUCCESS,
                amount=Decimal("100.00"),
                currency="TRY",
                buyer_email=f"buyer{i}@example.com",
            )
            payments.append(payment)

        queryset = TestPayment.objects.all()
        response = payment_admin.export_csv(admin_request, queryset)

        # Verify all payments are in CSV
        content = response.content.decode("utf-8")
        assert "pay-0" in content
        assert "pay-1" in content
        assert "pay-2" in content

    def test_export_csv_empty_queryset(self, payment_admin, admin_request, db):
        """Test CSV export with empty queryset."""
        queryset = TestPayment.objects.none()
        response = payment_admin.export_csv(admin_request, queryset)

        # Verify response
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Payment ID" in content  # Header should still be present


@pytest.mark.django_db
class TestDeletePermission:
    """Test has_delete_permission method."""

    def test_cannot_delete_successful_payment(self, payment_admin, admin_request, sample_payment):
        """Test that successful payments cannot be deleted."""
        sample_payment.status = PaymentStatus.SUCCESS

        can_delete = payment_admin.has_delete_permission(admin_request, sample_payment)
        assert can_delete is False

    def test_can_delete_failed_payment(self, payment_admin, admin_request, sample_payment):
        """Test that failed payments can be deleted."""
        sample_payment.status = PaymentStatus.FAILED

        can_delete = payment_admin.has_delete_permission(admin_request, sample_payment)
        assert can_delete is True

    def test_can_delete_pending_payment(self, payment_admin, admin_request, sample_payment):
        """Test that pending payments can be deleted."""
        sample_payment.status = PaymentStatus.PENDING

        can_delete = payment_admin.has_delete_permission(admin_request, sample_payment)
        assert can_delete is True

    def test_can_delete_in_list_view(self, payment_admin, admin_request):
        """Test delete permission in list view (no specific object)."""
        can_delete = payment_admin.has_delete_permission(admin_request, None)
        assert can_delete is True


@pytest.mark.django_db
class TestGetQueryset:
    """Test get_queryset method."""

    def test_get_queryset(self, payment_admin, admin_request, sample_payment):
        """Test get_queryset returns correct queryset."""
        queryset = payment_admin.get_queryset(admin_request)

        # Verify queryset contains our payment
        assert sample_payment in queryset
        assert queryset.count() == 1
