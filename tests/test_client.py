"""
Tests for django-iyzico IyzicoClient.

Tests payment client with mocked iyzipay SDK calls.
"""

import json
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from django_iyzico.client import IyzicoClient, PaymentResponse, ThreeDSResponse
from django_iyzico.exceptions import CardError, PaymentError, ThreeDSecureError, ValidationError


class TestPaymentResponse:
    """Test PaymentResponse wrapper class."""

    def test_successful_response(self):
        """Test successful payment response."""
        response_data = {
            "status": "success",
            "paymentId": "12345678",
            "conversationId": "test-conv-123",
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
            "installment": 1,
        }

        response = PaymentResponse(response_data)

        assert response.is_successful() is True
        assert response.status == "success"
        assert response.payment_id == "12345678"
        assert response.conversation_id == "test-conv-123"
        assert response.price == Decimal("100.00")
        assert response.paid_price == Decimal("100.00")
        assert response.currency == "TRY"
        assert response.installment == 1

    def test_failed_response(self):
        """Test failed payment response."""
        response_data = {
            "status": "failure",
            "errorCode": "5006",
            "errorMessage": "Transaction declined",
            "errorGroup": "CARD_ERROR",
        }

        response = PaymentResponse(response_data)

        assert response.is_successful() is False
        assert response.status == "failure"
        assert response.error_code == "5006"
        assert response.error_message == "Transaction declined"
        assert response.error_group == "CARD_ERROR"

    def test_parses_bytes_response(self):
        """Test parsing bytes response from iyzipay."""
        response_data = {"status": "success", "paymentId": "123"}
        response_bytes = json.dumps(response_data).encode("utf-8")

        response = PaymentResponse(response_bytes)

        assert response.payment_id == "123"

    def test_card_info_property(self):
        """Test card_info property extraction."""
        response_data = {
            "status": "success",
            "cardType": "CREDIT_CARD",
            "cardAssociation": "MASTER_CARD",
            "cardFamily": "Bonus",
        }

        response = PaymentResponse(response_data)
        card_info = response.card_info

        assert card_info["cardType"] == "CREDIT_CARD"
        assert card_info["cardAssociation"] == "MASTER_CARD"
        assert card_info["cardFamily"] == "Bonus"

    def test_buyer_properties(self):
        """Test buyer information properties."""
        response_data = {
            "status": "success",
            "buyerEmail": "test@example.com",
            "buyerName": "John",
            "buyerSurname": "Doe",
        }

        response = PaymentResponse(response_data)

        assert response.buyer_email == "test@example.com"
        assert response.buyer_name == "John"
        assert response.buyer_surname == "Doe"

    def test_to_dict(self):
        """Test to_dict() method."""
        response_data = {"status": "success", "paymentId": "123"}

        response = PaymentResponse(response_data)

        assert response.to_dict() == response_data

    def test_str_representation(self):
        """Test string representation."""
        response_data = {"status": "success", "paymentId": "123"}

        response = PaymentResponse(response_data)
        str_repr = str(response)

        assert "123" in str_repr
        assert "success" in str_repr


class TestThreeDSResponse:
    """Test ThreeDSResponse wrapper class."""

    def test_three_ds_html_content(self):
        """Test 3DS HTML content property."""
        response_data = {
            "status": "success",
            "threeDSHtmlContent": "<html>3DS Form</html>",
            "token": "payment-token-123",
        }

        response = ThreeDSResponse(response_data)

        assert response.three_ds_html_content == "<html>3DS Form</html>"
        assert response.token == "payment-token-123"

    def test_inherits_from_payment_response(self):
        """Test that ThreeDSResponse inherits PaymentResponse properties."""
        response_data = {
            "status": "success",
            "paymentId": "123",
        }

        response = ThreeDSResponse(response_data)

        # Should have all PaymentResponse methods
        assert response.is_successful() is True
        assert response.payment_id == "123"


