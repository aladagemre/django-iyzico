"""
Tests for django-iyzico monitoring module.

Tests the MonitoringService class, metrics collection, and logging utilities.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from django_iyzico.monitoring import (
    MonitoringService,
    PaymentMetrics,
    get_monitoring_service,
    monitor_timing,
)


class TestPaymentMetrics:
    """Tests for PaymentMetrics dataclass."""

    def test_default_values(self):
        """Test default initialization values."""
        metrics = PaymentMetrics()

        assert metrics.total_attempts == 0
        assert metrics.successful == 0
        assert metrics.failed == 0
        assert metrics.total_amount == Decimal("0.00")
        assert metrics.average_duration_ms == 0.0
        assert metrics.last_failure_reason is None
        assert metrics.period_start is not None

    def test_custom_values(self):
        """Test initialization with custom values."""
        now = timezone.now()
        metrics = PaymentMetrics(
            total_attempts=100,
            successful=95,
            failed=5,
            total_amount=Decimal("5000.00"),
            average_duration_ms=250.5,
            last_failure_reason="Card declined",
            period_start=now,
        )

        assert metrics.total_attempts == 100
        assert metrics.successful == 95
        assert metrics.failed == 5
        assert metrics.total_amount == Decimal("5000.00")
        assert metrics.average_duration_ms == 250.5
        assert metrics.last_failure_reason == "Card declined"
        assert metrics.period_start == now


@pytest.mark.django_db
class TestMonitoringService(TestCase):
    """Tests for MonitoringService class."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()
        self.service = MonitoringService()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_init_default_config(self):
        """Test initialization with default config."""
        service = MonitoringService()

        assert service.log_payments is True
        assert service.alert_on_double_billing is True
        assert service.alert_on_high_failure_rate is True
        assert service.failure_rate_threshold == 0.05

    @override_settings(
        IYZICO_MONITORING={
            "LOG_PAYMENTS": False,
            "ALERT_ON_DOUBLE_BILLING": False,
            "ALERT_ON_HIGH_FAILURE_RATE": False,
            "FAILURE_RATE_THRESHOLD": 0.10,
        }
    )
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        service = MonitoringService()

        assert service.log_payments is False
        assert service.alert_on_double_billing is False
        assert service.alert_on_high_failure_rate is False
        assert service.failure_rate_threshold == 0.10

    # -------------------------------------------------------------------------
    # Payment Event Logging Tests
    # -------------------------------------------------------------------------

    def test_log_payment_attempt(self):
        """Test logging payment attempt."""
        with patch("django_iyzico.monitoring.payment_logger") as mock_logger:
            self.service.log_payment_attempt(
                user_id=1,
                amount=Decimal("100.00"),
                currency="TRY",
                payment_type="one_time",
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Payment attempt" in call_args[0][0]
            assert "payment_data" in call_args[1]["extra"]

    def test_log_payment_attempt_with_metadata(self):
        """Test logging payment attempt with metadata."""
        with patch("django_iyzico.monitoring.payment_logger") as mock_logger:
            self.service.log_payment_attempt(
                user_id=1,
                amount=Decimal("100.00"),
                currency="TRY",
                metadata={"order_id": "ORD123"},
            )

            call_args = mock_logger.info.call_args
            log_data = call_args[1]["extra"]["payment_data"]
            assert "metadata" in log_data

    @override_settings(IYZICO_MONITORING={"LOG_PAYMENTS": False})
    def test_log_payment_attempt_disabled(self):
        """Test that logging is skipped when disabled."""
        service = MonitoringService()

        with patch("django_iyzico.monitoring.payment_logger") as mock_logger:
            service.log_payment_attempt(
                user_id=1,
                amount=Decimal("100.00"),
                currency="TRY",
            )

            mock_logger.info.assert_not_called()

    def test_log_payment_success(self):
        """Test logging payment success."""
        with patch("django_iyzico.monitoring.payment_logger") as mock_logger:
            self.service.log_payment_success(
                payment_id="pay_123",
                user_id=1,
                amount=Decimal("100.00"),
                currency="TRY",
                duration_ms=250.5,
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Payment success" in call_args[0][0]

    def test_log_payment_success_records_amount(self):
        """Test that payment success records amount metric."""
        self.service.log_payment_success(
            payment_id="pay_123",
            user_id=1,
            amount=Decimal("100.00"),
            currency="TRY",
        )

        # Check that amount was recorded
        volume = cache.get(f"{self.service.METRICS_KEY_PREFIX}payment_volume_TRY")
        assert volume == "100.00"

    def test_log_payment_failure(self):
        """Test logging payment failure."""
        with patch("django_iyzico.monitoring.payment_logger") as mock_logger:
            self.service.log_payment_failure(
                user_id=1,
                error_code="CARD_DECLINED",
                error_message="Insufficient funds",
                amount=Decimal("100.00"),
                currency="TRY",
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Payment failure" in call_args[0][0]

    def test_log_payment_failure_increments_metric(self):
        """Test that payment failure increments failure metric."""
        self.service.log_payment_failure(
            user_id=1,
            error_code="CARD_DECLINED",
            error_message="Insufficient funds",
        )

        failures = cache.get(f"{self.service.METRICS_KEY_PREFIX}payment_failures")
        assert failures == 1

    # -------------------------------------------------------------------------
    # Billing Logging Tests
    # -------------------------------------------------------------------------

    def test_log_billing_attempt(self):
        """Test logging billing attempt."""
        with patch("django_iyzico.monitoring.billing_logger") as mock_logger:
            self.service.log_billing_attempt(
                subscription_id=1,
                user_id=1,
                amount=Decimal("99.99"),
                currency="TRY",
                attempt_number=1,
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Billing attempt" in call_args[0][0]

    def test_log_billing_attempt_retry(self):
        """Test logging billing retry."""
        with patch("django_iyzico.monitoring.billing_logger") as mock_logger:
            self.service.log_billing_attempt(
                subscription_id=1,
                user_id=1,
                amount=Decimal("99.99"),
                currency="TRY",
                attempt_number=2,
                is_retry=True,
            )

            call_args = mock_logger.info.call_args
            assert "retry=True" in call_args[0][0]

    def test_log_double_billing_attempt(self):
        """Test logging double billing prevention."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            with patch.object(self.service, "_send_alert") as mock_alert:
                self.service.log_double_billing_attempt(
                    subscription_id=1,
                    user_id=1,
                    existing_payment_id="pay_existing",
                )

                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert "DOUBLE BILLING PREVENTED" in call_args[0][0]

                # Check alert was sent
                mock_alert.assert_called_once()
                alert_call = mock_alert.call_args
                assert alert_call[0][0] == "double_billing_attempt"
                assert alert_call[1]["severity"] == "high"

    @override_settings(IYZICO_MONITORING={"ALERT_ON_DOUBLE_BILLING": False})
    def test_log_double_billing_no_alert_when_disabled(self):
        """Test that alert is not sent when disabled."""
        service = MonitoringService()

        with patch.object(service, "_send_alert") as mock_alert:
            service.log_double_billing_attempt(
                subscription_id=1,
                user_id=1,
                existing_payment_id="pay_existing",
            )

            mock_alert.assert_not_called()

    # -------------------------------------------------------------------------
    # Security Event Logging Tests
    # -------------------------------------------------------------------------

    def test_log_webhook_received_valid(self):
        """Test logging valid webhook."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            self.service.log_webhook_received(
                event_type="payment.success",
                source_ip="1.2.3.4",
                signature_valid=True,
                payment_id="pay_123",
            )

            mock_logger.info.assert_called_once()

    def test_log_webhook_received_invalid_signature(self):
        """Test logging webhook with invalid signature."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            self.service.log_webhook_received(
                event_type="payment.success",
                source_ip="1.2.3.4",
                signature_valid=False,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "signature invalid" in call_args[0][0]

    def test_log_webhook_rejected(self):
        """Test logging rejected webhook."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            self.service.log_webhook_rejected(
                reason="IP not whitelisted",
                source_ip="5.6.7.8",
                details="IP not in allowed range",
            )

            mock_logger.warning.assert_called_once()

    def test_log_rate_limit_hit(self):
        """Test logging rate limit hit."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            self.service.log_rate_limit_hit(
                identifier="user_123",
                endpoint="/api/installments/",
                limit=100,
                window_seconds=3600,
            )

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Rate limit hit" in call_args[0][0]

    def test_log_rate_limit_hit_truncates_long_identifier(self):
        """Test that long identifiers are truncated."""
        with patch("django_iyzico.monitoring.security_logger") as mock_logger:
            long_identifier = "a" * 50
            self.service.log_rate_limit_hit(
                identifier=long_identifier,
                endpoint="/api/test/",
                limit=10,
                window_seconds=60,
            )

            call_args = mock_logger.warning.call_args
            log_data = call_args[1]["extra"]["security_data"]
            assert len(log_data["identifier"]) == 23  # 20 + "..."

    # -------------------------------------------------------------------------
    # API Error Logging Tests
    # -------------------------------------------------------------------------

    def test_log_api_error(self):
        """Test logging API error."""
        with patch("django_iyzico.monitoring.logger") as mock_logger:
            self.service.log_api_error(
                endpoint="/payment/create",
                error_code="5006",
                error_message="Card declined",
                response_time_ms=150.0,
                request_id="req_123",
            )

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Iyzico API error" in call_args[0][0]

    # -------------------------------------------------------------------------
    # Metrics Tests
    # -------------------------------------------------------------------------

    def test_increment_metric(self):
        """Test incrementing a metric."""
        self.service._increment_metric("test_metric")
        self.service._increment_metric("test_metric")
        self.service._increment_metric("test_metric", value=5)

        result = cache.get(f"{self.service.METRICS_KEY_PREFIX}test_metric")
        assert result == 7

    def test_record_amount(self):
        """Test recording amount metrics."""
        self.service._record_amount("test_volume", Decimal("100.00"), "TRY")
        self.service._record_amount("test_volume", Decimal("50.50"), "TRY")

        result = cache.get(f"{self.service.METRICS_KEY_PREFIX}test_volume_TRY")
        assert Decimal(result) == Decimal("150.50")

    def test_get_metrics(self):
        """Test getting all metrics."""
        # Set up some metrics
        self.service._increment_metric("payment_attempts", 10)
        self.service._increment_metric("payment_successes", 8)
        self.service._increment_metric("payment_failures", 2)
        self.service._record_amount("payment_volume", Decimal("1000.00"), "TRY")

        metrics = self.service.get_metrics()

        assert metrics["payment_attempts"] == 10
        assert metrics["payment_successes"] == 8
        assert metrics["payment_failures"] == 2
        assert metrics["payment_volume_TRY"] == "1000.00"

    def test_reset_metrics(self):
        """Test resetting all metrics."""
        # Set up some metrics
        self.service._increment_metric("payment_attempts", 10)
        self.service._increment_metric("payment_failures", 5)

        # Reset
        self.service.reset_metrics()

        # Check all metrics are cleared
        metrics = self.service.get_metrics()
        assert metrics["payment_attempts"] == 0
        assert metrics["payment_failures"] == 0

    # -------------------------------------------------------------------------
    # Alert Tests
    # -------------------------------------------------------------------------

    def test_check_failure_rate_alert_below_threshold(self):
        """Test that no alert is sent when below threshold."""
        # Set up metrics with low failure rate
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_attempts", 100)
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_failures", 2)

        with patch.object(self.service, "_send_alert") as mock_alert:
            self.service._check_failure_rate_alert()
            mock_alert.assert_not_called()

    def test_check_failure_rate_alert_above_threshold(self):
        """Test that alert is sent when above threshold."""
        # Set up metrics with high failure rate
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_attempts", 100)
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_failures", 20)  # 20%

        with patch.object(self.service, "_send_alert") as mock_alert:
            self.service._check_failure_rate_alert()
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[0][0] == "high_failure_rate"
            assert call_args[1]["severity"] == "high"

    def test_check_failure_rate_alert_insufficient_samples(self):
        """Test that no alert is sent with insufficient samples."""
        # Set up metrics with few attempts
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_attempts", 5)
        cache.set(f"{self.service.METRICS_KEY_PREFIX}payment_failures", 5)  # 100% but only 5 samples

        with patch.object(self.service, "_send_alert") as mock_alert:
            self.service._check_failure_rate_alert()
            mock_alert.assert_not_called()

    @override_settings(IYZICO_MONITORING={"ALERT_ON_HIGH_FAILURE_RATE": False})
    def test_check_failure_rate_alert_disabled(self):
        """Test that alert is not sent when disabled."""
        service = MonitoringService()
        cache.set(f"{service.METRICS_KEY_PREFIX}payment_attempts", 100)
        cache.set(f"{service.METRICS_KEY_PREFIX}payment_failures", 50)

        with patch.object(service, "_send_alert") as mock_alert:
            service._check_failure_rate_alert()
            mock_alert.assert_not_called()

    def test_send_alert_logs_and_signals(self):
        """Test that alerts are logged and sent via signals."""
        with patch("django_iyzico.monitoring.logger") as mock_logger:
            with patch("django_iyzico.signals.payment_alert") as mock_signal:
                self.service._send_alert(
                    alert_type="test_alert",
                    message="Test alert message",
                    severity="high",
                    data={"key": "value"},
                )

                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert "ALERT [HIGH]" in call_args[0][0]

                mock_signal.send.assert_called_once()


class TestGetMonitoringService:
    """Tests for get_monitoring_service function."""

    def test_returns_singleton(self):
        """Test that get_monitoring_service returns a singleton."""
        # Reset the global instance
        import django_iyzico.monitoring as monitoring_module

        monitoring_module._monitoring_service = None

        service1 = get_monitoring_service()
        service2 = get_monitoring_service()

        assert service1 is service2

    def test_creates_instance_on_first_call(self):
        """Test that instance is created on first call."""
        import django_iyzico.monitoring as monitoring_module

        monitoring_module._monitoring_service = None

        service = get_monitoring_service()

        assert isinstance(service, MonitoringService)


class TestMonitorTimingDecorator:
    """Tests for monitor_timing decorator."""

    def test_decorator_times_function(self):
        """Test that decorator times function execution."""

        @monitor_timing("test_operation")
        def slow_function():
            import time

            time.sleep(0.01)
            return "done"

        with patch("django_iyzico.monitoring.logger") as mock_logger:
            result = slow_function()

            assert result == "done"
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "test_operation" in call_args
            assert "ms" in call_args

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function metadata."""

        @monitor_timing("test_metric")
        def my_function():
            """My docstring."""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_decorator_handles_exceptions(self):
        """Test that decorator handles exceptions properly."""

        @monitor_timing("failing_operation")
        def failing_function():
            raise ValueError("Test error")

        with patch("django_iyzico.monitoring.logger"):
            with pytest.raises(ValueError, match="Test error"):
                failing_function()

    def test_decorator_with_arguments(self):
        """Test decorator with function arguments."""

        @monitor_timing("add_operation")
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_decorator_with_kwargs(self):
        """Test decorator with keyword arguments."""

        @monitor_timing("greet_operation")
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World!"
