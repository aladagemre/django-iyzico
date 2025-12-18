# django-iyzico

> **Django integration for Iyzico payment gateway** - Turkey's leading payment solution

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-3.2%2B-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-662%2B%20passing-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](#testing)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)

> **Note:** This is an unofficial, community-maintained package and is not endorsed by or affiliated with Iyzico. For the official Iyzico Python SDK, please visit [iyzipay-python](https://github.com/iyzico/iyzipay-python).

**django-iyzico** provides a complete Django-native integration for the Iyzico payment gateway, designed specifically for the Turkish market. Reduce integration time from days to hours with a secure, well-tested, production-ready solution.

## 🌟 Features

### Core Features
- ✅ **Payment Processing** - Direct payments and 3D Secure support
- ✅ **Subscription Payments** - Recurring billing with automated lifecycle management
- ✅ **Installment Payments** - Full installment support with BIN-based options
- ✅ **Multi-Currency** - Support for TRY, USD, EUR, GBP with conversion
- ✅ **PCI DSS Compliant** - Secure card data handling (never stores full card numbers)
- ✅ **Refund Processing** - Full and partial refunds
- ✅ **Django Admin** - Professional interface with color-coded statuses
- ✅ **Webhook Handling** - Real-time payment status updates
- ✅ **Signal System** - Event-driven architecture (20 signals)
- ✅ **Celery Integration** - Automated subscription billing and task processing
- ✅ **Management Commands** - Sync and cleanup utilities
- ✅ **Type Hints** - Full type coverage for IDE support
- ✅ **Well Tested** - 662+ tests, 95%+ coverage across all modules
- ✅ **Monitoring** - Structured logging, metrics, and alerting

### Optional Features
- 🔌 **Django REST Framework** - Optional API support
- 🔧 **Advanced Utilities** - Currency conversion, installment calculation, basket ID generator

## 📦 Installation

```bash
pip install django-iyzico
```

### Requirements
- Python 3.11+
- Django 4.2+ (supports 4.2 LTS, 5.2, 6.0)
- iyzipay >= 1.0.45

## 🚀 Quick Start

### 1. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_iyzico',
]
```

### 2. Configure Settings

```python
# settings.py

# Required settings
IYZICO_API_KEY = 'your-api-key'
IYZICO_SECRET_KEY = 'your-secret-key'
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'  # Sandbox
# IYZICO_BASE_URL = 'https://api.iyzipay.com'  # Production

# Optional settings (with defaults)
IYZICO_LOCALE = 'tr'  # Default locale
IYZICO_CURRENCY = 'TRY'  # Default currency

# Optional webhook security
IYZICO_WEBHOOK_SECRET = 'your-webhook-secret'  # For signature validation
IYZICO_WEBHOOK_ALLOWED_IPS = ['1.2.3.4', '5.6.7.0/24']  # IP whitelist with CIDR
```

### 3. Create Your Payment Model

```python
# models.py
from django.db import models
from django_iyzico.models import AbstractIyzicoPayment

class Order(AbstractIyzicoPayment):
    """Your order model extending Iyzico payment."""

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    product = models.CharField(max_length=200)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Include URLs

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    path('payments/', include('django_iyzico.urls')),
    ...
]
```

### 6. Process a Payment

```python
# views.py
from decimal import Decimal
from django_iyzico.client import IyzicoClient
from .models import Order

def checkout(request):
    # Create order
    order = Order.objects.create(
        user=request.user,
        product="Premium Subscription",
        amount=Decimal("99.00"),
        conversation_id="ORDER-12345"
    )

    # Process payment
    client = IyzicoClient()

    payment_data = {
        'price': '99.00',
        'paidPrice': '99.00',
        'currency': 'TRY',
        'basketId': 'BASKET-12345',
        'paymentCard': {
            'cardHolderName': request.POST['card_holder'],
            'cardNumber': request.POST['card_number'],
            'expireMonth': request.POST['expire_month'],
            'expireYear': request.POST['expire_year'],
            'cvc': request.POST['cvc'],
        },
        'buyer': {
            'id': str(request.user.id),
            'name': request.user.first_name,
            'surname': request.user.last_name,
            'email': request.user.email,
            'identityNumber': '11111111111',
            'registrationAddress': 'Address here',
            'city': 'Istanbul',
            'country': 'Turkey',
            'zipCode': '34000',
        },
    }

    try:
        response = client.create_payment(payment_data)

        if response.is_successful():
            # Update order
            order.update_from_response(response)
            return redirect('order_success', order_id=order.id)
        else:
            messages.error(request, response.error_message)
            return redirect('checkout')

    except PaymentError as e:
        messages.error(request, "Payment failed. Please try again.")
        return redirect('checkout')
