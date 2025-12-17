"""Django settings configuration for django-iyzico."""

from typing import Dict, Any, List
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_setting(name: str, default: Any = None, required: bool = False) -> Any:
    """
    Get a django-iyzico setting from Django settings.

    Args:
        name: Setting name (without IYZICO_ prefix)
        default: Default value if setting not found
        required: Whether the setting is required

    Returns:
        Setting value

    Raises:
        ImproperlyConfigured: If required setting is not found
    """
    setting_name = f"IYZICO_{name}"
    value = getattr(settings, setting_name, default)

    if required and value is None:
        raise ImproperlyConfigured(
            f"{setting_name} is required. Please add it to your Django settings."
        )

    return value


class IyzicoSettings:
    """Central configuration for Iyzico settings."""

    @property
    def api_key(self) -> str:
        """Iyzico API key."""
        return get_setting("API_KEY", required=True)

    @property
    def secret_key(self) -> str:
        """Iyzico secret key."""
        return get_setting("SECRET_KEY", required=True)

    @property
    def base_url(self) -> str:
        """
        Iyzico base URL.

        Defaults to sandbox URL. Use production URL in production:
        - Sandbox: https://sandbox-api.iyzipay.com
        - Production: https://api.iyzipay.com
        """
        return get_setting("BASE_URL", default="https://sandbox-api.iyzipay.com")

    @property
    def locale(self) -> str:
        """Default locale for Iyzico requests."""
        return get_setting("LOCALE", default="tr")

    @property
    def currency(self) -> str:
        """Default currency for Iyzico payments."""
        return get_setting("CURRENCY", default="TRY")

    @property
    def store_card_data(self) -> bool:
        """
        Whether to store card data (last 4 digits, card family, etc.).

        Note: Full card numbers are NEVER stored for PCI DSS compliance.
        """
        return get_setting("STORE_CARD_DATA", default=True)

    @property
    def enable_3d_secure(self) -> bool:
        """Whether 3D Secure is enabled by default."""
        return get_setting("ENABLE_3D_SECURE", default=True)

    @property
    def callback_url(self) -> str:
        """Callback URL for 3D Secure payments."""
        return get_setting("CALLBACK_URL", default="/iyzico/callback/")

    @property
    def webhook_url(self) -> str:
        """Webhook URL for payment notifications."""
        return get_setting("WEBHOOK_URL", default="/iyzico/webhook/")

    @property
    def webhook_secret(self) -> str:
        """
        Webhook secret for signature validation.

        If set, webhook requests will be validated using HMAC-SHA256 signature.
        Leave empty to disable signature validation.
        """
        return get_setting("WEBHOOK_SECRET", default="")

    @property
    def webhook_allowed_ips(self) -> List[str]:
        """
        List of allowed IP addresses for webhook requests.

        If set, only requests from these IPs will be accepted.
        Leave empty to allow all IPs.

        Example:
            IYZICO_WEBHOOK_ALLOWED_IPS = [
                "185.201.20.0/24",  # Iyzico webhook IPs
                "127.0.0.1",        # Localhost for testing
            ]
        """
        return get_setting("WEBHOOK_ALLOWED_IPS", default=[])

    def get_options(self) -> Dict[str, str]:
        """
        Get Iyzico API options dict.

        Returns:
            Dict with api_key, secret_key, and base_url
        """
        return {
            "api_key": self.api_key,
            "secret_key": self.secret_key,
            "base_url": self.base_url,
        }


# Global settings instance
iyzico_settings = IyzicoSettings()
