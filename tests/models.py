"""
Test models for django-iyzico tests.

Provides concrete implementations of abstract models for testing.
"""

from django.db import models
from django_iyzico.models import AbstractIyzicoPayment


class TestPayment(AbstractIyzicoPayment):
    """
    Concrete payment model for testing.

    This extends AbstractIyzicoPayment to create a real database table
    that can be used in tests.
    """

    # No additional fields needed for basic testing
    # AbstractIyzicoPayment provides all payment fields

    class Meta(AbstractIyzicoPayment.Meta):
        db_table = "test_payments"
        app_label = "tests"
