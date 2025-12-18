"""
Tests for django-iyzico models.

Tests AbstractIyzicoPayment model with a concrete implementation.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from django_iyzico.models import PaymentStatus

# Concrete model for testing
from .models import TestPayment


@pytest.mark.django_db
class TestPaymentStatusChoices:
    """Test PaymentStatus choices enum."""

    def test_has_all_expected_statuses(self):
        """Test that all expected statuses are defined."""
        expected_statuses = [
            "pending",
            "processing",
            "success",
            "failed",
            "refund_pending",
            "refunded",
            "cancelled",
        ]

        actual_statuses = [choice[0] for choice in PaymentStatus.choices]

        for status in expected_statuses:
            assert status in actual_statuses

    def test_status_display_names(self):
        """Test that status display names are set."""
        assert PaymentStatus.PENDING.label
        assert PaymentStatus.SUCCESS.label
        assert PaymentStatus.FAILED.label


@pytest.mark.django_db
class TestTestPaymentModel:
    """Test the concrete TestPayment model."""

    def test_create_minimal_payment(self):
        """Test creating payment with minimal required fields."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        assert payment.id is not None
        assert payment.conversation_id == "test-conv-123"
        assert payment.amount == Decimal("100.00")
        assert payment.status == PaymentStatus.PENDING
        assert payment.currency == "TRY"
        assert payment.locale == "tr"
        assert payment.installment == 1

    def test_create_complete_payment(self):
        """Test creating payment with all fields."""
        payment = TestPayment.objects.create(
            payment_id="iyzico-payment-123",
            conversation_id="test-conv-123",
            status=PaymentStatus.SUCCESS,
            amount=Decimal("100.00"),
            paid_amount=Decimal("100.00"),
            currency="TRY",
            locale="tr",
            card_last_four_digits="0008",
            card_type="CREDIT_CARD",
            card_association="MASTER_CARD",
            card_family="Bonus",
            card_bank_name="Test Bank",
            card_bank_code="1234",
            installment=1,
            buyer_email="test@example.com",
            buyer_name="John",
            buyer_surname="Doe",
            raw_response={"status": "success"},
        )

        assert payment.payment_id == "iyzico-payment-123"
        assert payment.status == PaymentStatus.SUCCESS
        assert payment.card_last_four_digits == "0008"
        assert payment.buyer_email == "test@example.com"

    def test_payment_id_unique_constraint(self):
        """Test that payment_id must be unique."""
        TestPayment.objects.create(
            payment_id="unique-payment-123",
            conversation_id="test-conv-1",
            amount=Decimal("100.00"),
        )

        # Try to create another with same payment_id
        with pytest.raises(IntegrityError):
            TestPayment.objects.create(
                payment_id="unique-payment-123",
                conversation_id="test-conv-2",
                amount=Decimal("200.00"),
            )

    def test_payment_id_can_be_null(self):
        """Test that payment_id can be null (before Iyzico assigns it)."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        assert payment.payment_id is None

    def test_auto_timestamps(self):
        """Test that created_at and updated_at are set automatically."""
        before_create = timezone.now()

        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        after_create = timezone.now()

        assert payment.created_at is not None
        assert payment.updated_at is not None
        assert before_create <= payment.created_at <= after_create
        assert before_create <= payment.updated_at <= after_create

    def test_updated_at_changes_on_save(self):
        """Test that updated_at changes when model is saved."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        original_updated_at = payment.updated_at

        # Wait a tiny bit and save
        import time

        time.sleep(0.01)

        payment.status = PaymentStatus.SUCCESS
        payment.save()

        assert payment.updated_at > original_updated_at

    def test_str_representation(self):
        """Test string representation of payment."""
        payment = TestPayment.objects.create(
            payment_id="test-payment-123",
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        str_repr = str(payment)

        assert "test-payment-123" in str_repr
        assert "Success" in str_repr or "success" in str_repr.lower()


@pytest.mark.django_db
class TestPaymentHelperMethods:
    """Test helper methods on payment model."""

    def test_is_successful_when_success(self):
        """Test is_successful() returns True for successful payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        assert payment.is_successful() is True

    def test_is_successful_when_not_success(self):
        """Test is_successful() returns False for non-successful payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )

        assert payment.is_successful() is False

    def test_is_failed_when_failed(self):
        """Test is_failed() returns True for failed payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
        )

        assert payment.is_failed() is True

    def test_is_failed_when_not_failed(self):
        """Test is_failed() returns False for non-failed payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        assert payment.is_failed() is False

    def test_is_pending_when_pending(self):
        """Test is_pending() returns True for pending payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )

        assert payment.is_pending() is True

    def test_is_pending_when_processing(self):
        """Test is_pending() returns True for processing payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.PROCESSING,
        )

        assert payment.is_pending() is True

    def test_is_pending_when_not_pending(self):
        """Test is_pending() returns False for completed payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        assert payment.is_pending() is False

    def test_can_be_refunded_when_success(self):
        """Test can_be_refunded() returns True for successful payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        assert payment.can_be_refunded() is True

    def test_can_be_refunded_when_not_success(self):
        """Test can_be_refunded() returns False for non-successful payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
        )

        assert payment.can_be_refunded() is False

    def test_get_buyer_full_name(self):
        """Test get_buyer_full_name() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            buyer_name="John",
            buyer_surname="Doe",
        )

        assert payment.get_buyer_full_name() == "John Doe"

    def test_get_buyer_full_name_only_first_name(self):
        """Test get_buyer_full_name() with only first name."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            buyer_name="John",
        )

        assert payment.get_buyer_full_name() == "John"

    def test_get_masked_card_number(self):
        """Test get_masked_card_number() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            card_last_four_digits="0008",
        )

        assert payment.get_masked_card_number() == "**** **** **** 0008"

    def test_get_card_display(self):
        """Test get_card_display() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            card_association="VISA",
            card_last_four_digits="1234",
        )

        display = payment.get_card_display()
        assert "VISA" in display
        assert "1234" in display

    def test_get_amount_display(self):
        """Test get_amount_display() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.50"),
            currency="TRY",
        )

        assert payment.get_amount_display() == "100.50 TRY"

    def test_get_paid_amount_display(self):
        """Test get_paid_amount_display() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            paid_amount=Decimal("105.00"),
            currency="TRY",
        )

        assert payment.get_paid_amount_display() == "105.00 TRY"


@pytest.mark.django_db
class TestUpdateFromResponse:
    """Test update_from_response() method."""

    def test_updates_from_dict_response(self):
        """Test updating payment from dict response."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        response = {
            "status": "success",
            "paymentId": "iyzico-123",
            "conversationId": "test-conv-123",
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
            "installment": 1,
            "cardType": "CREDIT_CARD",
            "cardAssociation": "MASTER_CARD",
            "buyerEmail": "test@example.com",
            "buyerName": "John",
            "buyerSurname": "Doe",
        }

        payment.update_from_response(response, save=False)

        assert payment.status == PaymentStatus.SUCCESS
        assert payment.payment_id == "iyzico-123"
        assert payment.amount == Decimal("100.00")
        assert payment.card_type == "CREDIT_CARD"
        assert payment.buyer_email == "test@example.com"

    def test_updates_from_payment_response_object(self):
        """Test updating from PaymentResponse object."""
        from django_iyzico.client import PaymentResponse

        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        response_data = {
            "status": "success",
            "paymentId": "iyzico-123",
            "conversationId": "test-conv-123",
        }

        response_obj = PaymentResponse(response_data)
        payment.update_from_response(response_obj, save=False)

        assert payment.payment_id == "iyzico-123"

    def test_updates_status_to_success(self):
        """Test status updated to SUCCESS on successful response."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )

        response = {"status": "success", "paymentId": "iyzico-123"}

        payment.update_from_response(response, save=False)

        assert payment.status == PaymentStatus.SUCCESS

    def test_updates_status_to_failed(self):
        """Test status updated to FAILED on failure response."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )

        response = {
            "status": "failure",
            "errorCode": "5006",
            "errorMessage": "Card declined",
        }

        payment.update_from_response(response, save=False)

        assert payment.status == PaymentStatus.FAILED
        assert payment.error_code == "5006"
        assert payment.error_message == "Card declined"

    def test_stores_raw_response(self):
        """Test that raw response is stored."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        response = {
            "status": "success",
            "paymentId": "iyzico-123",
            "someOtherField": "value",
        }

        payment.update_from_response(response, save=False)

        assert payment.raw_response == response

    def test_saves_when_save_true(self):
        """Test that model is saved when save=True."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        response = {"status": "success", "paymentId": "iyzico-123"}

        payment.update_from_response(response, save=True)

        # Reload from database
        payment.refresh_from_db()

        assert payment.payment_id == "iyzico-123"


