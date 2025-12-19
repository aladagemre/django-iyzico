"""
django-iyzico: Django integration for Iyzico payment gateway
"""

# Expose commonly used classes and functions
# Note: Models are NOT imported here to avoid Django app registry issues
# Import them directly from django_iyzico.models when needed
from .exceptions import (
    CardError,
    ConfigurationError,
    IyzicoError,
    PaymentError,
    ThreeDSecureError,
    ValidationError,
    WebhookError,
)
from .settings import IyzicoSettings, iyzico_settings
from .signals import (  # Monitoring signals
    double_billing_prevented,
    high_failure_rate_detected,
    payment_alert,
    payment_completed,
    payment_failed,
    payment_initiated,
    payment_refunded,
    threeds_completed,
    threeds_failed,
    threeds_initiated,
    webhook_received,
)

__version__ = "0.2.1"
__author__ = "Emre Aladag"
__email__ = "your-email@example.com"

default_app_config = "django_iyzico.apps.DjangoIyzicoConfig"

# Version information
VERSION = (0, 2, 1, "final", 0)


def get_version():
    """Return the version string."""
    return __version__


# Lazy imports for Django components to avoid app registry issues


def _get_client():
    """Lazy import of IyzicoClient."""
    from .client import IyzicoClient

    return IyzicoClient


def _get_models():
    """Lazy import of models."""
    from .models import AbstractIyzicoPayment, PaymentStatus

    return AbstractIyzicoPayment, PaymentStatus


__all__ = [
    # Version
    "__version__",
    "get_version",
    "VERSION",
    # Settings
    "IyzicoSettings",
    "iyzico_settings",
    # Exceptions
    "IyzicoError",
    "PaymentError",
    "CardError",
    "ValidationError",
    "ConfigurationError",
    "ThreeDSecureError",
    "WebhookError",
    # Signals
    "payment_initiated",
    "payment_completed",
    "payment_failed",
    "payment_refunded",
    "threeds_initiated",
    "threeds_completed",
    "threeds_failed",
    "webhook_received",
    # Monitoring signals
    "payment_alert",
    "double_billing_prevented",
    "high_failure_rate_detected",
    # Lazy imports (use functions to get these)
    "_get_client",
    "_get_models",
]
