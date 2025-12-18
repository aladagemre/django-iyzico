# Release Notes: django-iyzico v0.2.0

**Release Date:** December 18, 2025
**Status:** ✅ Released
**Type:** Major Feature Release

---

## 🎉 Overview

We're excited to announce the release of **django-iyzico v0.2.0**, a major update that adds three powerful features for payment processing in Django applications:

- **Subscription Payments** - Automated recurring billing with full lifecycle management
- **Installment Payments** - Complete installment support with BIN-based options
- **Multi-Currency Support** - Process payments in TRY, USD, EUR, and GBP

This release adds **~12,000 lines of production code**, includes **662+ comprehensive tests** across 22 test files, and maintains our commitment to **95%+ test coverage**.

**Additional v0.2.0 Features:**
- **Monitoring Module** - Structured logging, metrics, and alerting
- **CI/CD Workflows** - GitHub Actions for automated testing and publishing
- **DevContainer Support** - VS Code development environment
- **Complete Example Project** - Full Django e-commerce application

---

## 🌟 What's New

### 1. Subscription Payments (Milestone 2)

Complete recurring billing system with automated lifecycle management.

**Key Features:**
- ✅ **Subscription Plans** - Define flexible billing plans (monthly, yearly, weekly)
- ✅ **Subscription Management** - Create, cancel, pause, resume, upgrade, downgrade
- ✅ **Trial Periods** - Configurable trial periods with automatic conversion
- ✅ **Automated Billing** - Celery-based automated recurring charges
- ✅ **Failed Payment Handling** - Retry logic with grace periods
- ✅ **Proration** - Automatic proration for plan changes
- ✅ **9 Lifecycle Signals** - Complete event-driven architecture
- ✅ **Admin Interface** - Professional subscription management UI

**Example:**
```python
from django_iyzico.subscription_models import SubscriptionPlan
from django_iyzico.subscription_manager import SubscriptionManager

# Create a plan
plan = SubscriptionPlan.objects.create(
    name="Premium Monthly",
    price=Decimal("99.00"),
    currency="TRY",
    billing_interval="MONTHLY",
    trial_days=7
)

# Subscribe a user
manager = SubscriptionManager()
subscription = manager.create_subscription(
    plan=plan,
    user=request.user,
    payment_method=card_data
)

# Subscription automatically bills every month!
```

**Documentation:** [SUBSCRIPTION_GUIDE.md](SUBSCRIPTION_GUIDE.md)

**Stats:**
- 577 lines: Models
- 753 lines: Manager
- 492 lines: Celery tasks
- 468 lines: Admin
- 230+ tests (95% coverage)

---

### 2. Installment Payments (Milestone 3)

Full installment support with BIN-based installment options.

**Key Features:**
- ✅ **Installment Client** - Fetch installment options from Iyzico API
- ✅ **BIN Detection** - Automatic installment options based on card BIN
- ✅ **Installment Utilities** - 15+ utility functions for calculations
- ✅ **AJAX/REST Views** - Frontend-ready API endpoints
- ✅ **Zero-Interest Detection** - Identify and highlight 0% interest options
- ✅ **Admin Enhancements** - Installment display in payment admin
- ✅ **5-Minute Caching** - Performance optimization

**Example:**
```python
from django_iyzico.installment_client import InstallmentClient

# Get installment options for a card
client = InstallmentClient()
options = client.get_installment_info(
    bin_number='552879',  # First 6 digits
    price=Decimal('1000.00')
)

# Display to user
for option in options:
    print(f"{option.installment_count}x - {option.installment_price}/month")
    if option.installment_rate == 0:
        print("🎉 0% Interest!")

# Process with installments
payment_data['installment'] = 3
response = client.create_payment(payment_data)
```

**Documentation:** [INSTALLMENT_GUIDE.md](INSTALLMENT_GUIDE.md)

**Stats:**
- 450 lines: Client
- 400 lines: Utilities
- 450 lines: Views
- 165+ tests (95% coverage)

---

### 3. Multi-Currency Support (Milestone 4)

Process payments in multiple currencies with automatic conversion.

**Key Features:**
- ✅ **4 Supported Currencies** - TRY, USD, EUR, GBP
- ✅ **Currency Validation** - Case-insensitive with normalization
- ✅ **Locale-Aware Formatting** - Proper number formatting per currency
- ✅ **Currency Conversion** - Built-in converter with customizable rates
- ✅ **9 Model Methods** - Easy currency operations on payments
- ✅ **Admin Enhancements** - Currency symbols and formatted displays
- ✅ **Helper Functions** - Complete currency utility toolkit

**Example:**
```python
from django_iyzico.currency import format_amount, CurrencyConverter

# Create payment in any currency
payment = Payment.objects.create(
    amount=Decimal("100.00"),
    currency='USD'
)

# Format with symbol
formatted = payment.get_formatted_amount()  # "$100.00"

# Convert to another currency
converter = CurrencyConverter()
try_amount = payment.convert_to_currency('TRY')
print(f"$100 = ₺{try_amount}")

# Get currency info
symbol = payment.get_currency_symbol()  # "$"
name = payment.get_currency_name()  # "US Dollar"
```