```

### 7. Process Subscription Payments (v0.2.0+)

```python
from django_iyzico.subscription_models import SubscriptionPlan, Subscription
from django_iyzico.subscription_manager import SubscriptionManager

# Create a subscription plan
plan = SubscriptionPlan.objects.create(
    name="Premium Monthly",
    price=Decimal("99.00"),
    currency="TRY",
    billing_interval="MONTHLY",
    billing_period=1,
    trial_days=7
)

# Subscribe a user
manager = SubscriptionManager()
subscription = manager.create_subscription(
    plan=plan,
    user=request.user,
    payment_method={
        'cardHolderName': 'John Doe',
        'cardNumber': '5528790000000008',
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
    }
)

# Subscription automatically bills every month
# See docs/SUBSCRIPTION_GUIDE.md for complete guide
```

### 8. Use Installment Payments (v0.2.0+)

```python
from django_iyzico.installment_client import InstallmentClient

# Get installment options for a card
client = InstallmentClient()
options = client.get_installment_info(
    bin_number='552879',  # First 6 digits of card
    price=Decimal('1000.00')
)

# Display installment options to user
for option in options:
    print(f"{option.installment_count} installments: {option.installment_price}/month")
    print(f"Total: {option.total_price} (Rate: {option.installment_rate}%)")

# Process payment with installments
payment_data['installment'] = 3  # 3 installments
response = client.create_payment(payment_data)

# See docs/INSTALLMENT_GUIDE.md for complete guide
```

### 9. Multi-Currency Support (v0.2.0+)

```python
from django_iyzico.currency import format_amount, CurrencyConverter

# Create payment in any supported currency
order = Order.objects.create(
    amount=Decimal("100.00"),
    currency='USD'  # TRY, USD, EUR, or GBP
)

# Format amount with currency symbol
formatted = order.get_formatted_amount()  # "$100.00"

# Convert between currencies
converter = CurrencyConverter()
try_amount = order.convert_to_currency('TRY')
print(f"${order.amount} USD = ₺{try_amount} TRY")

# See docs/CURRENCY_GUIDE.md for complete guide
```

## 🎨 Django Admin Integration

```python
# admin.py
from django.contrib import admin
from django_iyzico.admin import IyzicoPaymentAdminMixin
from .models import Order

@admin.register(Order)
class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
    list_display = IyzicoPaymentAdminMixin.list_display + ['user', 'product']

    # All payment admin features included:
    # - Color-coded status badges
    # - Advanced filtering
    # - Bulk refund action
    # - CSV export
    # - Delete protection
```

## 📡 Signal Handling

django-iyzico provides 20 signals for payment, subscription, and monitoring events:

### Payment Signals (8 signals)

```python
# signals.py
from django.dispatch import receiver
from django_iyzico.signals import (
    payment_completed, payment_failed, payment_refunded,
    threeds_completed, webhook_received
)

@receiver(payment_completed)
def on_payment_success(sender, instance, **kwargs):
    """Handle successful payment."""
    # Update user subscription
    instance.user.activate_premium()

    # Send confirmation email
    send_email(instance.buyer_email, "Payment Confirmed")

    # Log for analytics
    track_event('payment_success', amount=instance.amount)

@receiver(payment_failed)
def on_payment_failed(sender, instance, **kwargs):
    """Handle failed payment."""
    # Log failure
    logger.error(f"Payment failed: {instance.error_message}")

    # Notify user
    send_email(instance.buyer_email, "Payment Failed")
```

### Subscription Signals (9 signals - v0.2.0+)

```python
from django_iyzico.subscription_signals import (
    subscription_created, subscription_activated,
    subscription_cancelled, subscription_payment_succeeded,
    subscription_payment_failed
)

@receiver(subscription_activated)
def on_subscription_activated(sender, subscription, **kwargs):
    """Handle subscription activation."""
    # Grant access to premium features
    subscription.user.grant_premium_access()

    # Send welcome email
    send_email(subscription.user.email, "Welcome to Premium!")

@receiver(subscription_payment_failed)
def on_subscription_payment_failed(sender, subscription, payment, **kwargs):
    """Handle failed subscription payment."""
    # Notify user
    send_email(subscription.user.email, "Payment Failed - Please Update Card")

    # Log for retry
    logger.warning(f"Subscription {subscription.id} payment failed")
```

### Monitoring Signals (3 signals - v0.2.0+)

```python
from django_iyzico.signals import (
    payment_alert, double_billing_prevented, high_failure_rate_detected
)