@pytest.fixture
def mock_payment_class():
    """Mock the iyzipay.Payment class."""
    with patch("django_iyzico.client.iyzipay.Payment") as mock:
        yield mock


@pytest.fixture
def mock_threeds_initialize_class():
    """Mock the iyzipay.ThreedsInitialize class."""
    with patch("django_iyzico.client.iyzipay.ThreedsInitialize") as mock:
        yield mock


@pytest.fixture
def mock_threeds_payment_class():
    """Mock the iyzipay.ThreedsPayment class."""
    with patch("django_iyzico.client.iyzipay.ThreedsPayment") as mock:
        yield mock


@pytest.fixture
def sample_order_data():
    """Sample order data for payment."""
    return {
        "conversationId": "test-conv-123",
        "price": "100.00",
        "paidPrice": "100.00",
        "currency": "TRY",
        "basketId": "B123",
    }


@pytest.fixture
def sample_payment_card():
    """Sample payment card data."""
    return {
        "cardHolderName": "John Doe",
        "cardNumber": "5528790000000008",
        "expireMonth": "12",
        "expireYear": "2030",
        "cvc": "123",
    }


@pytest.fixture
def sample_buyer():
    """Sample buyer data."""
    return {
        "id": "BY123",
        "name": "John",
        "surname": "Doe",
        "email": "john@example.com",
        "identityNumber": "11111111111",
        "registrationAddress": "Test Address",
        "city": "Istanbul",
        "country": "Turkey",
        "gsmNumber": "+905551234567",
    }


@pytest.fixture
def sample_billing_address():
    """Sample billing address."""
    return {
        "address": "Test Address 123",
        "city": "Istanbul",
        "country": "Turkey",
        "zipCode": "34000",
    }


class TestIyzicoClientInit:
    """Test IyzicoClient initialization."""

    def test_initializes_with_default_settings(self):
        """Test client initializes with default settings."""
        client = IyzicoClient()

        assert client.settings is not None

    def test_initializes_with_custom_settings(self):
        """Test client initializes with custom settings."""
        from django_iyzico.settings import IyzicoSettings

        custom_settings = IyzicoSettings()
        client = IyzicoClient(settings=custom_settings)

        assert client.settings == custom_settings

    def test_get_options(self):
        """Test get_options() returns API options."""
        client = IyzicoClient()
        options = client.get_options()

        assert "api_key" in options
        assert "secret_key" in options
        assert "base_url" in options

    def test_get_options_caches_result(self):
        """Test that options are cached."""
        client = IyzicoClient()

        options1 = client.get_options()
        options2 = client.get_options()

        # Should be same object (cached)
        assert options1 is options2


