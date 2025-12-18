"""Django settings for testing django-iyzico."""

import os
import sys

# Fail if this settings file is used outside of testing
if 'pytest' not in sys.modules and 'TESTING' not in os.environ and 'test' not in sys.argv:
    raise RuntimeError(
        "Test settings should not be used outside of test environment. "
        "Set TESTING=1 environment variable or use pytest."
    )

SECRET_KEY = "test-secret-key-for-django-iyzico"

DEBUG = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django_iyzico",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Iyzico test settings
IYZICO_API_KEY = "test-api-key"
IYZICO_SECRET_KEY = "test-secret-key"
IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
IYZICO_LOCALE = "tr"
IYZICO_CURRENCY = "TRY"

USE_TZ = True
TIME_ZONE = "Europe/Istanbul"

ROOT_URLCONF = "tests.urls"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
