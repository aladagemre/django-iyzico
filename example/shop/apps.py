"""
Django app configuration for shop.
"""

from django.apps import AppConfig


class ShopConfig(AppConfig):
    """Configuration for the shop app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"
    verbose_name = "E-commerce Shop"

    def ready(self):
        """Import signal handlers when app is ready."""
        try:
            import shop.signals  # noqa
        except ImportError:
            pass