class TestCreatePayment:
    """Test create_payment() method."""

    def test_successful_payment(
        self,
        mock_payment_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test successful payment creation."""
        # Mock successful response - iyzipay returns dict directly
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "paymentId": "test-payment-123",
            "conversationId": "test-conv-123",
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
        }
        mock_instance.create.return_value = mock_response_data
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.create_payment(
            order_data=sample_order_data,
            payment_card=sample_payment_card,
            buyer=sample_buyer,
            billing_address=sample_billing_address,
        )

        # Verify response
        assert response.is_successful() is True
        assert response.payment_id == "test-payment-123"

        # Verify SDK was called
        mock_payment_class.assert_called_once()
        mock_instance.create.assert_called_once()

    def test_failed_payment_raises_payment_error(
        self,
        mock_payment_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that failed payment raises PaymentError."""
        # Mock failed response
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "1000",
            "errorMessage": "General error",
        }
        mock_instance.create.return_value = mock_response_data
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.create_payment(
                order_data=sample_order_data,
                payment_card=sample_payment_card,
                buyer=sample_buyer,
                billing_address=sample_billing_address,
            )

        assert "General error" in str(exc_info.value)

    def test_card_error_raises_card_error(
        self,
        mock_payment_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that card-related errors raise CardError."""
        # Mock card error response
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "5006",  # Card declined
            "errorMessage": "Card declined",
        }
        mock_instance.create.return_value = mock_response_data
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.create_payment(
                order_data=sample_order_data,
                payment_card=sample_payment_card,
                buyer=sample_buyer,
                billing_address=sample_billing_address,
            )

        assert "Card declined" in str(exc_info.value)

    def test_invalid_payment_data_raises_validation_error(
        self,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that invalid payment data raises ValidationError."""
        client = IyzicoClient()

        # Missing required fields
        invalid_order_data = {"price": "100.00"}

        with pytest.raises(ValidationError):
            client.create_payment(
                order_data=invalid_order_data,
                payment_card=sample_payment_card,
                buyer=sample_buyer,
                billing_address=sample_billing_address,
            )

    def test_exception_during_payment_raises_payment_error(
        self,
        mock_payment_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that SDK exceptions are wrapped in PaymentError."""
        # Mock SDK exception
        mock_instance = Mock()
        mock_instance.create.side_effect = Exception("SDK error")
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.create_payment(
                order_data=sample_order_data,
                payment_card=sample_payment_card,
                buyer=sample_buyer,
                billing_address=sample_billing_address,
            )

        assert "SDK error" in str(exc_info.value)


class TestCreate3DSPayment:
    """Test create_3ds_payment() method."""

    def test_successful_3ds_initialization(
        self,
        mock_threeds_initialize_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test successful 3DS payment initialization."""
        # Mock successful response
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "threeDSHtmlContent": "<html>3DS Form</html>",
            "token": "payment-token-123",
            "conversationId": "test-conv-123",
        }
        mock_instance.create.return_value = mock_response_data
        mock_threeds_initialize_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.create_3ds_payment(
            order_data=sample_order_data,
            payment_card=sample_payment_card,
            buyer=sample_buyer,
            billing_address=sample_billing_address,
            callback_url="https://example.com/callback/",
        )

        # Verify response
        assert response.is_successful() is True
        assert response.three_ds_html_content == "<html>3DS Form</html>"
        assert response.token == "payment-token-123"

    def test_failed_3ds_initialization_raises_error(
        self,
        mock_threeds_initialize_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that failed 3DS initialization raises ThreeDSecureError."""
        # Mock failed response
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "3001",
            "errorMessage": "3DS initialization failed",
        }
        mock_instance.create.return_value = mock_response_data
        mock_threeds_initialize_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(ThreeDSecureError) as exc_info:
            client.create_3ds_payment(
                order_data=sample_order_data,
                payment_card=sample_payment_card,
                buyer=sample_buyer,
                billing_address=sample_billing_address,
            )

        assert "3DS initialization failed" in str(exc_info.value)

    def test_uses_default_callback_url(
        self,
        mock_threeds_initialize_class,
        sample_order_data,
        sample_payment_card,
        sample_buyer,
        sample_billing_address,
    ):
        """Test that default callback URL is used when not provided."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "threeDSHtmlContent": "<html>3DS</html>",
        }
        mock_instance.create.return_value = mock_response_data
        mock_threeds_initialize_class.return_value = mock_instance

        client = IyzicoClient()
        client.create_3ds_payment(
            order_data=sample_order_data,
            payment_card=sample_payment_card,
            buyer=sample_buyer,
            billing_address=sample_billing_address,
            # callback_url not provided
        )

        # Verify callback_url was set in request
        call_args = mock_instance.create.call_args
        request_data = call_args[0][0]
        assert "callbackUrl" in request_data


class TestComplete3DSPayment:
    """Test complete_3ds_payment() method."""

    def test_successful_3ds_completion(self, mock_threeds_payment_class):
        """Test successful 3DS payment completion."""
        # Mock successful response
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "paymentId": "test-payment-123",
            "conversationId": "test-conv-123",
            "price": "100.00",
            "paidPrice": "100.00",
        }
        mock_instance.create.return_value = mock_response_data
        mock_threeds_payment_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.complete_3ds_payment("payment-token-123")

        assert response.is_successful() is True
        assert response.payment_id == "test-payment-123"

    def test_failed_3ds_completion_raises_error(self, mock_threeds_payment_class):
        """Test that failed 3DS completion raises ThreeDSecureError."""
        # Mock failed response
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "3002",
            "errorMessage": "3DS authentication failed",
        }
        mock_instance.create.return_value = mock_response_data
        mock_threeds_payment_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(ThreeDSecureError) as exc_info:
            client.complete_3ds_payment("payment-token-123")

        assert "3DS authentication failed" in str(exc_info.value)

    def test_missing_token_raises_validation_error(self):
        """Test that missing token raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.complete_3ds_payment("")

        assert "token" in str(exc_info.value).lower()

    def test_none_token_raises_validation_error(self):
        """Test that None token raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError):
            client.complete_3ds_payment(None)


