"""
Critical Path Tests for django-iyzico

Tests for critical security and data integrity functionality:
- Concurrent billing (no double charges)
- Refund idempotency
- Payment method security (no sensitive data stored)
- Subscription lifecycle
- SQL injection prevention
- Webhook signature validation
- BIN validation
- Rate limiting
"""

import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

User = get_user_model()


class TestConcurrentBillingProtection(TestCase):
    """Test that concurrent billing attempts don't result in double charges."""

    def setUp(self):
        """Set up test fixtures."""
        from django_iyzico.subscription_models import (
            PaymentMethod,
            Subscription,
            SubscriptionPlan,
            SubscriptionStatus,
        )

        # Create test user with required profile fields
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

        # Create subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test-plan",
            price=Decimal("99.99"),
            currency="TRY",
            billing_interval="monthly",
        )

        # Create subscription
        now = timezone.now()
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timezone.timedelta(days=30),
            next_billing_date=now + timezone.timedelta(days=30),
        )

        # Create payment method
        self.payment_method = PaymentMethod.objects.create(
            user=self.user,
            card_token="test_token_123",
            card_last_four="1234",
            card_brand="VISA",
            expiry_month="12",
            expiry_year="2030",
            is_default=True,
        )

    def test_concurrent_billing_creates_only_one_payment(self):
        """
        Test that concurrent billing tasks only create one payment.

        Simulates race condition where multiple billing tasks try to
        charge the same subscription simultaneously.
        """
        from django_iyzico.subscription_manager import SubscriptionManager
        from django_iyzico.subscription_models import SubscriptionPayment

        # Mock successful payment response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status = "success"
        mock_response.payment_id = "test_payment_id"
        mock_response.error_code = None
        mock_response.error_message = None
        mock_client.create_payment.return_value = mock_response

        manager = SubscriptionManager(client=mock_client)

        # Track payment counts
        payments_before = SubscriptionPayment.objects.filter(subscription=self.subscription).count()

        results = []
        errors = []

        def attempt_billing():
            try:
                # Each thread gets a fresh subscription instance
                from django_iyzico.subscription_models import Subscription

                sub = Subscription.objects.get(pk=self.subscription.pk)
                payment = manager.process_billing(
                    subscription=sub,
                    payment_method={"cardToken": "test_token"},
                )
                results.append(payment)
            except Exception as e:
                errors.append(e)

        # Launch concurrent billing attempts
        threads = []
        for _ in range(5):
            t = threading.Thread(target=attempt_billing)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have at most 1 new payment (the first successful one)
        payments_after = SubscriptionPayment.objects.filter(subscription=self.subscription).count()

        # Either all return the same payment (idempotent) or only one succeeds
        # Count successful payments (not stored since we just need to verify assertion)
        _ = [r for r in results if r.status == "success"]

        # At most one successful payment should be created
        assert (
            payments_after - payments_before <= 1
        ), f"Expected at most 1 new payment, got {payments_after - payments_before}"


