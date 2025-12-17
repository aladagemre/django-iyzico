"""Tests for django-iyzico settings."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django_iyzico.settings import IyzicoSettings, get_setting


def test_get_setting_with_default():
    """Test getting a setting with default value."""
    value = get_setting("NONEXISTENT", default="default_value")
    assert value == "default_value"


def test_get_setting_required_missing():
    """Test that required missing setting raises error."""
    with pytest.raises(ImproperlyConfigured):
        get_setting("REQUIRED_BUT_MISSING", required=True)


def test_iyzico_settings_api_key(settings):
    """Test API key setting."""
    iyzico_settings = IyzicoSettings()
    assert iyzico_settings.api_key == settings.IYZICO_API_KEY


def test_iyzico_settings_get_options():
    """Test getting options dict."""
    iyzico_settings = IyzicoSettings()
    options = iyzico_settings.get_options()

    assert "api_key" in options
    assert "secret_key" in options
    assert "base_url" in options
