"""Custom exceptions for django-iyzico."""


class IyzicoError(Exception):
    """Base exception for all django-iyzico errors."""

    def __init__(self, message: str, error_code: str = None, error_group: str = None):
        """
        Initialize Iyzico error.

        Args:
            message: Error message
            error_code: Iyzico error code
            error_group: Iyzico error group
        """
        self.message = message
        self.error_code = error_code
        self.error_group = error_group
        super().__init__(self.message)

    def __str__(self):
        """Return string representation of error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class PaymentError(IyzicoError):
    """Payment processing error."""
    pass


class ValidationError(IyzicoError):
    """Validation error for payment data."""
    pass


class ConfigurationError(IyzicoError):
    """Configuration error."""
    pass


class WebhookError(IyzicoError):
    """Webhook processing error."""
    pass


class CardError(IyzicoError):
    """Card-related error."""
    pass


class ThreeDSecureError(IyzicoError):
    """3D Secure authentication error."""
    pass


# Aliases for backwards compatibility and clearer naming
IyzicoAPIException = PaymentError
"""Alias for PaymentError - used for API-level errors from Iyzico."""

IyzicoValidationException = ValidationError
"""Alias for ValidationError - used for input validation errors."""
