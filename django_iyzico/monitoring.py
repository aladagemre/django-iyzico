"""
Monitoring and logging utilities for django-iyzico.

Provides structured logging, metrics collection, and monitoring hooks
for payment processing, subscription billing, and error tracking.

Usage:
    Configure monitoring by adding handlers in your Django settings:

    IYZICO_MONITORING = {
        'METRICS_BACKEND': 'statsd',  # or 'prometheus', 'datadog'
        'LOG_PAYMENTS': True,
        'LOG_SENSITIVE_ERRORS': False,
        'ALERT_ON_DOUBLE_BILLING': True,
        'ALERT_ON_HIGH_FAILURE_RATE': True,
        'FAILURE_RATE_THRESHOLD': 0.05,  # 5%
    }
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Structured logger for payment events
payment_logger = logging.getLogger("django_iyzico.payments")
billing_logger = logging.getLogger("django_iyzico.billing")
security_logger = logging.getLogger("django_iyzico.security")


@dataclass
class PaymentMetrics:
    """Container for payment metrics."""

    total_attempts: int = 0
    successful: int = 0
    failed: int = 0
    total_amount: Decimal = field(default_factory=lambda: Decimal("0.00"))
    average_duration_ms: float = 0.0
    last_failure_reason: Optional[str] = None
    period_start: datetime = field(default_factory=timezone.now)


class MonitoringService:
    """
    Central monitoring service for django-iyzico.

    Provides:
    - Structured event logging
    - Metrics collection
    - Alert triggering
    - Rate tracking

    Example:
        >>> monitor = MonitoringService()
        >>> monitor.log_payment_attempt(user_id=1, amount=100.00, currency='TRY')
        >>> monitor.log_payment_success(payment_id='xyz123', duration_ms=250)
        >>> monitor.log_payment_failure(error_code='CARD_DECLINED', message='Insufficient funds')
    """

    # Cache keys for metrics
    METRICS_KEY_PREFIX = "iyzico_metrics_"
    FAILURE_RATE_KEY = "iyzico_failure_rate"
    DOUBLE_BILLING_KEY = "iyzico_double_billing_attempts"

    def __init__(self):
        """Initialize monitoring service."""
        self.config = getattr(settings, "IYZICO_MONITORING", {})
        self.metrics_backend = self.config.get("METRICS_BACKEND", None)
        self.log_payments = self.config.get("LOG_PAYMENTS", True)
        self.alert_on_double_billing = self.config.get("ALERT_ON_DOUBLE_BILLING", True)
        self.alert_on_high_failure_rate = self.config.get("ALERT_ON_HIGH_FAILURE_RATE", True)
        self.failure_rate_threshold = self.config.get("FAILURE_RATE_THRESHOLD", 0.05)

    # -------------------------------------------------------------------------
    # Payment Event Logging
    # -------------------------------------------------------------------------

    def log_payment_attempt(
        self,
        user_id: Any,
        amount: Decimal,
        currency: str,
        payment_type: str = "one_time",
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log a payment attempt.

        Args:
            user_id: User initiating the payment.
            amount: Payment amount.
            currency: Currency code.
            payment_type: Type of payment (one_time, subscription, etc.).
            metadata: Additional context data.
        """
        if not self.log_payments:
            return

        log_data = {
            "event": "payment_attempt",
            "user_id": str(user_id),
            "amount": str(amount),
            "currency": currency,
            "payment_type": payment_type,
            "timestamp": timezone.now().isoformat(),
        }

        if metadata:
            log_data["metadata"] = metadata

        payment_logger.info(
            f"Payment attempt: user={user_id}, amount={amount} {currency}",
            extra={"payment_data": log_data},
        )

        self._increment_metric("payment_attempts")

    def log_payment_success(
        self,
        payment_id: str,
        user_id: Any,
        amount: Decimal,
        currency: str,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log a successful payment.

        Args:
            payment_id: Iyzico payment ID.
            user_id: User who made the payment.
            amount: Payment amount.
            currency: Currency code.
            duration_ms: Processing duration in milliseconds.
            metadata: Additional context data.
        """
        if not self.log_payments:
            return

        log_data = {
            "event": "payment_success",
            "payment_id": payment_id,
            "user_id": str(user_id),
            "amount": str(amount),
            "currency": currency,
            "duration_ms": duration_ms,
            "timestamp": timezone.now().isoformat(),
        }

        if metadata:
            log_data["metadata"] = metadata

        payment_logger.info(
            f"Payment success: payment_id={payment_id}, amount={amount} {currency}",
            extra={"payment_data": log_data},
        )

        self._increment_metric("payment_successes")
        self._record_amount("payment_volume", amount, currency)

    def log_payment_failure(
        self,
        user_id: Any,
        error_code: Optional[str],
        error_message: str,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        is_recoverable: bool = True,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Log a payment failure.

        Args:
            user_id: User whose payment failed.
            error_code: Error code from Iyzico.
            error_message: Human-readable error message.
            amount: Payment amount (if available).
            currency: Currency code (if available).
            is_recoverable: Whether the error might be retryable.
            metadata: Additional context data.
        """
        log_data = {
            "event": "payment_failure",
            "user_id": str(user_id),
            "error_code": error_code,
            "error_message": error_message,
            "amount": str(amount) if amount else None,
            "currency": currency,
            "is_recoverable": is_recoverable,
            "timestamp": timezone.now().isoformat(),
        }

        if metadata:
            log_data["metadata"] = metadata

        payment_logger.warning(
            f"Payment failure: user={user_id}, error={error_code}: {error_message}",
            extra={"payment_data": log_data},
        )

        self._increment_metric("payment_failures")
        self._check_failure_rate_alert()

    # -------------------------------------------------------------------------
    # Subscription Billing Logging
    # -------------------------------------------------------------------------

    def log_billing_attempt(
        self,
        subscription_id: int,
        user_id: Any,
        amount: Decimal,
        currency: str,
        attempt_number: int = 1,
        is_retry: bool = False,
    ) -> None:
        """Log a subscription billing attempt."""
        log_data = {
            "event": "billing_attempt",
            "subscription_id": subscription_id,
            "user_id": str(user_id),
            "amount": str(amount),
            "currency": currency,
            "attempt_number": attempt_number,
            "is_retry": is_retry,
            "timestamp": timezone.now().isoformat(),
        }

        billing_logger.info(
            f"Billing attempt: subscription={subscription_id}, "
            f"attempt={attempt_number}, retry={is_retry}",
            extra={"billing_data": log_data},
        )

        self._increment_metric("billing_attempts")

    def log_double_billing_attempt(
        self,
        subscription_id: int,
        user_id: Any,
        existing_payment_id: str,
    ) -> None:
        """
        Log a prevented double billing attempt.

        This is a critical security event that should trigger alerts.
        """
        log_data = {
            "event": "double_billing_prevented",
            "subscription_id": subscription_id,
            "user_id": str(user_id),
            "existing_payment_id": existing_payment_id,
            "timestamp": timezone.now().isoformat(),
            "severity": "HIGH",
        }

        security_logger.warning(
            f"DOUBLE BILLING PREVENTED: subscription={subscription_id}, "
            f"existing_payment={existing_payment_id}",
            extra={"security_data": log_data},
        )

        self._increment_metric("double_billing_prevented")

        if self.alert_on_double_billing:
            self._send_alert(
                "double_billing_attempt",
                f"Double billing attempt prevented for subscription {subscription_id}",
                severity="high",
                data=log_data,
            )

    # -------------------------------------------------------------------------
    # Security Event Logging
    # -------------------------------------------------------------------------

    def log_webhook_received(
        self,
        event_type: str,
        source_ip: str,
        signature_valid: bool,
        payment_id: Optional[str] = None,
    ) -> None:
        """Log webhook receipt."""
        log_data = {
            "event": "webhook_received",
            "event_type": event_type,
            "source_ip": source_ip,
            "signature_valid": signature_valid,
            "payment_id": payment_id,
            "timestamp": timezone.now().isoformat(),
        }

        if signature_valid:
            security_logger.info(
                f"Webhook received: type={event_type}, ip={source_ip}",
                extra={"webhook_data": log_data},
            )
        else:
            security_logger.warning(
                f"Webhook signature invalid: type={event_type}, ip={source_ip}",
                extra={"webhook_data": log_data},
            )

    def log_webhook_rejected(
        self,
        reason: str,
        source_ip: str,
        details: Optional[str] = None,
    ) -> None:
        """Log rejected webhook."""
        log_data = {
            "event": "webhook_rejected",
            "reason": reason,
            "source_ip": source_ip,
            "details": details,
            "timestamp": timezone.now().isoformat(),
        }

        security_logger.warning(
            f"Webhook rejected: reason={reason}, ip={source_ip}", extra={"security_data": log_data}
        )

        self._increment_metric("webhooks_rejected")

    def log_rate_limit_hit(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """Log rate limit being hit."""
        log_data = {
            "event": "rate_limit_hit",
            "identifier": identifier[:20] + "..." if len(identifier) > 20 else identifier,
            "endpoint": endpoint,
            "limit": limit,
            "window_seconds": window_seconds,
            "timestamp": timezone.now().isoformat(),
        }

        security_logger.warning(
            f"Rate limit hit: endpoint={endpoint}, limit={limit}/{window_seconds}s",
            extra={"security_data": log_data},
        )

        self._increment_metric("rate_limits_hit")

    # -------------------------------------------------------------------------
    # API Error Logging
    # -------------------------------------------------------------------------

    def log_api_error(
        self,
        endpoint: str,
        error_code: Optional[str],
        error_message: str,
        response_time_ms: Optional[float] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Log Iyzico API error."""
        log_data = {
            "event": "api_error",
            "endpoint": endpoint,
            "error_code": error_code,
            "error_message": error_message,
            "response_time_ms": response_time_ms,
            "request_id": request_id,
            "timestamp": timezone.now().isoformat(),
        }

        logger.error(
            f"Iyzico API error: endpoint={endpoint}, error={error_code}",
            extra={"api_data": log_data},
        )

        self._increment_metric("api_errors")

    # -------------------------------------------------------------------------
    # Metrics Helpers
    # -------------------------------------------------------------------------

    def _increment_metric(self, metric_name: str, value: int = 1) -> None:
        """Increment a metric counter."""
        cache_key = f"{self.METRICS_KEY_PREFIX}{metric_name}"
        try:
            current = cache.get(cache_key, 0)
            cache.set(cache_key, current + value, timeout=86400)  # 24 hours
        except Exception as e:
            logger.debug(f"Failed to increment metric {metric_name}: {e}")

    def _record_amount(
        self,
        metric_name: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        """Record an amount metric."""
        cache_key = f"{self.METRICS_KEY_PREFIX}{metric_name}_{currency}"
        try:
            current = Decimal(str(cache.get(cache_key, "0.00")))
            cache.set(cache_key, str(current + amount), timeout=86400)
        except Exception as e:
            logger.debug(f"Failed to record amount {metric_name}: {e}")

    def _check_failure_rate_alert(self) -> None:
        """Check if failure rate exceeds threshold and send alert."""
        if not self.alert_on_high_failure_rate:
            return

        try:
            attempts = cache.get(f"{self.METRICS_KEY_PREFIX}payment_attempts", 0)
            failures = cache.get(f"{self.METRICS_KEY_PREFIX}payment_failures", 0)

            if attempts > 10:  # Minimum sample size
                failure_rate = failures / attempts
                if failure_rate > self.failure_rate_threshold:
                    self._send_alert(
                        "high_failure_rate",
                        f"Payment failure rate ({failure_rate:.1%}) exceeds threshold "
                        f"({self.failure_rate_threshold:.1%})",
                        severity="high",
                        data={
                            "attempts": attempts,
                            "failures": failures,
                            "failure_rate": failure_rate,
                        },
                    )
        except Exception as e:
            logger.debug(f"Failed to check failure rate: {e}")

    def _send_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "medium",
        data: Optional[Dict] = None,
    ) -> None:
        """
        Send an alert through configured channels.

        Override this method to integrate with your alerting system
        (PagerDuty, Slack, email, etc.).
        """
        alert_data = {
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "data": data,
            "timestamp": timezone.now().isoformat(),
        }

        # Log the alert
        logger.warning(
            f"ALERT [{severity.upper()}]: {alert_type} - {message}",
            extra={"alert_data": alert_data},
        )

        # Send to Django signals for custom handling
        try:
            from .signals import payment_alert

            payment_alert.send(
                sender=self.__class__,
                alert_type=alert_type,
                message=message,
                severity=severity,
                data=data,
            )
        except ImportError:
            pass

    # -------------------------------------------------------------------------
    # Metrics Retrieval
    # -------------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dictionary with all current metrics.
        """
        return {
            "payment_attempts": cache.get(f"{self.METRICS_KEY_PREFIX}payment_attempts", 0),
            "payment_successes": cache.get(f"{self.METRICS_KEY_PREFIX}payment_successes", 0),
            "payment_failures": cache.get(f"{self.METRICS_KEY_PREFIX}payment_failures", 0),
            "billing_attempts": cache.get(f"{self.METRICS_KEY_PREFIX}billing_attempts", 0),
            "double_billing_prevented": cache.get(
                f"{self.METRICS_KEY_PREFIX}double_billing_prevented", 0
            ),
            "api_errors": cache.get(f"{self.METRICS_KEY_PREFIX}api_errors", 0),
            "webhooks_rejected": cache.get(f"{self.METRICS_KEY_PREFIX}webhooks_rejected", 0),
            "rate_limits_hit": cache.get(f"{self.METRICS_KEY_PREFIX}rate_limits_hit", 0),
            "payment_volume_TRY": cache.get(f"{self.METRICS_KEY_PREFIX}payment_volume_TRY", "0.00"),
            "payment_volume_USD": cache.get(f"{self.METRICS_KEY_PREFIX}payment_volume_USD", "0.00"),
            "payment_volume_EUR": cache.get(f"{self.METRICS_KEY_PREFIX}payment_volume_EUR", "0.00"),
        }

    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        metric_keys = [
            "payment_attempts",
            "payment_successes",
            "payment_failures",
            "billing_attempts",
            "double_billing_prevented",
            "api_errors",
            "webhooks_rejected",
            "rate_limits_hit",
            "payment_volume_TRY",
            "payment_volume_USD",
            "payment_volume_EUR",
        ]
        for key in metric_keys:
            cache.delete(f"{self.METRICS_KEY_PREFIX}{key}")


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """
    Get the global monitoring service instance.

    Returns:
        MonitoringService singleton instance.
    """
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service


# Decorator for timing function execution
def monitor_timing(metric_name: str):
    """
    Decorator to monitor function execution time.

    Args:
        metric_name: Name of the metric to record.

    Example:
        >>> @monitor_timing('payment_processing')
        >>> def process_payment(data):
        ...     # Processing logic
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"{metric_name} completed in {duration_ms:.2f}ms")

        return wrapper

    return decorator
