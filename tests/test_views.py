"""
Tests for django-iyzico views.

Tests 3DS callback and webhook views.
"""

import json
from unittest.mock import Mock, patch

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from django_iyzico.exceptions import ThreeDSecureError
from django_iyzico.signals import threeds_completed, threeds_failed, webhook_received
from django_iyzico.views import threeds_callback_view, webhook_view


@pytest.fixture
def request_factory():
    """Django request factory."""
    return RequestFactory()


@pytest.fixture
def mock_iyzico_client():
    """Mock IyzicoClient."""
    with patch("django_iyzico.views.IyzicoClient") as mock:
        yield mock


def add_session_to_request(request):
    """Add session to request for testing."""
    middleware = SessionMiddleware(lambda x: x)
    middleware.process_request(request)
    request.session.save()
    return request


def create_json_post_request(request_factory, url, data):
    """
    Create a POST request with JSON data.

    Django's RequestFactory doesn't set request.body properly when using
    data=json.dumps(...), so we need to set it explicitly.
    """
    json_data = json.dumps(data)
    request = request_factory.post(
        url,
        data=json_data,
        content_type="application/json",
    )
    # Explicitly set the body attribute for views that read request.body
    request._body = json_data.encode("utf-8")
    return request


@pytest.mark.django_db
class TestThreeDSCallbackView:
    """Test threeds_callback_view."""

    def test_successful_3ds_callback_get(self, request_factory, mock_iyzico_client):
        """Test successful 3DS callback via GET."""
        # Mock successful payment completion
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = True
        mock_response.payment_id = "test-payment-123"
        mock_response.conversation_id = "test-conv-123"
        mock_response.to_dict.return_value = {"status": "success"}
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Create request with token
        request = request_factory.get("/callback/?token=payment-token-123")
        request = add_session_to_request(request)

        # Call view
        response = threeds_callback_view(request)

        # Verify redirect to success
        assert response.status_code == 302
        assert "success" in response.url or "payment" in response.url

        # Verify client was called
        mock_client_instance.complete_3ds_payment.assert_called_once_with("payment-token-123")

    def test_successful_3ds_callback_post(self, request_factory, mock_iyzico_client):
        """Test successful 3DS callback via POST."""
        # Mock successful payment completion
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = True
        mock_response.payment_id = "test-payment-123"
        mock_response.conversation_id = "test-conv-123"
        mock_response.to_dict.return_value = {"status": "success"}
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Create POST request
        request = request_factory.post("/callback/", {"paymentId": "payment-token-123"})
        request = add_session_to_request(request)

        # Call view
        response = threeds_callback_view(request)

        # Verify redirect to success
        assert response.status_code == 302

    def test_failed_3ds_callback(self, request_factory, mock_iyzico_client):
        """Test failed 3DS callback."""
        # Mock failed payment completion
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = False
        mock_response.error_code = "3002"
        mock_response.error_message = "Authentication failed"
        mock_response.conversation_id = "test-conv-123"
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Create request
        request = request_factory.get("/callback/?token=payment-token-123")
        request = add_session_to_request(request)

        # Call view
        response = threeds_callback_view(request)

        # Verify redirect to error
        assert response.status_code == 302
        assert "error" in response.url or "payment" in response.url

    def test_missing_token_redirects_to_error(self, request_factory):
        """Test that missing token redirects to error."""
        request = request_factory.get("/callback/")  # No token
        request = add_session_to_request(request)

        response = threeds_callback_view(request)

        # Should redirect to error
        assert response.status_code == 302

    def test_triggers_success_signal(self, request_factory, mock_iyzico_client):
        """Test that threeds_completed signal is triggered on success."""
        # Mock successful payment
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = True
        mock_response.payment_id = "test-payment-123"
        mock_response.conversation_id = "test-conv-123"
        mock_response.to_dict.return_value = {"status": "success"}
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Connect signal receiver
        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        threeds_completed.connect(receiver)

        try:
            request = request_factory.get("/callback/?token=payment-token-123")
            request = add_session_to_request(request)

            threeds_callback_view(request)

            # Verify signal was triggered
            assert len(signal_received) == 1
            assert signal_received[0]["payment_id"] == "test-payment-123"
        finally:
            threeds_completed.disconnect(receiver)

    def test_triggers_failure_signal(self, request_factory, mock_iyzico_client):
        """Test that threeds_failed signal is triggered on failure."""
        # Mock failed payment
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = False
        mock_response.error_code = "3002"
        mock_response.error_message = "Failed"
        mock_response.conversation_id = "test-conv-123"
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Connect signal receiver
        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        threeds_failed.connect(receiver)

        try:
            request = request_factory.get("/callback/?token=payment-token-123")
            request = add_session_to_request(request)

            threeds_callback_view(request)

            # Verify signal was triggered
            assert len(signal_received) == 1
            assert signal_received[0]["error_code"] == "3002"
        finally:
            threeds_failed.disconnect(receiver)

    def test_stores_payment_info_in_session(self, request_factory, mock_iyzico_client):
        """Test that payment info is stored in session."""
        # Mock successful payment
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = True
        mock_response.payment_id = "test-payment-123"
        mock_response.conversation_id = "test-conv-123"
        mock_response.to_dict.return_value = {"status": "success"}
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        request = request_factory.get("/callback/?token=payment-token-123")
        request = add_session_to_request(request)

        threeds_callback_view(request)

        # Verify session data
        assert request.session.get("last_payment_id") == "test-payment-123"
        assert request.session.get("last_payment_status") == "success"

    def test_threeds_error_triggers_failed_signal(self, request_factory, mock_iyzico_client):
        """Test ThreeDSecureError triggers failed signal."""
        # Mock IyzicoClient to raise ThreeDSecureError
        mock_client_instance = Mock()
        mock_client_instance.complete_3ds_payment.side_effect = ThreeDSecureError(
            "3DS authentication failed", error_code="3DS_ERROR"
        )
        mock_iyzico_client.return_value = mock_client_instance

        # Connect signal receiver
        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        threeds_failed.connect(receiver)

        try:
            request = request_factory.get("/callback/?token=test-token")
            request = add_session_to_request(request)

            # Should handle error gracefully
            response = threeds_callback_view(request)
            assert response.status_code == 302  # Redirect

            # Verify signal was triggered
            assert len(signal_received) == 1
            assert signal_received[0]["error_code"] == "3DS_ERROR"
            assert "3DS authentication failed" in signal_received[0]["error_message"]
        finally:
            threeds_failed.disconnect(receiver)

    def test_unexpected_error_triggers_failed_signal(self, request_factory, mock_iyzico_client):
        """Test unexpected exception triggers failed signal."""
        # Mock IyzicoClient to raise unexpected exception
        mock_client_instance = Mock()
        mock_client_instance.complete_3ds_payment.side_effect = Exception(
            "Unexpected database error"
        )
        mock_iyzico_client.return_value = mock_client_instance

        # Connect signal receiver
        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        threeds_failed.connect(receiver)

        try:
            request = request_factory.get("/callback/?token=test-token")
            request = add_session_to_request(request)

            response = threeds_callback_view(request)
            assert response.status_code == 302  # Redirect

            # Verify signal was triggered with generic error
            assert len(signal_received) == 1
            assert signal_received[0]["error_code"] == "UNEXPECTED_ERROR"
            assert signal_received[0]["conversation_id"] is None
        finally:
            threeds_failed.disconnect(receiver)

    def test_stores_error_info_in_session(self, request_factory, mock_iyzico_client):
        """Test that error info is stored in session."""
        # Mock failed payment
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = False
        mock_response.error_code = "5001"
        mock_response.error_message = "Card declined"
        mock_response.conversation_id = "test-conv-123"
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        request = request_factory.get("/callback/?token=test-token")
        request = add_session_to_request(request)

        threeds_callback_view(request)

        # Verify session error data
        assert request.session.get("last_payment_status") == "failed"
        assert request.session.get("last_payment_error") == "Card declined"
        assert request.session.get("last_payment_error_code") == "5001"
        assert request.session.get("last_payment_conversation_id") == "test-conv-123"