@receiver(payment_alert)
def on_payment_alert(sender, alert_type, message, severity, **kwargs):
    """Handle payment system alerts."""
    if severity == 'critical':
        notify_ops_team(alert_type, message)

@receiver(double_billing_prevented)
def on_double_billing_prevented(sender, subscription_id, **kwargs):
    """Log prevented double billing attempts."""
    logger.info(f"Double billing prevented for subscription {subscription_id}")

@receiver(high_failure_rate_detected)
def on_high_failure_rate(sender, failure_rate, threshold, **kwargs):
    """Alert on high payment failure rates."""
    alert_ops(f"Payment failure rate {failure_rate:.1%} exceeds threshold {threshold:.1%}")
```

## 🔄 Webhook Handling

Webhooks are automatically handled at `/payments/webhook/`. Configure your Iyzico merchant panel to send webhooks to:

```
https://yourdomain.com/payments/webhook/
```

For enhanced security, configure webhook validation:

```python
# settings.py
IYZICO_WEBHOOK_SECRET = 'your-webhook-secret'  # HMAC signature validation
IYZICO_WEBHOOK_ALLOWED_IPS = ['1.2.3.4']  # IP whitelist
```

## 💰 Refund Processing

```python
# Process a refund
from .models import Order

order = Order.objects.get(id=order_id)

# Full refund
response = order.process_refund()

# Partial refund
response = order.process_refund(
    amount=Decimal("50.00"),
    reason="Customer request"
)

if response.is_successful():
    # Refund processed
    # Status automatically updated
    # Signal automatically triggered
    pass
```

## 🛠️ Management Commands

### Sync Payment Statuses

```bash
# Sync payments from last 7 days
python manage.py sync_iyzico_payments --model myapp.models.Order --days 7

# Dry run (see what would be updated)
python manage.py sync_iyzico_payments --model myapp.models.Order --dry-run

# Filter by status
python manage.py sync_iyzico_payments --model myapp.models.Order --status pending
```

### Clean Up Old Payments

```bash
# Delete payments older than 365 days
python manage.py cleanup_old_payments --model myapp.models.Order --days 365

# Keep successful payments longer
python manage.py cleanup_old_payments \
    --model myapp.models.Order \
    --days 365 \
    --keep-successful 730

# Export before deleting
python manage.py cleanup_old_payments \
    --model myapp.models.Order \
    --export /backup/payments.csv \
    --days 365
```

## 🔌 Django REST Framework (Optional)

If you have DRF installed, you can use the optional API support:

```python
# urls.py
from rest_framework.routers import DefaultRouter
from django_iyzico.viewsets import IyzicoPaymentViewSet
from .models import Order

router = DefaultRouter()

# Configure viewset with your model
class OrderPaymentViewSet(IyzicoPaymentViewSet):
    queryset = Order.objects.all()

router.register('payments', OrderPaymentViewSet, basename='payment')

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**API Endpoints:**
- `GET /api/payments/` - List all payments
- `GET /api/payments/{id}/` - Retrieve payment details
- `GET /api/payments/successful/` - List successful payments
- `GET /api/payments/failed/` - List failed payments
- `GET /api/payments/stats/` - Payment statistics

## 🔒 Security

### PCI DSS Compliance

django-iyzico is designed to be PCI DSS Level 1 compliant:

- ✅ **Never stores full card numbers** - Only last 4 digits
- ✅ **Never stores CVC/CVV codes**
- ✅ **Automatic log sanitization** - No sensitive data in logs
- ✅ **Secure card data masking**
- ✅ **Input validation** on all endpoints

### Webhook Security

- ✅ **HMAC-SHA256 signature validation**
- ✅ **IP whitelisting with CIDR support**
- ✅ **Constant-time comparison** (timing attack prevention)
- ✅ **X-Forwarded-For header support**

### Best Practices

See [SECURITY.md](SECURITY.md) for complete security guidelines.

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=django_iyzico --cov-report=html

# Specific test file
pytest tests/test_client.py -v
```

**Test Statistics:**
- **662+ test methods** across 22 test files
- **95%+ coverage** across all modules
- **~12,000 lines** of test code
- **Comprehensive test suites** for payments, subscriptions, installments, currency, and monitoring
- **83+ security-critical tests**

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. Payment Fails with "INVALID_SIGNATURE" Error

**Problem:** Payment requests return an error about invalid signature.

**Solution:**
```python
# Verify your API credentials are correct
# settings.py
IYZICO_API_KEY = 'your-correct-api-key'
IYZICO_SECRET_KEY = 'your-correct-secret-key'
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'  # For testing