class TestHandlePaymentError:
    """Test _handle_payment_error() method."""

    def test_identifies_card_errors(self):
        """Test that card errors are identified correctly."""
        response_data = {
            "status": "failure",
            "errorCode": "5001",  # Card number invalid
            "errorMessage": "Invalid card number",
        }

        response = PaymentResponse(response_data)
        client = IyzicoClient()

        with pytest.raises(CardError):
            client._handle_payment_error(response)

    def test_raises_payment_error_for_non_card_errors(self):
        """Test that non-card errors raise PaymentError."""
        response_data = {
            "status": "failure",
            "errorCode": "1000",
            "errorMessage": "General error",
        }

        response = PaymentResponse(response_data)
        client = IyzicoClient()

        with pytest.raises(PaymentError):
            client._handle_payment_error(response)


class TestRefundPayment:
    """Test refund_payment() method."""

    @pytest.fixture
    def mock_refund_class(self):
        """Mock the iyzipay.Refund class."""
        with patch("django_iyzico.client.iyzipay.Refund") as mock:
            yield mock

    def test_successful_full_refund(self, mock_refund_class):
        """Test successful full refund."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "paymentId": "payment-123",
            "paymentTransactionId": "refund-456",
            "price": "100.00",
        }
        mock_instance.create.return_value = mock_response_data
        mock_refund_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.refund_payment(
            payment_id="payment-123",
            ip_address="192.168.1.1",
        )

        assert response.is_successful() is True
        assert response.payment_id == "payment-123"
        mock_instance.create.assert_called_once()

    def test_successful_partial_refund(self, mock_refund_class):
        """Test successful partial refund."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "paymentId": "payment-123",
            "price": "50.00",
        }
        mock_instance.create.return_value = mock_response_data
        mock_refund_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.refund_payment(
            payment_id="payment-123",
            ip_address="192.168.1.1",
            amount=Decimal("50.00"),
            reason="Customer requested partial refund",
        )

        assert response.is_successful() is True
        call_args = mock_instance.create.call_args[0][0]
        assert call_args["price"] == "50.00"
        assert call_args["description"] == "Customer requested partial refund"

    def test_refund_missing_payment_id_raises_error(self):
        """Test refund without payment ID raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.refund_payment(payment_id="", ip_address="192.168.1.1")

        assert "MISSING_PAYMENT_ID" in str(exc_info.value)

    def test_refund_missing_ip_address_raises_error(self):
        """Test refund without IP address raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.refund_payment(payment_id="payment-123", ip_address="")

        assert "MISSING_IP_ADDRESS" in str(exc_info.value)

    def test_refund_invalid_ip_address_raises_error(self):
        """Test refund with invalid IP address raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.refund_payment(payment_id="payment-123", ip_address="invalid-ip")

        assert "INVALID_IP_ADDRESS" in str(exc_info.value)

    def test_failed_refund_raises_payment_error(self, mock_refund_class):
        """Test failed refund raises PaymentError."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "1001",
            "errorMessage": "Refund not allowed",
        }
        mock_instance.create.return_value = mock_response_data
        mock_refund_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.refund_payment(payment_id="payment-123", ip_address="192.168.1.1")

        assert "Refund not allowed" in str(exc_info.value)

    def test_refund_sdk_exception_raises_payment_error(self, mock_refund_class):
        """Test SDK exception during refund raises PaymentError."""
        mock_instance = Mock()
        mock_instance.create.side_effect = Exception("SDK error")
        mock_refund_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(PaymentError) as exc_info:
            client.refund_payment(payment_id="payment-123", ip_address="192.168.1.1")

        assert "SDK error" in str(exc_info.value)


