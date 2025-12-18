"""
Django signals for django-iyzico.

Provides signals for payment lifecycle events.
"""

from django.dispatch import Signal

# Payment lifecycle signals
payment_initiated = Signal()  # providing_args=["payment", "request"]
payment_completed = Signal()  # providing_args=["payment", "response"]
payment_failed = Signal()  # providing_args=["payment", "error"]
payment_refunded = Signal()  # providing_args=["payment", "refund_response"]

# 3D Secure signals
threeds_initiated = Signal()  # providing_args=["payment", "html_content"]
threeds_completed = Signal()  # providing_args=["payment", "response"]
threeds_failed = Signal()  # providing_args=["payment", "error"]

# Webhook signals
webhook_received = Signal()  # providing_args=["event_type", "data"]

# Subscription lifecycle signals
subscription_created = Signal()  # providing_args=["subscription", "user"]
subscription_activated = Signal()  # providing_args=["subscription"]
subscription_cancelled = Signal()  # providing_args=["subscription", "immediate"]
subscription_expired = Signal()  # providing_args=["subscription"]
subscription_paused = Signal()  # providing_args=["subscription"]
subscription_resumed = Signal()  # providing_args=["subscription"]

# Subscription payment signals
subscription_payment_succeeded = Signal()  # providing_args=["subscription"]
subscription_payment_failed = Signal()  # providing_args=["subscription", "error_message"]
subscription_renewal_approaching = Signal()  # providing_args=["subscription", "days_until_renewal"]

# Monitoring and alerting signals
payment_alert = Signal()  # providing_args=["alert_type", "message", "severity", "data"]
double_billing_prevented = Signal()  # providing_args=["subscription_id", "existing_payment_id"]
high_failure_rate_detected = Signal()  # providing_args=["failure_rate", "threshold", "period"]
