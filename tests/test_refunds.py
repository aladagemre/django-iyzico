"""Tests for refund functionality."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError

from django_iyzico.client import IyzicoClient, RefundResponse
from django_iyzico.exceptions import PaymentError, ValidationError
from django_iyzico.models import PaymentStatus
from tests.models import TestPayment


@pytest.fixture
def sample_refund_response():
    """Fixture providing sample refund response."""
    return {
        "status": "success",
        "paymentId": "test-payment-123",
        "paymentTransactionId": "test-refund-456",
        "conversationId": "test-conv-123",
        "price": "100.00",
        "currency": "TRY",
    }


@pytest.fixture
def sample_failed_refund():
    """Fixture providing sample failed refund response."""
    return {
        "status": "failure",
        "errorCode": "10000",
        "errorMessage": "Refund failed",
        "errorGroup": "REFUND_ERROR",
    }


@pytest.mark.django_db
class TestRefundResponse:
    """Test RefundResponse class."""

    def test_refund_response_success(self, sample_refund_response):
        """Test successful refund response."""
        response = RefundResponse(sample_refund_response)

        assert response.is_successful() is True
        assert response.status == "success"
        assert response.payment_id == "test-payment-123"
        assert response.refund_id == "test-refund-456"
        assert response.conversation_id == "test-conv-123"
        assert response.price == Decimal("100.00")
        assert response.currency == "TRY"
        assert response.error_code is None
        assert response.error_message is None

    def test_refund_response_failure(self, sample_failed_refund):
        """Test failed refund response."""
        response = RefundResponse(sample_failed_refund)

        assert response.is_successful() is False
        assert response.status == "failure"
        assert response.error_code == "10000"
        assert response.error_message == "Refund failed"
        assert response.error_group == "REFUND_ERROR"
        assert response.payment_id is None
        assert response.refund_id is None

    def test_refund_response_to_dict(self, sample_refund_response):
        """Test converting refund response to dictionary."""
        response = RefundResponse(sample_refund_response)
        result = response.to_dict()

        assert result == sample_refund_response

    def test_refund_response_str(self, sample_refund_response):
        """Test refund response string representation."""
        response = RefundResponse(sample_refund_response)
        result = str(response)

        assert "RefundResponse" in result
        assert "success" in result
        assert "test-payment-123" in result
        assert "test-refund-456" in result

    def test_refund_response_repr(self, sample_refund_response):
        """Test refund response repr."""
        response = RefundResponse(sample_refund_response)
        result = repr(response)

        assert "RefundResponse" in result


@pytest.mark.django_db
class TestClientRefund:
    """Test IyzicoClient refund functionality."""

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_refund_payment_full(self, mock_refund_class, sample_refund_response):
        """Test full refund of a payment."""
        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_refund_response
        mock_refund_class.return_value = mock_refund

        client = IyzicoClient()
        response = client.refund_payment("test-payment-123", ip_address="85.34.78.112")

        assert response.is_successful() is True
        assert response.payment_id == "test-payment-123"
        assert response.refund_id == "test-refund-456"

        # Verify API was called correctly
        call_args = mock_refund.create.call_args[0][0]
        assert call_args["paymentTransactionId"] == "test-payment-123"
        assert call_args["ip"] == "85.34.78.112"
        assert "price" not in call_args  # Full refund, no amount specified

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_refund_payment_partial(self, mock_refund_class, sample_refund_response):
        """Test partial refund of a payment."""
        # Setup mock
        mock_refund = Mock()
        partial_response = sample_refund_response.copy()
        partial_response["price"] = "50.00"
        mock_refund.create.return_value = partial_response
        mock_refund_class.return_value = mock_refund

        client = IyzicoClient()
        response = client.refund_payment(
            "test-payment-123", ip_address="85.34.78.112", amount=Decimal("50.00")
        )

        assert response.is_successful() is True
        assert response.price == Decimal("50.00")

        # Verify API was called with amount
        call_args = mock_refund.create.call_args[0][0]
        assert call_args["paymentTransactionId"] == "test-payment-123"
        assert call_args["price"] == "50.00"

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_refund_payment_with_reason(self, mock_refund_class, sample_refund_response):
        """Test refund with reason."""
        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_refund_response
        mock_refund_class.return_value = mock_refund

        client = IyzicoClient()
        response = client.refund_payment(
            "test-payment-123", ip_address="85.34.78.112", reason="Customer request"
        )

        assert response.is_successful() is True

        # Verify reason was included
        call_args = mock_refund.create.call_args[0][0]
        assert call_args["description"] == "Customer request"

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_refund_payment_failed(self, mock_refund_class, sample_failed_refund):
        """Test failed refund."""
        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_failed_refund
        mock_refund_class.return_value = mock_refund

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.refund_payment("test-payment-123", ip_address="85.34.78.112")

        assert "Refund failed" in str(exc_info.value)
        assert exc_info.value.error_code == "10000"

    def test_refund_payment_missing_payment_id(self):
        """Test refund without payment ID."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.refund_payment("", ip_address="85.34.78.112")

        assert "Payment ID is required" in str(exc_info.value)

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_refund_payment_api_exception(self, mock_refund_class):
        """Test refund when API raises exception."""
        # Setup mock to raise exception
        mock_refund = Mock()
        mock_refund.create.side_effect = Exception("API Error")
        mock_refund_class.return_value = mock_refund

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.refund_payment("test-payment-123", ip_address="85.34.78.112")

        assert "Refund request failed" in str(exc_info.value)