class TestRegisterCard:
    """Test register_card() method."""

    @pytest.fixture
    def mock_card_class(self):
        """Mock the iyzipay.Card class."""
        with patch("django_iyzico.client.iyzipay.Card") as mock:
            yield mock

    @pytest.fixture
    def sample_card_info(self):
        """Sample card information for registration."""
        return {
            "cardAlias": "My Card",
            "cardHolderName": "John Doe",
            "cardNumber": "5528790000000008",
            "expireMonth": "12",
            "expireYear": "2030",
        }

    @pytest.fixture
    def sample_buyer(self):
        """Sample buyer info."""
        return {
            "id": "BY123",
            "name": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "identityNumber": "11111111111",
        }

    def test_successful_card_registration(self, mock_card_class, sample_card_info, sample_buyer):
        """Test successful card registration."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "cardToken": "card-token-123",
            "cardUserKey": "card-user-key-456",
            "cardAlias": "My Card",
            "lastFourDigits": "0008",
            "cardAssociation": "MASTER_CARD",
        }
        mock_instance.create.return_value = mock_response_data
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()
        result = client.register_card(
            card_info=sample_card_info,
            buyer=sample_buyer,
        )

        assert result["card_token"] == "card-token-123"
        assert result["card_user_key"] == "card-user-key-456"
        mock_instance.create.assert_called_once()

    def test_card_registration_with_external_id(
        self, mock_card_class, sample_card_info, sample_buyer
    ):
        """Test card registration with external ID."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "cardToken": "card-token-123",
            "cardUserKey": "card-user-key-456",
            "externalId": "EXT-123",
        }
        mock_instance.create.return_value = mock_response_data
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()
        client.register_card(
            card_info=sample_card_info,
            buyer=sample_buyer,
            external_id="EXT-123",
        )

        call_args = mock_instance.create.call_args[0][0]
        assert call_args.get("externalId") == "EXT-123"

    def test_failed_card_registration_raises_error(
        self, mock_card_class, sample_card_info, sample_buyer
    ):
        """Test failed card registration raises CardError."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "5001",
            "errorMessage": "Invalid card number",
        }
        mock_instance.create.return_value = mock_response_data
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.register_card(card_info=sample_card_info, buyer=sample_buyer)

        assert "Invalid card number" in str(exc_info.value)

    def test_card_registration_sdk_exception(self, mock_card_class, sample_card_info, sample_buyer):
        """Test SDK exception during registration raises CardError."""
        mock_instance = Mock()
        mock_instance.create.side_effect = Exception("SDK error")
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.register_card(card_info=sample_card_info, buyer=sample_buyer)

        assert "SDK error" in str(exc_info.value)


class TestDeleteCard:
    """Test delete_card() method."""

    @pytest.fixture
    def mock_card_class(self):
        """Mock the iyzipay.Card class."""
        with patch("django_iyzico.client.iyzipay.Card") as mock:
            yield mock

    def test_successful_card_deletion(self, mock_card_class):
        """Test successful card deletion."""
        mock_instance = Mock()
        mock_response_data = {"status": "success"}
        mock_instance.delete.return_value = mock_response_data
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()
        result = client.delete_card(
            card_token="card-token-123",
            card_user_key="card-user-key-456",
        )

        assert result is True
        mock_instance.delete.assert_called_once()

    def test_delete_card_missing_token_raises_error(self):
        """Test deleting card without token raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.delete_card(card_token="", card_user_key="user-key")

        assert "Card token" in str(exc_info.value)

    def test_delete_card_missing_user_key_raises_error(self):
        """Test deleting card without user key raises ValidationError."""
        client = IyzicoClient()

        with pytest.raises(ValidationError) as exc_info:
            client.delete_card(card_token="card-token", card_user_key="")

        assert "Card user key" in str(exc_info.value)

    def test_failed_card_deletion_raises_error(self, mock_card_class):
        """Test failed card deletion raises CardError."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "1001",
            "errorMessage": "Card not found",
        }
        mock_instance.delete.return_value = mock_response_data
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.delete_card(
                card_token="card-token-123",
                card_user_key="card-user-key-456",
            )

        assert "Card not found" in str(exc_info.value)

    def test_delete_card_sdk_exception(self, mock_card_class):
        """Test SDK exception during deletion raises CardError."""
        mock_instance = Mock()
        mock_instance.delete.side_effect = Exception("SDK error")
        mock_card_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.delete_card(
                card_token="card-token-123",
                card_user_key="card-user-key-456",
            )

        assert "SDK error" in str(exc_info.value)


class TestCreatePaymentWithToken:
    """Test create_payment_with_token() method."""

    @pytest.fixture
    def mock_payment_class(self):
        """Mock the iyzipay.Payment class."""
        with patch("django_iyzico.client.iyzipay.Payment") as mock:
            yield mock

    @pytest.fixture
    def sample_order_data(self):
        """Sample order data for payment."""
        return {
            "conversationId": "test-conv-123",
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
            "basketId": "B123",
        }

    @pytest.fixture
    def sample_buyer(self):
        """Sample buyer data."""
        return {
            "id": "BY123",
            "name": "John",
            "surname": "Doe",
            "email": "john@example.com",
            "identityNumber": "11111111111",
            "registrationAddress": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
        }

    @pytest.fixture
    def sample_address(self):
        """Sample address."""
        return {
            "address": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
        }

    @pytest.fixture
    def sample_basket_items(self):
        """Sample basket items."""
        return [
            {
                "id": "ITEM1",
                "name": "Test Item",
                "category1": "Test Category",
                "itemType": "VIRTUAL",
                "price": "100.00",
            }
        ]

    def test_successful_token_payment(
        self,
        mock_payment_class,
        sample_order_data,
        sample_buyer,
        sample_address,
        sample_basket_items,
    ):
        """Test successful payment with stored card token."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "success",
            "paymentId": "payment-123",
            "price": "100.00",
        }
        mock_instance.create.return_value = mock_response_data
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()
        response = client.create_payment_with_token(
            order_data=sample_order_data,
            card_token="card-token-123",
            card_user_key="user-key-456",
            buyer=sample_buyer,
            billing_address=sample_address,
            shipping_address=sample_address,
            basket_items=sample_basket_items,
        )

        assert response.is_successful() is True
        assert response.payment_id == "payment-123"

        # Verify token data was passed
        call_args = mock_instance.create.call_args[0][0]
        assert call_args["paymentCard"]["cardToken"] == "card-token-123"
        assert call_args["paymentCard"]["cardUserKey"] == "user-key-456"

    def test_failed_token_payment_raises_payment_error(
        self,
        mock_payment_class,
        sample_order_data,
        sample_buyer,
        sample_address,
        sample_basket_items,
    ):
        """Test failed token payment raises PaymentError."""
        mock_instance = Mock()
        mock_response_data = {
            "status": "failure",
            "errorCode": "5006",
            "errorMessage": "Card declined",
        }
        mock_instance.create.return_value = mock_response_data
        mock_payment_class.return_value = mock_instance

        client = IyzicoClient()

        with pytest.raises(CardError) as exc_info:
            client.create_payment_with_token(
                order_data=sample_order_data,
                card_token="card-token-123",
                card_user_key="user-key-456",
                buyer=sample_buyer,
                billing_address=sample_address,
                shipping_address=sample_address,
                basket_items=sample_basket_items,
            )

        assert "Card declined" in str(exc_info.value)