**Documentation:** [CURRENCY_GUIDE.md](CURRENCY_GUIDE.md)

**Stats:**
- 620 lines: Currency module
- 155 lines: Model extensions
- 100+ tests (98% coverage)

---

## 🔧 Additional Improvements

### Celery Integration
- 6 automated tasks for subscription billing
- Celery Beat schedule configuration
- Retry logic for failed payments
- Subscription expiration handling

### Enhanced Signal System
- **17 total signals** (up from 8)
- 9 new subscription lifecycle signals
- Event-driven architecture for all major operations

### Admin Interface Enhancements
- Currency symbols in amount displays
- Installment display with zero-interest badges
- Subscription management interface
- Color-coded subscription statuses
- Payment history viewer

### Documentation
- **2,200+ lines of new documentation**
- 3 comprehensive feature guides
- 3 milestone completion reports
- 28 complete examples across all guides

---

## 📊 By the Numbers

| Metric | v0.1.0-beta | v0.2.0 | Change |
|--------|-------------|--------|--------|
| Production Lines | ~6,000 | ~12,000 | +100% |
| Test Lines | ~3,500 | ~12,000 | +243% |
| Total Tests | 312 | 662+ | +112% |
| Test Coverage | 95% | 95%+ | Maintained |
| Signals | 8 | 20 | +150% |
| Admin Classes | 1 | 4 | +300% |
| Models | 1 | 4 | +300% |
| Documentation Files | 12 | 21 | +75% |

---

## 🚀 Upgrade Guide

### From v0.1.0-beta to v0.2.0

**Step 1: Update Package**
```bash
pip install --upgrade django-iyzico
```

**Step 2: Run Migrations**
```bash
python manage.py migrate
```

**Step 3: Update Settings (Optional)**

If you want to use subscriptions with Celery:
```python
# settings.py

# Add Celery configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Configure Celery Beat schedule (optional - use defaults)
from django_iyzico.subscription_tasks import get_beat_schedule
CELERY_BEAT_SCHEDULE = get_beat_schedule()
```

**Step 4: Start Celery Workers (for subscriptions)**
```bash
# Start Celery worker
celery -A your_project worker -l info

# Start Celery Beat (for scheduled tasks)
celery -A your_project beat -l info
```

**That's it!** All new features are backward compatible. Your existing payment processing code will continue to work without changes.

---

## ⚠️ Breaking Changes

**None!** This release is **100% backward compatible** with v0.1.0-beta.

All new features are:
- ✅ Additive (no removals or modifications to existing APIs)
- ✅ Optional (subscription and installment features are opt-in)
- ✅ Non-breaking (existing payment flows unchanged)

---

## 🔒 Security

All new features maintain our PCI DSS Level 1 compliance:
- ✅ No full card numbers stored
- ✅ No CVC/CVV stored
- ✅ Secure webhook validation
- ✅ Input validation on all endpoints
- ✅ Log sanitization

---

## 🐛 Known Issues

None at this time. If you encounter any issues, please report them on [GitHub Issues](https://github.com/aladagemre/django-iyzico/issues).

---

## 📚 Documentation

### New Guides
- [Subscription Guide](SUBSCRIPTION_GUIDE.md) - 800+ lines
- [Installment Guide](INSTALLMENT_GUIDE.md) - 800+ lines
- [Currency Guide](CURRENCY_GUIDE.md) - 600+ lines

### Milestone Reports
- [Milestone 2 Complete](MILESTONE_2_COMPLETE.md) - Subscriptions
- [Milestone 3 Complete](MILESTONE_3_COMPLETE.md) - Installments
- [Milestone 4 Complete](MILESTONE_4_COMPLETE.md) - Multi-Currency

### Core Documentation
- [Changelog](../CHANGELOG.md) - Complete version history
- [Development Roadmap](DEVELOPMENT_ROADMAP.md) - Project roadmap

---

## 🎯 What's Next?

### v0.3.0 (Planned)
- Payment tokenization
- Split payments for marketplaces
- Additional payment methods (bank transfer)
- Enhanced reporting and analytics
- Webhook retry mechanism

See [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for details.

---

## 🙏 Acknowledgments

Thank you to:
- The Django community for the excellent framework
- Iyzico for their payment gateway and API
- All contributors and users of django-iyzico
- The Python packaging community

---

## 💬 Support

- **Documentation:** [README.md](../README.md)
- **Issues:** [GitHub Issues](https://github.com/aladagemre/django-iyzico/issues)
- **Security:** [SECURITY.md](../SECURITY.md)
- **Discussions:** [GitHub Discussions](https://github.com/aladagemre/django-iyzico/discussions)

---

## 📝 Full Changelog

For a complete list of all changes, see [CHANGELOG.md](../CHANGELOG.md).

---

**Happy Coding!** 🚀

---

**Version:** 0.2.0
**Release Date:** December 18, 2025
**Author:** Emre Aladag ([@aladagemre](https://github.com/aladagemre))