class TestWebhookView:
    """Test webhook_view."""

    def test_successful_webhook(self, request_factory):
        """Test successful webhook processing."""
        webhook_data = {
            "iyziEventType": "payment.success",
            "paymentId": "test-payment-123",
            "conversationId": "test-conv-123",
            "status": "success",
        }

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)

        response = webhook_view(request)

        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert response_data["status"] == "success"

    def test_triggers_webhook_signal(self, request_factory):
        """Test that webhook_received signal is triggered."""
        webhook_data = {
            "iyziEventType": "payment.success",
            "paymentId": "test-payment-123",
            "conversationId": "test-conv-123",
        }

        # Connect signal receiver
        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        webhook_received.connect(receiver)

        try:
            request = create_json_post_request(request_factory, "/webhook/", webhook_data)

            webhook_view(request)

            # Verify signal was triggered
            assert len(signal_received) == 1
            assert signal_received[0]["event_type"] == "payment.success"
            assert signal_received[0]["payment_id"] == "test-payment-123"
        finally:
            webhook_received.disconnect(receiver)

    def test_invalid_json_returns_200(self, request_factory):
        """Test that invalid JSON still returns 200 (prevents retry spam)."""
        request = request_factory.post(
            "/webhook/",
            data="not valid json",
            content_type="application/json",
        )
        # Set invalid body
        request._body = b"not valid json"

        response = webhook_view(request)

        # Should still return 200 to avoid retry
        assert response.status_code == 200

    def test_exception_during_processing_returns_200(self, request_factory):
        """Test that exceptions still return 200 (prevents retry spam)."""
        webhook_data = {
            "iyziEventType": "payment.success",
            "paymentId": "test-payment-123",
        }

        # Connect receiver that raises exception
        def failing_receiver(sender, **kwargs):
            raise Exception("Test exception")

        webhook_received.connect(failing_receiver)

        try:
            request = create_json_post_request(request_factory, "/webhook/", webhook_data)

            response = webhook_view(request)

            # Should still return 200
            assert response.status_code == 200
        finally:
            webhook_received.disconnect(failing_receiver)

    def test_extracts_webhook_fields(self, request_factory):
        """Test that webhook fields are properly extracted."""
        webhook_data = {
            "iyziEventType": "payment.refund",
            "paymentId": "payment-123",
            "conversationId": "conv-123",
            "refundId": "refund-123",
        }

        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        webhook_received.connect(receiver)

        try:
            request = create_json_post_request(request_factory, "/webhook/", webhook_data)

            webhook_view(request)

            # Verify extracted fields
            assert signal_received[0]["event_type"] == "payment.refund"
            assert signal_received[0]["payment_id"] == "payment-123"
            assert signal_received[0]["conversation_id"] == "conv-123"
            assert signal_received[0]["data"]["refundId"] == "refund-123"
        finally:
            webhook_received.disconnect(receiver)