# Check that credentials match your Iyzico merchant panel
# Production credentials differ from sandbox credentials
```

#### 2. Webhook Not Receiving Updates

**Problem:** Payments succeed but webhooks don't trigger.

**Solution:**
```python
# 1. Ensure webhook URL is publicly accessible
IYZICO_WEBHOOK_SECRET = 'your-webhook-secret'

# 2. Configure webhook URL in Iyzico merchant panel:
# https://yourdomain.com/payments/webhook/

# 3. Check webhook logs
import logging
logger = logging.getLogger('django_iyzico')
logger.setLevel(logging.DEBUG)

# 4. Verify IP whitelist (if configured)
IYZICO_WEBHOOK_ALLOWED_IPS = []  # Allow all IPs for testing

# 5. Test webhook locally with ngrok:
# ngrok http 8000
# Use ngrok URL in Iyzico panel
```

#### 3. "Payment ID already exists" Error

**Problem:** Duplicate payment_id constraint violation.

**Solution:**
```python
# Use unique conversation_id for each payment attempt
import uuid

order = Order.objects.create(
    conversation_id=f"ORDER-{uuid.uuid4()}",  # Always unique
    amount=Decimal("99.00")
)

# Or use the utility function
from django_iyzico.utils import generate_basket_id
basket_id = generate_basket_id()  # Returns UUID-based ID
```

#### 4. Card Data Not Saving

**Problem:** card_last_four_digits is always None.

**Solution:**
```python
# Store card data before sending to Iyzico
payment_data = {
    'paymentCard': {
        'cardNumber': '5528790000000008',
        # ... other fields
    }
}

# Extract and store card info
order.mask_and_store_card_data(payment_data)

# Then process payment
response = client.create_payment(...)
```

#### 5. 3D Secure Callback Fails

**Problem:** 3DS callback returns 404 or doesn't update payment.

**Solution:**
```python
# 1. Verify URLs are included in your project
# urls.py
urlpatterns = [
    path('payments/', include('django_iyzico.urls')),  # Required
]

# 2. Check callback URL configuration
IYZICO_CALLBACK_URL = 'https://yourdomain.com/payments/callback/'

# 3. Ensure callback URL is accessible (not behind auth)
# The view has @csrf_exempt decorator by default

# 4. Check payment token in callback
# Token should be in GET parameters: ?token=xxx
```

#### 6. Refund Fails with "INSUFFICIENT_FUNDS"

**Problem:** Refund requests fail even though payment was successful.

**Solution:**
```python
# 1. Check payment status
if order.can_be_refunded():
    # Payment must be SUCCESS status
    response = order.process_refund()

# 2. For partial refunds, ensure amount is valid
if order.amount >= Decimal("50.00"):
    response = order.process_refund(amount=Decimal("50.00"))

# 3. Check Iyzico merchant account balance
# Refunds require sufficient balance in merchant account

# 4. Wait time: Allow 24 hours after payment before refund
```

#### 7. Admin Shows Wrong Payment Status

**Problem:** Admin displays incorrect status or outdated data.

**Solution:**
```bash
# Sync payment statuses with Iyzico API
python manage.py sync_iyzico_payments --model myapp.Order --days 7

# Check for specific payment
python manage.py sync_iyzico_payments --model myapp.Order --payment-id 12345

# Use --dry-run to see what would be updated
python manage.py sync_iyzico_payments --model myapp.Order --dry-run
```

#### 8. Migration Errors

**Problem:** Errors when running makemigrations or migrate.

**Solution:**
```bash
# 1. Ensure django_iyzico is in INSTALLED_APPS
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    # ...
    'django_iyzico',  # Add this
    'myapp',  # Your app with Order model
]

# 2. Create migrations for your model
python manage.py makemigrations myapp

# 3. Apply migrations
python manage.py migrate

# 4. If you get conflicts, try:
python manage.py makemigrations --merge
```

#### 9. Test Card Numbers Not Working

**Problem:** Sandbox test cards are being rejected.

**Solution:**
```python
# Use Iyzico's official test cards:

# Successful payment test card:
{
    'cardNumber': '5528790000000008',
    'cardHolderName': 'John Doe',
    'expireMonth': '12',
    'expireYear': '2030',
    'cvc': '123'
}

# 3D Secure test card (OTP: 123456):
{
    'cardNumber': '5528790000000008',
    'cardHolderName': 'John Doe',
    'expireMonth': '12',
    'expireYear': '2030',
    'cvc': '123'
}

# Ensure you're using SANDBOX_BASE_URL
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'
```

#### 10. High Response Times

**Problem:** Payment processing is slow.

**Solution:**
```python
# 1. Enable database connection pooling
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}

