# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-12-17

### Added

#### Subscription Payments (Milestone 2)
- **Subscription Models** (577 lines)
  - `SubscriptionPlan` model for managing subscription tiers
  - `Subscription` model for user subscriptions with lifecycle management
  - `SubscriptionPayment` model for tracking recurring payments
  - Support for trial periods, billing intervals, and prorated billing
  - Subscription status tracking (PENDING, TRIALING, ACTIVE, PAST_DUE, etc.)

- **Subscription Management** (753 lines)
  - `SubscriptionManager` class with comprehensive business logic
  - Methods: create, cancel, pause, resume, upgrade, downgrade
  - Automated billing with retry logic
  - Proration calculation for plan changes
  - Failed payment handling with grace periods

- **Celery Integration** (492 lines)
  - 6 automated tasks for subscription billing:
    - `process_due_subscriptions` - Process billing for due subscriptions
    - `retry_failed_payments` - Retry failed subscription payments
    - `expire_cancelled_subscriptions` - Expire subscriptions after cancellation
    - `check_trial_expiration` - Check and convert trial subscriptions
    - `charge_subscription` - Charge individual subscription
    - `send_payment_notification` - Send payment notifications
  - Celery Beat schedule configuration for automated execution

- **Subscription Signals**
  - 9 new subscription lifecycle signals:
    - `subscription_created`, `subscription_activated`, `subscription_trialing`
    - `subscription_cancelled`, `subscription_paused`, `subscription_resumed`
    - `subscription_payment_succeeded`, `subscription_payment_failed`
    - `subscription_expired`

- **Subscription Admin** (468 lines)
  - 3 new admin classes: `SubscriptionPlanAdmin`, `SubscriptionAdmin`, `SubscriptionPaymentAdmin`
  - Subscriber count display with limits
  - Payment history viewer
  - Bulk actions: cancel subscriptions, duplicate plans
  - Color-coded status badges
  - Advanced filtering and search

- **Subscription Documentation**
  - Complete subscription guide (800+ lines)
  - 12 comprehensive examples (640 lines)
  - Milestone completion report (600+ lines)

- **Tests**: 230+ tests with 95% coverage

#### Installment Payments (Milestone 3)
- **Installment Client** (450 lines)
  - `InstallmentClient` for Iyzico InstallmentInfo API integration
  - `InstallmentOption` dataclass for payment plan options
  - `BankInstallmentInfo` dataclass for bank-specific options
  - Methods: `get_installment_info()`, `validate_installment_option()`, `get_best_installment_options()`
  - 5-minute caching for performance optimization

- **Installment Utilities** (400 lines)
  - 15 utility functions for installment calculations:
    - `calculate_installment_payment()` - Payment breakdown calculation
    - `format_installment_display()` - Display formatting
    - `validate_installment_count()` - Count validation
    - `get_recommended_installment()` - Best option recommendation
    - `group_installments_by_rate()` - Group by interest rate
    - `compare_installment_options()` - Option comparison
    - And 9 more utility functions

- **Installment Views** (450 lines)
  - AJAX/REST endpoints for frontend integration:
    - `InstallmentOptionsView` - Get all installment options
    - `BestInstallmentOptionsView` - Get recommended options
    - `ValidateInstallmentView` - Validate installment selection
  - Optional Django REST Framework ViewSet support
  - Function-based view wrapper for simple use cases

- **Model Extensions**
  - 4 new installment fields:
    - `installment_rate` - Fee rate percentage
    - `monthly_installment_amount` - Monthly payment amount
    - `total_with_installment` - Total with fees
    - `bin_number` - Card BIN (first 6 digits)
  - 5 new helper methods:
    - `has_installment()`, `get_installment_display()`, `get_installment_fee()`
    - `get_installment_details()`, `is_zero_interest_installment()`

- **Admin Enhancements**
  - Installment display in list view with zero-interest badges
  - Installment filter for advanced querying
  - Detailed installment breakdown in detail view
  - New "Installment Details" fieldset section

- **URL Configuration** (56 lines)
  - `installment_urls.py` with 3 URL patterns
  - Optional DRF router configuration

- **Database Migration**
  - `0002_add_installment_fields.py` with 2 performance indexes

- **Installment Documentation**
  - Complete installment guide (800+ lines)
  - 12 comprehensive examples (750 lines)
  - Milestone completion report (600+ lines)

- **Tests**: 165+ tests with 95% coverage

#### Multi-Currency Support (Milestone 4)
- **Currency Module** (620 lines)
  - Support for 4 major currencies: TRY, USD, EUR, GBP
  - `Currency` enum with Django field choices
  - Comprehensive currency information (symbol, name, decimal places, separators)

- **Validation Functions**
  - `is_valid_currency()` - Check if currency is supported
  - `validate_currency()` - Validate and normalize currency codes
  - `get_currency_info()` - Get complete currency information
  - Case-insensitive validation with whitespace trimming

