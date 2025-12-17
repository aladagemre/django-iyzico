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