class TestWebhookViewSecurity:
    """Test webhook view security features."""

    @patch("django.conf.settings.IYZICO_WEBHOOK_SECRET", "test-secret", create=True)
    def test_webhook_with_invalid_signature_returns_403(self, request_factory):
        """Test webhook with invalid signature is rejected."""
        webhook_data = {"iyziEventType": "payment.success", "paymentId": "test-123"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        request.META["HTTP_X_IYZICO_SIGNATURE"] = "invalid-signature"

        response = webhook_view(request)
        assert response.status_code == 403
        response_data = json.loads(response.content)
        assert "signature" in response_data["message"].lower()

    @patch("django.conf.settings.IYZICO_WEBHOOK_ALLOWED_IPS", ["192.168.1.1"], create=True)
    def test_webhook_from_disallowed_ip_returns_403(self, request_factory):
        """Test webhook from disallowed IP is rejected."""
        webhook_data = {"iyziEventType": "payment.success"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        response = webhook_view(request)
        assert response.status_code == 403
        response_data = json.loads(response.content)
        assert "ip" in response_data["message"].lower()

    @patch("django.conf.settings.IYZICO_WEBHOOK_SECRET", "test-secret", create=True)
    def test_webhook_with_valid_signature(self, request_factory):
        """Test webhook with valid signature is accepted."""
        import hashlib
        import hmac

        webhook_data = {"iyziEventType": "payment.success", "paymentId": "test-123"}
        secret = "test-secret"
        payload = json.dumps(webhook_data).encode("utf-8")
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        request.META["HTTP_X_IYZICO_SIGNATURE"] = signature

        response = webhook_view(request)
        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert response_data["status"] == "success"

    @patch("django.conf.settings.IYZICO_WEBHOOK_ALLOWED_IPS", ["192.168.1.1"], create=True)
    def test_webhook_from_allowed_ip(self, request_factory):
        """Test webhook from allowed IP is accepted."""
        webhook_data = {"iyziEventType": "payment.success"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        response = webhook_view(request)
        assert response.status_code == 200

    @patch("django.conf.settings.IYZICO_WEBHOOK_ALLOWED_IPS", ["192.168.1.0/24"], create=True)
    def test_webhook_from_ip_in_cidr_range(self, request_factory):
        """Test webhook from IP in CIDR range is accepted."""
        webhook_data = {"iyziEventType": "payment.success"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        request.META["REMOTE_ADDR"] = "192.168.1.50"

        response = webhook_view(request)
        assert response.status_code == 200

    @patch("django.conf.settings.IYZICO_WEBHOOK_SECRET", "", create=True)
    def test_webhook_no_secret_configured_skips_validation(self, request_factory):
        """Test webhook without secret configured skips signature validation."""
        webhook_data = {"iyziEventType": "payment.success"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        # Even with invalid signature, should pass
        request.META["HTTP_X_IYZICO_SIGNATURE"] = "invalid"

        response = webhook_view(request)
        assert response.status_code == 200

    @patch("django.conf.settings.IYZICO_WEBHOOK_ALLOWED_IPS", ["203.0.113.1"], create=True)
    def test_webhook_with_x_forwarded_for_header(self, request_factory):
        """Test webhook IP extraction from X-Forwarded-For header."""
        webhook_data = {"iyziEventType": "payment.success"}

        request = create_json_post_request(request_factory, "/webhook/", webhook_data)
        # Set X-Forwarded-For header (proxied request)
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.1"
        request.META["REMOTE_ADDR"] = "10.0.0.1"

        response = webhook_view(request)
        # Should use first IP from X-Forwarded-For
        assert response.status_code == 200


class TestWebhookTestView:
    """Test test_webhook_view."""

    @patch("django.conf.settings")
    def test_test_webhook_in_debug_mode(self, mock_settings, request_factory):
        """Test that test webhook works in DEBUG mode."""
        # Import the view locally to avoid pytest collecting it as a test
        from django_iyzico.views import test_webhook_view as test_webhook_view_impl

        mock_settings.DEBUG = True

        request = request_factory.post("/webhook/test/")

        response = test_webhook_view_impl(request)

        assert response.status_code == 200
        response_data = json.loads(response.content)
        assert response_data["status"] == "success"

    @patch("django.conf.settings")
    def test_test_webhook_disabled_in_production(self, mock_settings, request_factory):
        """Test that test webhook is disabled in production."""
        # Import the view locally to avoid pytest collecting it as a test
        from django_iyzico.views import test_webhook_view as test_webhook_view_impl

        mock_settings.DEBUG = False

        request = request_factory.post("/webhook/test/")

        response = test_webhook_view_impl(request)

        assert response.status_code == 403

    @patch("django.conf.settings")
    def test_test_webhook_triggers_signal(self, mock_settings, request_factory):
        """Test that test webhook triggers webhook_received signal."""
        # Import the view locally to avoid pytest collecting it as a test
        from django_iyzico.views import test_webhook_view as test_webhook_view_impl

        mock_settings.DEBUG = True

        signal_received = []

        def receiver(sender, **kwargs):
            signal_received.append(kwargs)

        webhook_received.connect(receiver)

        try:
            request = request_factory.post("/webhook/test/")

            test_webhook_view_impl(request)

            # Verify signal was triggered
            assert len(signal_received) == 1
            assert signal_received[0]["event_type"] == "test_event"
            assert signal_received[0]["data"]["test"] is True
        finally:
            webhook_received.disconnect(receiver)


@pytest.mark.django_db
class TestViewCSRFExemption:
    """Test that views are properly CSRF exempt."""

    def test_threeds_callback_csrf_exempt(self, request_factory, mock_iyzico_client):
        """Test that 3DS callback is CSRF exempt."""
        # Mock response
        mock_client_instance = Mock()
        mock_response = Mock()
        mock_response.is_successful.return_value = True
        mock_response.payment_id = "123"
        mock_response.conversation_id = "conv-123"
        mock_response.to_dict.return_value = {}
        mock_client_instance.complete_3ds_payment.return_value = mock_response
        mock_iyzico_client.return_value = mock_client_instance

        # Request without CSRF token
        request = request_factory.post("/callback/", {"paymentId": "token-123"})
        request = add_session_to_request(request)

        # Should not raise CSRF error
        response = threeds_callback_view(request)
        assert response.status_code == 302

    def test_webhook_view_csrf_exempt(self, request_factory):
        """Test that webhook view is CSRF exempt."""
        webhook_data = {"iyziEventType": "test"}

        # Request without CSRF token
        request = create_json_post_request(request_factory, "/webhook/", webhook_data)

        # Should not raise CSRF error
        response = webhook_view(request)
        assert response.status_code == 200