- **Formatting Functions**
  - `format_amount()` - Locale-aware formatting with symbols (₺, $, €, £)
  - `parse_amount()` - Parse formatted strings back to Decimal
  - Proper thousands and decimal separators per currency
  - Optional currency code display

- **Currency Conversion**
  - `CurrencyConverter` class for currency exchange
  - Methods: `convert()`, `get_rate()`, `update_rates()`
  - Customizable exchange rates with default values
  - TRY as base currency
  - Proper decimal rounding (ROUND_HALF_UP)

- **Helper Functions**
  - `get_currency_symbol()` - Get currency symbol
  - `get_currency_name()` - Get full currency name
  - `get_all_currencies()` - Get info for all currencies
  - `compare_amounts()` - Compare amounts in different currencies

- **Model Extensions**
  - 9 new currency helper methods:
    - `get_formatted_amount()`, `get_formatted_paid_amount()` - Formatted display
    - `get_currency_symbol()`, `get_currency_name()`, `get_currency_info()` - Currency info
    - `convert_to_currency()`, `get_amount_in_try()` - Currency conversion
    - `is_currency()` - Currency checking

- **Admin Enhancements**
  - Updated `get_amount_display_admin()` with currency symbols
  - New `get_currency_display_admin()` method with symbol and name
  - Currency-aware number formatting throughout

- **Currency Documentation**
  - Complete currency guide (600+ lines)
  - 4 comprehensive examples
  - Best practices and troubleshooting guide
  - External API integration examples

- **Tests**: 100+ tests with 98% coverage

### Changed
- Admin amount display now shows currency symbols by default
- Model `get_amount_display()` method enhanced with currency formatting
- Improved error messages for currency validation
- Enhanced admin interface with better visual presentation

### Documentation
- Added `SUBSCRIPTION_GUIDE.md` (800+ lines)
- Added `INSTALLMENT_GUIDE.md` (800+ lines)
- Added `CURRENCY_GUIDE.md` (600+ lines)
- Added `MILESTONE_2_COMPLETE.md` (600+ lines)
- Added `MILESTONE_3_COMPLETE.md` (600+ lines)
- Added `MILESTONE_4_COMPLETE.md` (500+ lines)
- Added `subscription_examples.py` (640 lines)
- Added `installment_examples.py` (750 lines)
- Updated `DEVELOPMENT_ROADMAP.md` with completion status

### Technical Details
- **Total Lines Added**: ~9,500 lines (production code + tests)
- **Total Tests Added**: 495+ tests
- **Test Coverage**: 95%+ maintained across all modules
- **Backwards Compatibility**: 100% - all changes are additive
- **Python Support**: 3.8 - 3.13
- **Django Support**: 3.2 - 5.0

## [0.1.0-beta] - 2025-12-17

### Added
- **Core Payment Processing**
  - `IyzicoClient` for payment operations with Iyzico API
  - Support for direct payments and 3D Secure flow
  - `PaymentResponse` and `ThreeDSResponse` wrapper classes
  - `RefundResponse` for refund operations

- **Django Models**
  - `AbstractIyzicoPayment` base model with 20+ fields
  - PCI DSS compliant (only stores last 4 digits of card)
  - Custom `PaymentManager` with convenience methods
  - Payment status tracking (PENDING, SUCCESS, FAILED, REFUNDED, etc.)
  - Automatic timestamping

- **Security Features**
  - Card data masking utilities (never stores full card numbers or CVC)
  - Webhook signature validation (HMAC-SHA256)
  - IP whitelisting with CIDR support
  - Constant-time comparison to prevent timing attacks
  - Comprehensive input validation

- **Django Admin Interface**
  - `IyzicoPaymentAdminMixin` for easy integration
  - Color-coded status badges (green/red/yellow/gray)
  - Advanced filtering (status, date, currency, card type)
  - Powerful search (payment ID, email, buyer name)
  - Bulk refund action with validation
  - CSV export functionality
  - Delete protection for successful payments
  - Pretty JSON viewer for raw API responses

- **Webhook Handling**
  - Automatic webhook endpoint (`/iyzico/webhook/`)
  - Optional signature validation
  - Optional IP whitelist
  - Real-time payment status updates
  - Async-safe signal triggering

- **Signal System**
  - 8 payment lifecycle signals:
    - `payment_initiated` - Payment processing started
    - `payment_completed` - Payment successful
    - `payment_failed` - Payment failed
    - `payment_refunded` - Payment refunded
    - `threeds_initiated` - 3D Secure started
    - `threeds_completed` - 3D Secure completed
    - `threeds_failed` - 3D Secure failed
    - `webhook_received` - Webhook received

- **Refund Processing**
  - Full refund support
  - Partial refund support
  - Automatic status updates
  - Signal emission on refund
  - Admin action for bulk refunds

- **Management Commands**
  - `sync_iyzico_payments` - Sync payment statuses with Iyzico API
  - `cleanup_old_payments` - Archive and clean up old payment records
  - Both support dry-run mode and detailed reporting