@pytest.mark.django_db
class TestMaskAndStoreCardData:
    """Test mask_and_store_card_data() method."""

    def test_stores_last_four_digits(self):
        """Test that last 4 digits are stored."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        payment_details = {
            "card": {
                "cardNumber": "5528790000000008",
                "cardHolderName": "John Doe",
            }
        }

        payment.mask_and_store_card_data(payment_details, save=False)

        assert payment.card_last_four_digits == "0008"

    def test_does_not_store_full_card_number(self):
        """Test that full card number is never stored - SECURITY CRITICAL."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        payment_details = {
            "card": {
                "cardNumber": "5528790000000008",
                "cvc": "123",
            }
        }

        payment.mask_and_store_card_data(payment_details, save=False)

        # Check all fields - full card number should not be anywhere
        field_values = [
            str(getattr(payment, field.name))
            for field in payment._meta.get_fields()
            if hasattr(payment, field.name)
        ]

        full_card_str = "5528790000000008"
        for value in field_values:
            assert full_card_str not in value


@pytest.mark.django_db
class TestPaymentManager:
    """Test custom payment manager."""

    def test_get_by_payment_id(self):
        """Test get_by_payment_id() method."""
        payment = TestPayment.objects.create(
            payment_id="test-payment-123",
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        found = TestPayment.objects.get_by_payment_id("test-payment-123")

        assert found.id == payment.id

    def test_get_by_payment_id_not_found(self):
        """Test get_by_payment_id() raises DoesNotExist."""
        with pytest.raises(TestPayment.DoesNotExist):
            TestPayment.objects.get_by_payment_id("nonexistent")

    def test_get_by_conversation_id(self):
        """Test get_by_conversation_id() method."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
        )

        found = TestPayment.objects.get_by_conversation_id("test-conv-123")

        assert found.id == payment.id

    def test_successful_queryset(self):
        """Test successful() queryset method."""
        TestPayment.objects.create(
            conversation_id="test-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )
        TestPayment.objects.create(
            conversation_id="test-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
        )
        TestPayment.objects.create(
            conversation_id="test-3",
            amount=Decimal("300.00"),
            status=PaymentStatus.SUCCESS,
        )

        successful = TestPayment.objects.successful()

        assert successful.count() == 2
        assert all(p.status == PaymentStatus.SUCCESS for p in successful)

    def test_failed_queryset(self):
        """Test failed() queryset method."""
        TestPayment.objects.create(
            conversation_id="test-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )
        TestPayment.objects.create(
            conversation_id="test-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
        )
        TestPayment.objects.create(
            conversation_id="test-3",
            amount=Decimal("300.00"),
            status=PaymentStatus.FAILED,
        )

        failed = TestPayment.objects.failed()

        assert failed.count() == 2
        assert all(p.status == PaymentStatus.FAILED for p in failed)

    def test_pending_queryset(self):
        """Test pending() queryset method."""
        TestPayment.objects.create(
            conversation_id="test-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.PENDING,
        )
        TestPayment.objects.create(
            conversation_id="test-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.SUCCESS,
        )

        pending = TestPayment.objects.pending()

        assert pending.count() == 1
        assert pending.first().status == PaymentStatus.PENDING

    def test_ordering(self):
        """Test that payments are ordered by -created_at by default."""
        import time

        payment1 = TestPayment.objects.create(
            conversation_id="test-1",
            amount=Decimal("100.00"),
        )

        time.sleep(0.01)

        payment2 = TestPayment.objects.create(
            conversation_id="test-2",
            amount=Decimal("200.00"),
        )

        payments = list(TestPayment.objects.all())

        # Most recent should be first
        assert payments[0].id == payment2.id
        assert payments[1].id == payment1.id
