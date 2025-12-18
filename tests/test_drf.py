"""
Tests for Django REST Framework integration.

These tests are skipped if DRF is not installed.
"""

from decimal import Decimal

import pytest

# Try to import DRF components
try:
    from rest_framework.test import APIRequestFactory, force_authenticate
    from rest_framework import status
    from django.contrib.auth import get_user_model

    HAS_DRF = True
except ImportError:
    HAS_DRF = False

# Try to import our DRF components
try:
    from django_iyzico.serializers import (
        IyzicoPaymentSerializer,
        RefundRequestSerializer,
        PaymentFilterSerializer,
    )
    from django_iyzico.viewsets import (
        IyzicoPaymentViewSet,
        IyzicoPaymentManagementViewSet,
    )

    HAS_DRF_COMPONENTS = True
except ImportError:
    HAS_DRF_COMPONENTS = False

from django_iyzico.models import PaymentStatus


pytestmark = pytest.mark.skipif(
    not HAS_DRF or not HAS_DRF_COMPONENTS,
    reason="Django REST Framework not installed",
)


@pytest.mark.django_db
class TestIyzicoPaymentSerializer:
    """Test IyzicoPaymentSerializer."""

    def test_serialize_payment(self, payment_model, sample_payment_data):
        """Test serializing a payment."""
        payment = payment_model.objects.create(
            payment_id="test-payment-123",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            paid_amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            buyer_email="buyer@example.com",
            buyer_name="John",
            buyer_surname="Doe",
            card_last_four_digits="1234",
            card_association="VISA",
            **sample_payment_data,
        )

        serializer = IyzicoPaymentSerializer(payment)
        data = serializer.data

        # Check basic fields
        assert data["payment_id"] == "test-payment-123"
        assert data["conversation_id"] == "conv-123"
        assert data["status"] == PaymentStatus.SUCCESS
        assert Decimal(data["amount"]) == Decimal("100.00")
        assert data["buyer_email"] == "buyer@example.com"

        # Check computed fields
        assert data["status_display"] == "Success"
        assert data["buyer_full_name"] == "John Doe"
        assert data["is_successful"] is True
        assert data["is_failed"] is False
        assert data["can_be_refunded"] is True

    def test_serialize_failed_payment(self, payment_model, sample_payment_data):
        """Test serializing a failed payment."""
        payment = payment_model.objects.create(
            payment_id="failed-payment",
            conversation_id="conv-456",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
            error_code="5006",
            error_message="Card declined",
            **sample_payment_data,
        )

        serializer = IyzicoPaymentSerializer(payment)
        data = serializer.data

        assert data["status"] == PaymentStatus.FAILED
        assert data["is_failed"] is True
        assert data["can_be_refunded"] is False
        assert data["error_code"] == "5006"
        assert data["error_message"] == "Card declined"

    def test_serializer_read_only(self, payment_model, sample_payment_data):
        """Test that serializer is read-only."""
        payment = payment_model.objects.create(
            payment_id="test-payment",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        serializer = IyzicoPaymentSerializer(payment)

        # All fields should be read-only
        for field_name, field in serializer.fields.items():
            assert field.read_only, f"Field {field_name} should be read-only"


@pytest.mark.django_db
class TestRefundRequestSerializer:
    """Test RefundRequestSerializer."""

    def test_valid_full_refund(self):
        """Test valid full refund request (no amount)."""
        data = {"reason": "Customer request"}
        serializer = RefundRequestSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data.get("amount") is None
        assert serializer.validated_data["reason"] == "Customer request"

    def test_valid_partial_refund(self):
        """Test valid partial refund request."""
        data = {"amount": "50.00", "reason": "Partial refund"}
        serializer = RefundRequestSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["amount"] == Decimal("50.00")

    def test_zero_amount_invalid(self):
        """Test that zero amount is invalid."""
        data = {"amount": "0.00"}
        serializer = RefundRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_negative_amount_invalid(self):
        """Test that negative amount is invalid."""
        data = {"amount": "-50.00"}
        serializer = RefundRequestSerializer(data=data)

        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_optional_fields(self):
        """Test that all fields are optional."""
        data = {}
        serializer = RefundRequestSerializer(data=data)

        assert serializer.is_valid()


@pytest.mark.django_db
class TestPaymentFilterSerializer:
    """Test PaymentFilterSerializer."""

    def test_valid_filters(self):
        """Test valid filter parameters."""
        data = {
            "status": PaymentStatus.SUCCESS,
            "currency": "TRY",
            "buyer_email": "test@example.com",
            "min_amount": "100.00",
            "max_amount": "500.00",
        }
        serializer = PaymentFilterSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["status"] == PaymentStatus.SUCCESS

    def test_amount_range_validation(self):
        """Test amount range validation."""
        # Invalid: min > max
        data = {"min_amount": "500.00", "max_amount": "100.00"}
        serializer = PaymentFilterSerializer(data=data)

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_date_range_validation(self):
        """Test date range validation."""
        from datetime import datetime
        from django.utils import timezone

        # Invalid: created_after > created_before
        data = {
            "created_after": timezone.make_aware(datetime(2024, 12, 31)),
            "created_before": timezone.make_aware(datetime(2024, 1, 1)),
        }
        serializer = PaymentFilterSerializer(data=data)

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_all_fields_optional(self):
        """Test that all fields are optional."""
        serializer = PaymentFilterSerializer(data={})
        assert serializer.is_valid()


@pytest.mark.django_db
class TestIyzicoPaymentViewSet:
    """Test IyzicoPaymentViewSet."""

    @pytest.fixture
    def user(self, django_user_model):
        """Create test user."""
        return django_user_model.objects.create_user(
            username="testuser", password="testpass", email="test@example.com"
        )

    @pytest.fixture
    def admin_user(self, django_user_model):
        """Create admin user."""
        return django_user_model.objects.create_superuser(
            username="admin", password="admin", email="admin@example.com"
        )

    @pytest.fixture
    def viewset_class(self, payment_model):
        """Create viewset class for testing."""

        class TestPaymentViewSet(IyzicoPaymentViewSet):
            queryset = payment_model.objects.all()

        return TestPaymentViewSet

    @pytest.fixture
    def factory(self):
        """Create API request factory."""
        return APIRequestFactory()

    def test_list_payments(self, viewset_class, factory, user, payment_model, sample_payment_data):
        """Test listing payments."""
        # Create test payments
        payment_model.objects.create(
            payment_id="payment-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        payment_model.objects.create(
            payment_id="payment-2",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        # Create request
        request = factory.get("/api/payments/")
        force_authenticate(request, user=user)

        # Get response
        view = viewset_class.as_view({"get": "list"})
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_retrieve_payment(
        self, viewset_class, factory, user, payment_model, sample_payment_data
    ):
        """Test retrieving a single payment."""
        payment = payment_model.objects.create(
            payment_id="payment-123",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        request = factory.get(f"/api/payments/{payment.pk}/")
        force_authenticate(request, user=user)

        view = viewset_class.as_view({"get": "retrieve"})
        response = view(request, pk=payment.pk)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_id"] == "payment-123"

    def test_successful_action(
        self, viewset_class, factory, user, payment_model, sample_payment_data
    ):
        """Test successful payments action."""
        # Create mix of payments
        payment_model.objects.create(
            payment_id="success-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        payment_model.objects.create(
            payment_id="failed-1",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
            **sample_payment_data,
        )

        request = factory.get("/api/payments/successful/")
        force_authenticate(request, user=user)

        view = viewset_class.as_view({"get": "successful"})
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["status"] == PaymentStatus.SUCCESS

    def test_failed_action(self, viewset_class, factory, user, payment_model, sample_payment_data):
        """Test failed payments action."""
        payment_model.objects.create(
            payment_id="failed-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
            **sample_payment_data,
        )

        request = factory.get("/api/payments/failed/")
        force_authenticate(request, user=user)

        view = viewset_class.as_view({"get": "failed"})
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["status"] == PaymentStatus.FAILED

    def test_stats_action(self, viewset_class, factory, user, payment_model, sample_payment_data):
        """Test payment statistics action."""
        # Create various payments
        payment_model.objects.create(
            payment_id="success-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        payment_model.objects.create(
            payment_id="success-2",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        payment_model.objects.create(
            payment_id="failed-1",
            conversation_id="conv-3",
            amount=Decimal("50.00"),
            status=PaymentStatus.FAILED,
            **sample_payment_data,
        )

        request = factory.get("/api/payments/stats/")
        force_authenticate(request, user=user)

        view = viewset_class.as_view({"get": "stats"})
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 3
        assert response.data["successful"] == 2
        assert response.data["failed"] == 1
        assert Decimal(response.data["total_amount"]) == Decimal("350.00")
        assert Decimal(response.data["successful_amount"]) == Decimal("300.00")

    def test_unauthenticated_access_denied(
        self, viewset_class, factory, payment_model, sample_payment_data
    ):
        """Test that unauthenticated users cannot access."""
        payment_model.objects.create(
            payment_id="payment-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        request = factory.get("/api/payments/")
        view = viewset_class.as_view({"get": "list"})
        response = view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestIyzicoPaymentManagementViewSet:
    """Test IyzicoPaymentManagementViewSet with refund capabilities."""

    @pytest.fixture
    def admin_user(self, django_user_model):
        """Create admin user."""
        return django_user_model.objects.create_superuser(
            username="admin", password="admin", email="admin@example.com"
        )

    @pytest.fixture
    def viewset_class(self, payment_model):
        """Create management viewset class."""

        class TestPaymentManagementViewSet(IyzicoPaymentManagementViewSet):
            queryset = payment_model.objects.all()

        return TestPaymentManagementViewSet

    @pytest.fixture
    def factory(self):
        """Create API request factory."""
        return APIRequestFactory()

    def test_refund_action_requires_admin(
        self, viewset_class, factory, django_user_model, payment_model, sample_payment_data
    ):
        """Test that refund action requires admin."""
        # Create regular user
        user = django_user_model.objects.create_user(
            username="user", password="pass", email="user@example.com"
        )

        payment = payment_model.objects.create(
            payment_id="payment-123",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        request = factory.post(f"/api/payments/{payment.pk}/refund/", {})
        force_authenticate(request, user=user)

        view = viewset_class.as_view({"post": "refund"})
        response = view(request, pk=payment.pk)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_refund_non_refundable_payment(
        self, viewset_class, factory, admin_user, payment_model, sample_payment_data
    ):
        """Test refunding a non-refundable payment."""
        # Create failed payment (cannot be refunded)
        payment = payment_model.objects.create(
            payment_id="failed-payment",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
            **sample_payment_data,
        )

        request = factory.post(f"/api/payments/{payment.pk}/refund/", {"reason": "Test refund"})
        force_authenticate(request, user=admin_user)

        view = viewset_class.as_view({"post": "refund"})
        response = view(request, pk=payment.pk)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be refunded" in response.data["error"].lower()

    def test_refund_invalid_amount(
        self, viewset_class, factory, admin_user, payment_model, sample_payment_data
    ):
        """Test refund with invalid amount."""
        payment = payment_model.objects.create(
            payment_id="payment-123",
            conversation_id="conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
            **sample_payment_data,
        )

        # Try to refund negative amount
        request = factory.post(f"/api/payments/{payment.pk}/refund/", {"amount": "-50.00"})
        force_authenticate(request, user=admin_user)

        view = viewset_class.as_view({"post": "refund"})
        response = view(request, pk=payment.pk)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
