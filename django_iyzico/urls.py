"""
URL configuration for django-iyzico.

Include these URLs in your project's urls.py:

    from django.urls import path, include

    urlpatterns = [
        # ... your other URL patterns
        path('iyzico/', include('django_iyzico.urls')),
    ]

This will create the following endpoints:
    - /iyzico/callback/ - 3D Secure callback (called by Iyzico)
    - /iyzico/webhook/ - Webhook handler (called by Iyzico)
    - /iyzico/webhook/test/ - Test webhook (development only, DEBUG mode)
"""

from django.conf import settings
from django.urls import path

from . import views

app_name = "django_iyzico"

urlpatterns = [
    # 3D Secure callback endpoint
    # Called by Iyzico after user completes 3DS authentication
    path(
        "callback/",
        views.threeds_callback_view,
        name="threeds_callback",
    ),
    # Webhook endpoint
    # Called by Iyzico for various payment events
    path(
        "webhook/",
        views.webhook_view,
        name="webhook",
    ),
]

# SECURITY: Only include test webhook endpoint in DEBUG mode
# This prevents the test endpoint from being exposed in production
if getattr(settings, "DEBUG", False):
    urlpatterns.append(
        path(
            "webhook/test/",
            views.test_webhook_view,
            name="test_webhook",
        ),
    )