@pytest.mark.django_db
class TestModelRefund:
    """Test model refund functionality."""

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_process_full_refund(self, mock_refund_class, sample_refund_response):
        """Test processing full refund through model."""
        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_refund_response
        mock_refund_class.return_value = mock_refund

        # Create successful payment
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
        )

        # Process refund
        response = payment.process_refund(ip_address="85.34.78.112")

        assert response.is_successful() is True

        # Verify payment status updated
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.REFUNDED

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_process_partial_refund(self, mock_refund_class):
        """Test processing partial refund through model."""
        # Setup mock
        mock_refund = Mock()
        partial_response = {
            "status": "success",
            "paymentId": "test-payment-123",
            "paymentTransactionId": "test-refund-456",
            "price": "50.00",
            "currency": "TRY",
        }
        mock_refund.create.return_value = partial_response
        mock_refund_class.return_value = mock_refund

        # Create successful payment
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
        )

        # Process partial refund
        response = payment.process_refund(ip_address="85.34.78.112", amount=Decimal("50.00"))

        assert response.is_successful() is True
        assert response.price == Decimal("50.00")

        # Verify payment status updated to REFUND_PENDING
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.REFUND_PENDING

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_process_refund_with_reason(self, mock_refund_class, sample_refund_response):
        """Test processing refund with reason."""
        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_refund_response
        mock_refund_class.return_value = mock_refund

        # Create successful payment
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
        )

        # Process refund with reason
        response = payment.process_refund(
            ip_address="85.34.78.112", reason="Customer not satisfied"
        )

        assert response.is_successful() is True

        # Verify reason was passed to API
        call_args = mock_refund.create.call_args[0][0]
        assert call_args["description"] == "Customer not satisfied"

    def test_process_refund_invalid_status(self):
        """Test refund on payment that cannot be refunded."""
        # Create failed payment
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.FAILED,
        )

        with pytest.raises(DjangoValidationError) as exc_info:
            payment.process_refund(ip_address="85.34.78.112")

        assert "cannot be refunded" in str(exc_info.value)

    def test_process_refund_missing_payment_id(self):
        """Test refund on payment without payment_id."""
        # Create payment without payment_id
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
            payment_id=None,
        )

        with pytest.raises(DjangoValidationError) as exc_info:
            payment.process_refund(ip_address="85.34.78.112")

        assert "Payment ID is missing" in str(exc_info.value)

    @patch("django_iyzico.client.iyzipay.Refund")
    def test_process_refund_signal_sent(self, mock_refund_class, sample_refund_response):
        """Test that refund signal is sent."""
        from django_iyzico.signals import payment_refunded

        # Setup mock
        mock_refund = Mock()
        mock_refund.create.return_value = sample_refund_response
        mock_refund_class.return_value = mock_refund

        # Setup signal receiver
        signal_received = []

        def signal_handler(sender, **kwargs):
            signal_received.append(kwargs)

        payment_refunded.connect(signal_handler)

        # Create successful payment
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
        )

        # Process refund
        payment.process_refund(
            ip_address="85.34.78.112", amount=Decimal("50.00"), reason="Test refund"
        )

        # Verify signal was sent
        assert len(signal_received) == 1
        assert signal_received[0]["instance"] == payment
        assert signal_received[0]["amount"] == Decimal("50.00")
        assert signal_received[0]["reason"] == "Test refund"
        assert "response" in signal_received[0]

        # Cleanup
        payment_refunded.disconnect(signal_handler)

    def test_can_be_refunded_success_status(self):
        """Test can_be_refunded for successful payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.SUCCESS,
        )

        assert payment.can_be_refunded() is True

    def test_can_be_refunded_failed_status(self):
        """Test can_be_refunded for failed payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.FAILED,
        )

        assert payment.can_be_refunded() is False

    def test_can_be_refunded_refunded_status(self):
        """Test can_be_refunded for already refunded payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            payment_id="test-payment-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.REFUNDED,
        )

        assert payment.can_be_refunded() is False

    def test_can_be_refunded_pending_status(self):
        """Test can_be_refunded for pending payment."""
        payment = TestPayment.objects.create(
            conversation_id="test-conv-123",
            amount=Decimal("100.00"),
            currency="TRY",
            status=PaymentStatus.PENDING,
        )

        assert payment.can_be_refunded() is False
