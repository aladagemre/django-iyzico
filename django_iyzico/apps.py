"""Django app configuration for django-iyzico."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoIyzicoConfig(AppConfig):
    """App configuration for django-iyzico."""

    name = "django_iyzico"
    verbose_name = _("Django Iyzico")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Import signals when app is ready."""
        # TODO: Import signals when implemented
        # from . import signals  # noqa
        pass