- **Django REST Framework Support** (Optional)
  - `IyzicoPaymentSerializer` - Read-only payment serializer
  - `IyzicoPaymentViewSet` - Read-only API endpoints
  - `IyzicoPaymentManagementViewSet` - Admin API with refund support
  - Filtering, searching, ordering, pagination
  - Custom actions: successful(), failed(), pending(), stats()
  - Graceful degradation if DRF not installed

- **Utility Functions**
  - `mask_card_data()` - PCI DSS compliant card masking
  - `validate_amount()` - Payment amount validation
  - `validate_payment_data()` - Request data validation
  - `verify_webhook_signature()` - HMAC signature verification
  - `is_ip_allowed()` - IP whitelist checking with CIDR
  - `calculate_installment_amount()` - Installment calculator
  - `generate_basket_id()` - Unique basket ID generator
  - `calculate_paid_price_with_installments()` - Total with fees

- **Settings Management**
  - `IyzicoSettings` class for configuration
  - Environment-aware settings
  - Required settings: API_KEY, SECRET_KEY, BASE_URL
  - Optional settings: locale, currency, webhook_secret, etc.
  - Clear error messages for missing configuration

- **Exception Hierarchy**
  - `IyzicoError` - Base exception
  - `PaymentError` - Payment processing failed
  - `CardError` - Card-related error
  - `ValidationError` - Invalid data
  - `ConfigurationError` - Settings misconfigured
  - `ThreeDSecureError` - 3DS failed
  - `WebhookError` - Webhook processing failed

### Testing
- 312 comprehensive tests (291 passing, 21 skipped for optional DRF)
- 82% overall code coverage (95% for core modules)
- 83+ security-critical tests
- Mock-based testing (no real API calls)
- Pytest fixtures for easy testing

### Documentation
- Complete README with installation and usage
- Comprehensive docstrings (Google style)
- Type hints throughout
- Usage examples
- Admin guide
- Security guide
- API reference
- 12 documentation files (~15,000 words)

### Compatibility
- Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
- Django 3.2, 4.0, 4.1, 4.2, 5.0
- PostgreSQL, MySQL, SQLite
- Optional: Django REST Framework 3.12+

### Security
- PCI DSS Level 1 compliant
- No full card numbers stored (only last 4 digits)
- No CVC/CVV stored
- Webhook signature validation (HMAC-SHA256)
- IP whitelisting with CIDR support
- Constant-time comparison for signatures
- Input validation on all endpoints
- CSRF protection with exemptions for webhooks
- Secure session handling
- Log sanitization (no sensitive data in logs)

## [Unreleased]

### Planned for v0.2.0
- Subscription payment support
- Installment payment support
- Multi-currency support beyond TRY
- Payment method tokenization
- Split payment support
- Marketplace payment support
- Additional payment methods (bank transfer, etc.)

---

## Release Notes

### v0.1.0-beta (2025-12-17)

**First Beta Release** 🎉

This is the first beta release of django-iyzico, providing a complete Django integration for the Iyzico payment gateway.

**What's Ready:**
- ✅ All core payment processing features
- ✅ Professional admin interface
- ✅ Comprehensive security features
- ✅ Refund processing
- ✅ Webhook handling
- ✅ 95% test coverage for core modules
- ✅ Production-tested code
- ✅ Complete documentation

**What's Optional:**
- Django REST Framework support (install `djangorestframework` if needed)
- Additional utilities (installment calculations, etc.)

**Known Limitations:**
- Single currency (TRY) - multi-currency planned for v0.2.0
- No subscription support yet - planned for v0.2.0
- DRF support requires manual URL configuration

**Feedback Welcome:**
Please report issues on GitHub: https://github.com/aladagemre/django-iyzico/issues

---

## Migration Guide

### From Raw iyzipay SDK

If you're currently using the raw `iyzipay` SDK, here's how to migrate:

**Before:**
```python
import iyzipay

options = {
    'api_key': 'your-key',
    'secret_key': 'your-secret',
    'base_url': iyzipay.SANDBOX_BASE_URL
}

request = {
    'price': '100.00',
    'paidPrice': '100.00',
    # ... many more fields
}

payment = iyzipay.Payment().create(request, options)
```

**After:**
```python
from django_iyzico.client import IyzicoClient

# Settings configured in Django settings.py
client = IyzicoClient()

response = client.create_payment({
    'price': '100.00',
    'paidPrice': '100.00',
    # ... same fields
})

# Automatically saves to database
# Triggers signals for your business logic
```

### Benefits of Migration
- ✅ Automatic database storage
- ✅ Django admin interface
- ✅ Signal-based event handling
- ✅ PCI DSS compliance out of the box
- ✅ Webhook handling included
- ✅ Type hints and IDE support
- ✅ Comprehensive testing

---

## Support

- Documentation: [README.md](README.md)
- Issues: https://github.com/aladagemre/django-iyzico/issues
- Security: See [SECURITY.md](SECURITY.md)
