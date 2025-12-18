"""Pytest configuration and fixtures for django-iyzico tests."""

import pytest
from django.conf import settings


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Create database tables for test models.

    Since django-iyzico uses abstract models, we need to create tables
    for the concrete test models programmatically using schema editor.
    """
    from django.db import connection

    from tests.models import TestPayment

    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            # Create table for TestPayment model
            schema_editor.create_model(TestPayment)

    yield

    # Cleanup - drop the table
    with django_db_blocker.unblock():
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(TestPayment)


@pytest.fixture
def payment_model():
    """Fixture providing the payment model class."""
    from tests.models import TestPayment

    return TestPayment


@pytest.fixture
def iyzico_settings():
    """Fixture providing Iyzico settings."""
    return {
        "api_key": settings.IYZICO_API_KEY,
        "secret_key": settings.IYZICO_SECRET_KEY,
        "base_url": settings.IYZICO_BASE_URL,
    }


@pytest.fixture
def sample_payment_data():
    """Fixture providing sample payment data."""
    return {
        "price": "100.00",
        "paidPrice": "100.00",
        "currency": "TRY",
        "basketId": "B12345",
        "paymentCard": {
            "cardHolderName": "Test User",
            "cardNumber": "5528790000000008",  # Iyzico test card
            "expireMonth": "12",
            "expireYear": "2030",
            "cvc": "123",
        },
        "buyer": {
            "id": "BY123",
            "name": "Test",
            "surname": "User",
            "email": "test@example.com",
            "identityNumber": "11111111111",
            "registrationAddress": "Test Address",
            "city": "Istanbul",
            "country": "Turkey",
            "zipCode": "34000",
        },
    }


@pytest.fixture
def sample_iyzico_response():
    """Fixture providing sample Iyzico API response."""
    return {
        "status": "success",
        "paymentId": "test-payment-123",
        "conversationId": "test-conv-123",
        "price": "100.00",
        "paidPrice": "100.00",
        "currency": "TRY",
        "installment": 1,
        "cardType": "CREDIT_CARD",
        "cardAssociation": "MASTER_CARD",
        "cardFamily": "Bonus",
        "cardBankName": "Test Bank",
        "cardBankCode": "1234",
        "buyerEmail": "test@example.com",
        "buyerName": "Test",
        "buyerSurname": "User",
    }


@pytest.fixture
def sample_failed_response():
    """Fixture providing sample failed Iyzico response."""
    return {
        "status": "failure",
        "errorCode": "5006",
        "errorMessage": "Transaction declined",
        "errorGroup": "CARD_ERROR",
    }


@pytest.fixture
def sample_3ds_response():
    """Fixture providing sample 3DS initialization response."""
    return {
        "status": "success",
        "threeDSHtmlContent": "<html><body>3DS Authentication</body></html>",
        "token": "payment-token-123",
        "conversationId": "test-conv-123",
    }


@pytest.fixture(autouse=True)
def reset_signal_receivers():
    """
    Reset signal receivers before each test.

    This ensures that signal receivers from one test don't affect others.
    """
    from django_iyzico import signals

    # Store original receivers
    original_receivers = {}
    signal_list = [
        signals.payment_initiated,
        signals.payment_completed,
        signals.payment_failed,
        signals.payment_refunded,
        signals.threeds_initiated,
        signals.threeds_completed,
        signals.threeds_failed,
        signals.webhook_received,
    ]

    for signal in signal_list:
        original_receivers[signal] = list(signal.receivers)

    yield

    # Restore original receivers
    for signal in signal_list:
        signal.receivers = original_receivers[signal]