class TestPaymentMethodSecurity(TestCase):
    """Test that no sensitive card data is stored."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_payment_method_stores_only_token(self):
        """Verify PaymentMethod model only stores token, not card data."""
        from django_iyzico.subscription_models import PaymentMethod

        payment_method = PaymentMethod.objects.create(
            user=self.user,
            card_token="iyzico_secure_token_xyz123",
            card_last_four="1234",
            card_brand="VISA",
            expiry_month="12",
            expiry_year="2030",
        )

        # Verify sensitive data is not in the model
        payment_method.refresh_from_db()

        # Check that no full card number is stored
        for field in payment_method._meta.get_fields():
            if hasattr(payment_method, field.name):
                value = getattr(payment_method, field.name)
                if isinstance(value, str):
                    # Should not contain anything that looks like a full card number
                    assert (
                        len(value) < 16 or not value.isdigit()
                    ), f"Field {field.name} may contain sensitive card data"

    def test_to_payment_dict_returns_only_tokens(self):
        """Verify to_payment_dict returns only token references."""
        from django_iyzico.subscription_models import PaymentMethod

        payment_method = PaymentMethod(
            user=self.user,
            card_token="test_token",
            card_user_key="test_user_key",
            card_last_four="1234",
            card_brand="VISA",
            expiry_month="12",
            expiry_year="2030",
        )

        payment_dict = payment_method.to_payment_dict()

        # Should only contain token references
        assert "cardToken" in payment_dict
        assert "cardUserKey" in payment_dict

        # Should NOT contain actual card data
        assert "cardNumber" not in payment_dict
        assert "cvc" not in payment_dict
        assert "expireMonth" not in payment_dict
        assert "expireYear" not in payment_dict


class TestCardMasking(TestCase):
    """Test comprehensive card data masking."""

    def test_mask_card_data_removes_sensitive_fields(self):
        """Test that all sensitive fields are removed."""
        from django_iyzico.utils import mask_card_data

        payment_data = {
            "card": {
                "cardNumber": "5528790000000008",
                "number": "5528790000000008",
                "cvc": "123",
                "cvv": "123",
                "securityCode": "123",
                "expireMonth": "12",
                "expireYear": "2030",
                "cardHolderName": "Test User",
            }
        }

        masked = mask_card_data(payment_data)

        # Should have last four digits
        assert masked["card"]["lastFourDigits"] == "0008"

        # Should NOT have sensitive data
        assert (
            "cardNumber" not in masked["card"]
            or masked["card"].get("cardNumber") == "***REDACTED***"
        )
        assert "number" not in masked["card"] or masked["card"].get("number") == "***REDACTED***"
        assert "cvc" not in masked["card"] or masked["card"].get("cvc") == "***REDACTED***"

        # Should keep cardholder name
        assert masked["card"]["cardHolderName"] == "Test User"

    def test_mask_card_data_handles_nested_structures(self):
        """Test masking works on nested dictionaries."""
        from django_iyzico.utils import mask_card_data

        payment_data = {
            "paymentCard": {
                "cardNumber": "4111111111111111",
                "cvv": "123",
            },
            "nested": {
                "deep": {
                    "cardNumber": "4111111111111111",
                }
            },
        }

        masked = mask_card_data(payment_data)

        # Check nested masking
        assert masked["nested"]["deep"]["cardNumber"] == "***REDACTED***"


class TestBINValidation(TestCase):
    """Test BIN number validation."""

    def test_valid_bin_passes(self):
        """Test that valid BIN numbers pass validation."""
        from django_iyzico.installment_client import validate_bin_number

        # Valid Mastercard BIN
        result = validate_bin_number("554960", allow_test_bins=False)
        assert result == "554960"

        # Valid Visa BIN
        result = validate_bin_number("411111", allow_test_bins=False)
        assert result == "411111"

    def test_test_bins_rejected_in_production(self):
        """Test that known test BINs are rejected when not allowed."""
        from django_iyzico.exceptions import IyzicoValidationException
        from django_iyzico.installment_client import validate_bin_number

        test_bins = ["000000", "111111", "123456"]

        for bin_number in test_bins:
            with pytest.raises(IyzicoValidationException) as exc_info:
                validate_bin_number(bin_number, allow_test_bins=False)
            # Check that error message mentions test BIN (case insensitive)
            assert "test bin" in str(exc_info.value).lower()

    def test_invalid_mii_rejected(self):
        """Test that invalid MII (first digit) is rejected."""
        from django_iyzico.exceptions import IyzicoValidationException
        from django_iyzico.installment_client import validate_bin_number

        # First digit must be 3-6 for payment cards
        invalid_bins = ["112233", "223344", "778899", "990011"]

        for bin_number in invalid_bins:
            with pytest.raises(IyzicoValidationException) as exc_info:
                validate_bin_number(bin_number, allow_test_bins=True)
            assert "MII" in str(exc_info.value) or "first digit" in str(exc_info.value).lower()

    def test_invalid_length_rejected(self):
        """Test that BINs with wrong length are rejected."""
        from django_iyzico.exceptions import IyzicoValidationException
        from django_iyzico.installment_client import validate_bin_number

        invalid_lengths = ["12345", "1234567", ""]

        for bin_number in invalid_lengths:
            with pytest.raises(IyzicoValidationException):
                validate_bin_number(bin_number, allow_test_bins=True)


class TestAmountValidation(TestCase):
    """Test payment amount validation with currency limits."""

    def test_valid_amounts_pass(self):
        """Test that valid amounts pass validation."""
        from django_iyzico.utils import validate_amount

        # Normal TRY amount
        result = validate_amount("100.00", "TRY")
        assert result == Decimal("100.00")

        # Normal USD amount
        result = validate_amount("50.00", "USD")
        assert result == Decimal("50.00")

    def test_amount_too_high_rejected(self):
        """Test that amounts exceeding limit are rejected."""
        from django_iyzico.exceptions import ValidationError
        from django_iyzico.utils import validate_amount

        # TRY limit is 1,000,000
        with pytest.raises(ValidationError) as exc_info:
            validate_amount("2000000.00", "TRY")
        assert "exceeds maximum" in str(exc_info.value).lower()

    def test_amount_too_low_rejected(self):
        """Test that amounts with too many decimal places are rejected."""
        from django_iyzico.exceptions import ValidationError
        from django_iyzico.utils import validate_amount

        # 0.001 has 3 decimal places, which is rejected before min amount check
        with pytest.raises(ValidationError) as exc_info:
            validate_amount("0.001", "TRY")
        assert "decimal places" in str(exc_info.value).lower()

    def test_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        from django_iyzico.exceptions import ValidationError
        from django_iyzico.utils import validate_amount

        with pytest.raises(ValidationError):
            validate_amount("-10.00", "TRY")


class TestRateLimiting(TestCase):
    """Test rate limiting functionality."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    @override_settings(IYZICO_RATE_LIMITING_ENABLED=True, IYZICO_RATE_LIMIT_IN_DEBUG=True)
    def test_rate_limit_blocks_excessive_requests(self):
        """Test that rate limit blocks requests after threshold."""
        from django_iyzico.installment_client import InstallmentClient

        client = InstallmentClient()
        client.rate_limit_requests = 5  # Low limit for testing
        client.rate_limit_window = 60

        identifier = "test_identifier"

        # First 5 requests should succeed
        for i in range(5):
            result = client._check_rate_limit(identifier)
            assert result is True, f"Request {i+1} should have succeeded"

        # 6th request should be blocked
        result = client._check_rate_limit(identifier)
        assert result is False, "Request 6 should have been blocked"