# 2. Use select_related for foreign keys
orders = Order.objects.select_related('user').all()

# 3. Add database indexes (already included in AbstractIyzicoPayment)
# Check with:
# python manage.py sqlmigrate myapp 0001

# 4. Cache Iyzico settings
from django.core.cache import cache
# Settings are auto-cached in IyzicoClient

# 5. Use async views for I/O-bound operations (Django 4.1+)
from django.views.decorators.http import require_http_methods
```

### Debug Mode

Enable detailed logging for troubleshooting:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django_iyzico': {
            'handlers': ['console'],
            'level': 'DEBUG',  # Shows all API calls
            'propagate': False,
        },
    },
}
```

### Getting Help

If you're still experiencing issues:

1. Check the [GitHub Issues](https://github.com/aladagemre/django-iyzico/issues) for similar problems
2. Review the [SECURITY.md](SECURITY.md) for security-related questions
3. Enable DEBUG logging and check the output
4. Create a new issue with:
   - Django version
   - Python version
   - django-iyzico version
   - Error message and full traceback
   - Minimal code to reproduce the issue

## 📚 Documentation

### Core Documentation
- [**Changelog**](CHANGELOG.md) - Version history and migration guide
- [**Security Policy**](SECURITY.md) - Security features and best practices
- [**Contributing**](CONTRIBUTING.md) - Development guidelines
- [**Development Roadmap**](docs/DEVELOPMENT_ROADMAP.md) - Project roadmap and milestones

### Feature Guides (v0.2.0+)
- [**Subscription Guide**](docs/SUBSCRIPTION_GUIDE.md) - Complete guide to recurring billing (800+ lines)
- [**Installment Guide**](docs/INSTALLMENT_GUIDE.md) - Complete guide to installment payments (800+ lines)
- [**Currency Guide**](docs/CURRENCY_GUIDE.md) - Complete guide to multi-currency support (600+ lines)
- [**Release Notes v0.2.0**](docs/RELEASE_NOTES_v0.2.0.md) - Complete v0.2.0 release documentation

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/aladagemre/django-iyzico.git
cd django-iyzico

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black django_iyzico tests
isort django_iyzico tests

# Run linters
flake8 django_iyzico
mypy django_iyzico
```

## 📊 Project Status

| Phase | Status | Features |
|-------|--------|----------|
| **Milestone 1** | ✅ Complete | Core payment processing, admin, refunds |
| **Milestone 2** | ✅ Complete | Subscription payments with Celery |
| **Milestone 3** | ✅ Complete | Installment payments |
| **Milestone 4** | ✅ Complete | Multi-currency support |
| **Milestone 5** | ✅ Complete | v0.2.0 Release with monitoring & CI/CD |

## 🗺️ Roadmap

### v0.1.0-beta (Released - December 2025)
- ✅ Core payment processing (direct and 3D Secure)
- ✅ Admin interface with advanced features
- ✅ Refund processing (full and partial)
- ✅ Webhook handling with security
- ✅ Management commands
- ✅ 95% test coverage
- ✅ PCI DSS compliance

### v0.2.0 (Released - December 2025)
- ✅ **Subscription payments** - Recurring billing with automated lifecycle
- ✅ **Installment support** - BIN-based installment options and processing
- ✅ **Multi-currency support** - TRY, USD, EUR, GBP with conversion
- ✅ **Celery integration** - Automated subscription billing tasks
- ✅ **Monitoring module** - Structured logging, metrics, and alerting
- ✅ **20 lifecycle signals** - Payment, subscription, and monitoring events
- ✅ **662+ comprehensive tests** - 95%+ coverage maintained
- ✅ **CI/CD workflows** - GitHub Actions for testing and publishing
- ✅ **DevContainer support** - VS Code development environment
- ✅ **Complete example project** - Full Django app with all features

### v0.3.0 (Planned)
- [ ] Payment tokenization
- [ ] Split payments for marketplaces
- [ ] Additional payment methods (bank transfer, etc.)
- [ ] Enhanced reporting and analytics
- [ ] Webhook retry mechanism

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 🙏 Credits

Built on top of the official [iyzipay-python](https://github.com/iyzico/iyzipay-python) SDK.

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/aladagemre/django-iyzico/issues)
- **Security:** See [SECURITY.md](SECURITY.md)


## ⭐ Show Your Support

If django-iyzico helps your project, please give it a star on GitHub!

---

**Author:** Emre Aladag ([@aladagemre](https://github.com/aladagemre))
**Version:** 0.2.0
**Status:** ✅ Production-Ready
**Last Updated:** December 18, 2025