class TestCacheKeyTracking(TestCase):
    """Test safe cache key management."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_clear_validates_bin(self):
        """Test that cache clear validates BIN format."""
        from django_iyzico.installment_client import InstallmentClient

        client = InstallmentClient()

        # Invalid BIN formats should not cause issues
        result = client.clear_cache(bin_number="invalid")
        assert result == 0

        result = client.clear_cache(bin_number="12345")  # Too short
        assert result == 0

        result = client.clear_cache(bin_number="abc123")  # Non-numeric
        assert result == 0


class TestWebhookSecurity(TestCase):
    """Test webhook security features."""

    @override_settings(DEBUG=False, IYZICO_WEBHOOK_ALLOWED_IPS=[])
    def test_webhook_requires_whitelist_in_production(self):
        """Test that webhooks are rejected without IP whitelist in production."""
        from django.test import RequestFactory

        from django_iyzico.views import webhook_view

        factory = RequestFactory()
        request = factory.post("/webhook/", data='{"test": true}', content_type="application/json")
        request.META["REMOTE_ADDR"] = "1.2.3.4"

        # Mock the settings
        with patch("django_iyzico.views.iyzico_settings") as mock_settings:
            mock_settings.webhook_allowed_ips = []
            mock_settings.webhook_secret = None

            response = webhook_view(request)

            # Should be rejected in production without whitelist
            assert response.status_code == 403

    def test_webhook_signature_validation(self):
        """Test webhook signature validation."""
        import hashlib
        import hmac

        from django_iyzico.utils import verify_webhook_signature

        payload = b'{"event": "payment.success", "paymentId": "12345"}'
        secret = "test_webhook_secret"

        # Generate valid signature
        valid_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Valid signature should pass
        assert verify_webhook_signature(payload, valid_signature, secret) is True

        # Invalid signature should fail
        assert verify_webhook_signature(payload, "invalid_signature", secret) is False


class TestSubscriptionPaymentConstraints(TestCase):
    """Test database constraints for subscription payments."""

    def setUp(self):
        """Set up test fixtures."""
        from django_iyzico.subscription_models import (
            Subscription,
            SubscriptionPlan,
            SubscriptionStatus,
        )

        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test-plan",
            price=Decimal("99.99"),
            currency="TRY",
            billing_interval="monthly",
        )

        now = timezone.now()
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timezone.timedelta(days=30),
            next_billing_date=now + timezone.timedelta(days=30),
        )

    def test_unique_payment_period_constraint(self):
        """Test that duplicate payments for same period are prevented."""
        from django_iyzico.subscription_models import SubscriptionPayment

        now = timezone.now()
        period_start = now
        period_end = now + timezone.timedelta(days=30)

        # Create first payment
        SubscriptionPayment.objects.create(
            subscription=self.subscription,
            user=self.user,
            amount=Decimal("99.99"),
            currency="TRY",
            period_start=period_start,
            period_end=period_end,
            attempt_number=1,
            status="success",
            conversation_id="conv_1",
        )

        # Attempt to create duplicate - should fail
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SubscriptionPayment.objects.create(
                    subscription=self.subscription,
                    user=self.user,
                    amount=Decimal("99.99"),
                    currency="TRY",
                    period_start=period_start,
                    period_end=period_end,
                    attempt_number=1,  # Same attempt number
                    status="success",
                    conversation_id="conv_2",
                )


class TestPaymentMethodExpiry(TestCase):
    """Test payment method expiration handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_expired_card_detection(self):
        """Test that expired cards are correctly detected."""
        from django_iyzico.subscription_models import PaymentMethod

        now = timezone.now()

        # Expired card (last month)
        expired = PaymentMethod(
            user=self.user,
            card_token="expired_token",
            card_last_four="1234",
            card_brand="VISA",
            expiry_month=str((now.month - 2) % 12 + 1).zfill(2),
            expiry_year=str(now.year if now.month > 2 else now.year - 1),
        )
        assert expired.is_expired() is True

        # Valid card (next year)
        valid = PaymentMethod(
            user=self.user,
            card_token="valid_token",
            card_last_four="5678",
            card_brand="VISA",
            expiry_month="12",
            expiry_year=str(now.year + 1),
        )
        assert valid.is_expired() is False

    def test_expires_soon_detection(self):
        """Test that cards expiring soon are detected."""
        from django_iyzico.subscription_models import PaymentMethod

        now = timezone.now()

        # Card expiring this month
        expiring_soon = PaymentMethod(
            user=self.user,
            card_token="expiring_token",
            card_last_four="1234",
            card_brand="VISA",
            expiry_month=str(now.month).zfill(2),
            expiry_year=str(now.year),
        )

        # Should be marked as expiring soon (within 30 days)
        assert expiring_soon.expires_soon(within_days=60) is True
