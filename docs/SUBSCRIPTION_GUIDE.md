

# Subscription Payments Guide - django-iyzico

**Complete guide to implementing recurring subscription payments with django-iyzico.**

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Installation & Setup](#installation--setup)
4. [Quick Start](#quick-start)
5. [Subscription Plans](#subscription-plans)
6. [Subscription Lifecycle](#subscription-lifecycle)
7. [Celery Configuration](#celery-configuration)
8. [Signals](#signals)
9. [Admin Interface](#admin-interface)
10. [Testing](#testing)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Overview

django-iyzico's subscription system provides comprehensive recurring payment functionality for SaaS applications, memberships, and subscription-based services.

### Features

- ✅ Multiple billing intervals (daily, weekly, monthly, quarterly, yearly)
- ✅ Trial periods (7-30 days)
- ✅ Automatic recurring billing via Celery
- ✅ Failed payment retry with exponential backoff
- ✅ Subscription upgrades/downgrades with proration
- ✅ Pause/resume functionality
- ✅ Multiple cancellation options
- ✅ Email notifications for all events
- ✅ Comprehensive admin interface
- ✅ Signal-based integration hooks

### Architecture

```
┌─────────────────────────────────────────────────┐
│            Django Application                    │
│  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Subscription │  │ Subscription           │  │
│  │ Plans        │  │ Management             │  │
│  └──────────────┘  └────────────────────────┘  │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│          Celery Beat + Workers                   │
│  - Daily billing (2 AM)                         │
│  - Payment retries (every 6 hours)              │
│  - Trial expiration checks                      │
│  - Cancellation processing                      │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│            Iyzico API                            │
│  - Payment processing                           │
│  - 3D Secure authentication                     │
└──────────────────────────────────────────────────┘
```

---

## Requirements

### System Requirements

```python
# requirements.txt
django>=3.2,<6.0
celery>=5.0
redis>=4.0  # For Celery broker
```

### Infrastructure

1. **Redis** - For Celery message broker
2. **Celery Worker** - For async task processing
3. **Celery Beat** - For scheduled billing tasks

---

## Installation & Setup

### 1. Install Package

```bash
pip install django-iyzico
```

### 2. Add to INSTALLED_APPS

```python
# settings.py

INSTALLED_APPS = [
    # ...
    'django_iyzico',
    # ...
]
```

### 3. Configure Iyzico Settings

```python
# settings.py

# Iyzico API credentials
IYZICO_API_KEY = 'your-api-key'
IYZICO_SECRET_KEY = 'your-secret-key'
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'  # or production URL

# Subscription settings (optional)
IYZICO_SUBSCRIPTION_ENABLED = True
IYZICO_SUBSCRIPTION_RETRY_ATTEMPTS = 3  # Failed payment retries
IYZICO_SUBSCRIPTION_RETRY_DELAY = 86400  # 24 hours between retries
IYZICO_SUBSCRIPTION_DUNNING_PERIOD = 7  # Days before marking as past_due
```

### 4. Configure Celery

```python
# settings.py

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Import subscription tasks schedule
from django_iyzico.celeryconfig import CELERY_BEAT_SCHEDULE as IYZICO_SCHEDULE
CELERY_BEAT_SCHEDULE = IYZICO_SCHEDULE
```

### 5. Create Celery App

```python
# your_project/celery.py

from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

app = Celery('your_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

### 6. Run Migrations

```bash
python manage.py migrate django_iyzico
```

### 7. Start Celery Worker & Beat

```bash
# Terminal 1: Start worker
celery -A your_project worker -l info

# Terminal 2: Start beat scheduler
celery -A your_project beat -l info
```

---

## Quick Start

### Create Subscription Plans

```python
from decimal import Decimal
from django_iyzico.subscription_models import (
    SubscriptionPlan,
    BillingInterval,
)

# Create a monthly plan
basic_plan = SubscriptionPlan.objects.create(
    name='Basic Plan',
    slug='basic',
    description='Perfect for individuals',
    price=Decimal('9.99'),
    currency='USD',
    billing_interval=BillingInterval.MONTHLY,
    trial_period_days=14,
    features={
        'storage': '10GB',
        'projects': 5,
        'api_calls': 10000,
    },
    is_active=True,
)
```

### Subscribe a User

```python
from django_iyzico.subscription_manager import SubscriptionManager

manager = SubscriptionManager()

# Payment method
payment_method = {
    'cardHolderName': 'John Doe',
    'cardNumber': '5528790000000008',
    'expireMonth': '12',
    'expireYear': '2030',
    'cvc': '123',
}

# Create subscription
subscription = manager.create_subscription(
    user=request.user,
    plan=basic_plan,
    payment_method=payment_method,
    trial=True,  # Use trial period
)

print(f"Subscription created! Trial ends: {subscription.trial_end_date}")
```

### Check Subscription Status

```python
# Get user's active subscription
subscription = request.user.iyzico_subscriptions.filter(
    status__in=['active', 'trialing']
).first()

if subscription:
    print(f"Plan: {subscription.plan.name}")
    print(f"Status: {subscription.get_status_display()}")
    print(f"Next billing: {subscription.next_billing_date}")
else:
    print("No active subscription")
```

---

## Subscription Plans

### Creating Plans

```python
# Monthly plan
monthly = SubscriptionPlan.objects.create(
    name='Pro Monthly',
    slug='pro-monthly',
    price=Decimal('29.99'),
    billing_interval=BillingInterval.MONTHLY,
    trial_period_days=14,
)

# Quarterly plan (every 3 months)
quarterly = SubscriptionPlan.objects.create(
    name='Pro Quarterly',
    slug='pro-quarterly',
    price=Decimal('79.99'),
    billing_interval=BillingInterval.MONTHLY,
    billing_interval_count=3,  # Every 3 months
)

# Annual plan
annual = SubscriptionPlan.objects.create(
    name='Pro Annual',
    slug='pro-annual',
    price=Decimal('299.99'),
    billing_interval=BillingInterval.YEARLY,
)
```

### Plan Features (JSON Field)

```python
plan = SubscriptionPlan.objects.create(
    name='Enterprise',
    slug='enterprise',
    price=Decimal('99.99'),
    features={
        'storage': 'Unlimited',
        'projects': 'Unlimited',
        'team_members': 100,
        'support': '24/7 Phone',
        'sla': '99.9%',
        'custom_integrations': True,
        'dedicated_manager': True,
    },
)

# Access features
if plan.features.get('custom_integrations'):
    print("Custom integrations available")
```

### Subscriber Limits

```python
# Limited plan (max 50 subscribers)
limited_plan = SubscriptionPlan.objects.create(
    name='Early Bird Special',
    slug='early-bird',
    price=Decimal('19.99'),
    max_subscribers=50,
)

# Check availability
if limited_plan.can_accept_subscribers():
    # Allow signup
    pass
else:
    # Show "Plan full" message
    pass
```

---

## Subscription Lifecycle

### 1. Create Subscription

```python
from django_iyzico.subscription_manager import SubscriptionManager

manager = SubscriptionManager()

subscription = manager.create_subscription(
    user=user,
    plan=plan,
    payment_method=payment_method,
    trial=True,  # Use trial
    start_date=None,  # Start now (optional)
    metadata={'source': 'web', 'campaign': 'spring2025'},
)
```

**Behavior:**
- With trial: Status = `TRIALING`, no immediate charge
- Without trial: Status = `ACTIVE` or `PAST_DUE`, immediate charge

### 2. Automatic Billing (Celery)

Celery automatically processes billing:

```python
# Runs daily at 2 AM
from django_iyzico.tasks import process_due_subscriptions

# Processes all subscriptions with next_billing_date <= today
result = process_due_subscriptions()
# Returns: {'processed': 50, 'successful': 48, 'failed': 2}
```

### 3. Upgrade Subscription

```python
# Upgrade to higher tier
premium_plan = SubscriptionPlan.objects.get(slug='premium')

updated = manager.upgrade_subscription(
    subscription=subscription,
    new_plan=premium_plan,
    prorate=True,  # Charge prorated amount
)
```

**Proration Calculation:**
```
days_remaining = (period_end - today).days
total_days = (period_end - period_start).days
proration_factor = days_remaining / total_days
price_difference = new_plan.price - old_plan.price
prorated_charge = price_difference * proration_factor
```

### 4. Downgrade Subscription

```python
# Downgrade to lower tier
basic_plan = SubscriptionPlan.objects.get(slug='basic')

# Option 1: Downgrade at period end (recommended)
updated = manager.downgrade_subscription(
    subscription=subscription,
    new_plan=basic_plan,
    at_period_end=True,  # Apply at end of current period
)

# Option 2: Downgrade immediately (with refund)
updated = manager.downgrade_subscription(
    subscription=subscription,
    new_plan=basic_plan,
    at_period_end=False,  # Apply now
)
```

### 5. Pause & Resume

```python
# Pause subscription (stop billing)
paused = manager.pause_subscription(subscription)
# Status: PAUSED, billing stops

# Resume subscription
resumed = manager.resume_subscription(subscription)
# Status: ACTIVE, billing resumes
```

### 6. Cancel Subscription

```python
# Option 1: Cancel at period end (recommended)
cancelled = manager.cancel_subscription(
    subscription=subscription,
    at_period_end=True,
    reason="User requested cancellation",
)
# User keeps access until period end, no further charges

# Option 2: Cancel immediately
cancelled = manager.cancel_subscription(
    subscription=subscription,
    at_period_end=False,
    reason="Fraud detected",
)
# Access revoked immediately
```

---

## Celery Configuration

### Scheduled Tasks

```python
# from django_iyzico.celeryconfig

CELERY_BEAT_SCHEDULE = {
    # Process subscriptions due for billing (daily at 2 AM)
    'process-due-subscriptions': {
        'task': 'django_iyzico.process_due_subscriptions',
        'schedule': crontab(hour=2, minute=0),
    },

    # Retry failed payments (every 6 hours)
    'retry-failed-payments': {
        'task': 'django_iyzico.retry_failed_payments',
        'schedule': crontab(hour='*/6', minute=0),
    },

    # Expire cancelled subscriptions (daily at 3 AM)
    'expire-cancelled-subscriptions': {
        'task': 'django_iyzico.expire_cancelled_subscriptions',
        'schedule': crontab(hour=3, minute=0),
    },

    # Check trial expirations (daily at 1 AM)
    'check-trial-expiration': {
        'task': 'django_iyzico.check_trial_expiration',
        'schedule': crontab(hour=1, minute=0),
    },
}
```

### Manual Task Execution

```python
from django_iyzico.tasks import charge_subscription

# Charge specific subscription (async)
result = charge_subscription.delay(subscription_id=123)

# Wait for result
payment_successful = result.get(timeout=60)
```

---

## Signals

### Available Signals

```python
from django_iyzico.signals import (
    # Lifecycle signals
    subscription_created,
    subscription_activated,
    subscription_cancelled,
    subscription_expired,
    subscription_paused,
    subscription_resumed,

    # Payment signals
    subscription_payment_succeeded,
    subscription_payment_failed,
    subscription_renewal_approaching,
)
```

### Example Signal Handlers

```python
from django.dispatch import receiver
from django_iyzico.signals import subscription_created, subscription_payment_failed

@receiver(subscription_created)
def on_subscription_created(sender, subscription, user, **kwargs):
    """Send welcome email when subscription is created."""
    send_mail(
        subject='Welcome to Premium!',
        message=f'Thank you for subscribing to {subscription.plan.name}',
        from_email='noreply@example.com',
        recipient_list=[user.email],
    )

@receiver(subscription_payment_failed)
def on_payment_failed(sender, subscription, error_message, **kwargs):
    """Notify user of payment failure."""
    send_mail(
        subject='Payment Failed',
        message=f'We were unable to process your payment. Error: {error_message}',
        from_email='noreply@example.com',
        recipient_list=[subscription.user.email],
    )

    # Log to analytics
    analytics.track(subscription.user.id, 'Payment Failed', {
        'subscription_id': subscription.id,
        'plan': subscription.plan.name,
        'error': error_message,
    })
```

---

## Admin Interface

### Features

1. **Subscription Plans Admin**
   - Create/edit plans
   - View subscriber counts
   - Duplicate plans
   - Toggle active status

2. **Subscriptions Admin**
   - View all subscriptions
   - Filter by status, plan, date
   - Color-coded status badges
   - Payment history table
   - Bulk cancellation
   - Manual billing trigger

3. **Subscription Payments Admin**
   - View all recurring payments
   - Filter by retry status, proration
   - Billing period display
   - Retry attempt tracking

### Admin Actions

```python
# Available in Django admin

# 1. Cancel subscriptions (bulk)
#    Select subscriptions → Actions → Cancel selected subscriptions

# 2. Duplicate plan
#    Select plan → Actions → Duplicate selected plans

# 3. Export payments to CSV
#    Select payments → Actions → Export selected payments to CSV
```

---

## Testing

### Test Cards

```python
# Success card
'5528790000000008'

# Failure card (insufficient funds)
'5528790000000004'
```

### Running Tests

```bash
# Run all subscription tests
pytest tests/test_subscription_models.py
pytest tests/test_subscription_manager.py
pytest tests/test_subscription_tasks.py
pytest tests/test_subscription_admin.py

# Run with coverage
pytest --cov=django_iyzico --cov-report=html
```

### Example Test

```python
import pytest
from decimal import Decimal
from django_iyzico.subscription_manager import SubscriptionManager

@pytest.mark.django_db
def test_create_subscription_with_trial(user, plan):
    manager = SubscriptionManager()

    subscription = manager.create_subscription(
        user=user,
        plan=plan,
        payment_method={'cardNumber': '5528790000000008'},
        trial=True,
    )

    assert subscription.status == 'trialing'
    assert subscription.trial_end_date is not None
```

---

## Best Practices

### 1. Payment Method Storage

**⚠️ IMPORTANT:** The current implementation does NOT store payment methods. You must implement one of:

**Option A: Iyzico Tokenization** (Recommended if available)
```python
# TODO: Research Iyzico tokenization API
# Store token instead of card details
```

**Option B: Payment Vault Service**
```python
# Use third-party vault (e.g., Stripe, Adyen)
# Store vault token reference
```

**Option C: User Re-entry**
```python
# Prompt user to re-enter card before each charge
# Lower conversion but PCI compliant
```

### 2. Error Handling

```python
from django_iyzico.exceptions import IyzicoValidationException, IyzicoAPIException

try:
    subscription = manager.create_subscription(...)
except IyzicoValidationException as e:
    # Validation error (inactive plan, at capacity, etc.)
    messages.error(request, str(e))
except IyzicoAPIException as e:
    # API error (network, Iyzico down, etc.)
    logger.error(f"Iyzico API error: {e}")
    messages.error(request, "Payment service unavailable")
```

### 3. Transaction Safety

```python
from django.db import transaction

@transaction.atomic
def subscribe_user(user, plan):
    """Wrap subscription creation in transaction."""
    subscription = manager.create_subscription(
        user=user,
        plan=plan,
        payment_method=payment_method,
    )

    # Update user permissions
    user.groups.add(premium_group)

    return subscription
```

### 4. Monitoring

```python
# Monitor subscription metrics
from django_iyzico.subscription_models import Subscription

# Active subscriptions
active_count = Subscription.objects.filter(
    status__in=['active', 'trialing']
).count()

# Churn rate
monthly_churn = Subscription.objects.filter(
    cancelled_at__month=timezone.now().month
).count()

# MRR (Monthly Recurring Revenue)
from django.db.models import Sum
mrr = Subscription.objects.filter(
    status='active',
    plan__billing_interval='monthly',
).aggregate(
    total=Sum('plan__price')
)['total']
```

### 5. Security

```python
# settings.py

# Secure Celery
CELERY_TASK_ALWAYS_EAGER = False  # Prevent sync execution in production
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True

# Rate limiting
CELERY_TASK_ANNOTATIONS = {
    'django_iyzico.charge_subscription': {
        'rate_limit': '10/m',  # Max 10 charges per minute
    },
}

# Secure admin
# Only allow trusted IPs to access admin
ALLOWED_HOSTS = ['your-domain.com']
```

---

## Troubleshooting

### Issue: Subscriptions not billing automatically

**Solution:**
1. Check Celery worker is running: `celery -A your_project worker -l info`
2. Check Celery beat is running: `celery -A your_project beat -l info`
3. Verify beat schedule is loaded: Look for "Scheduler: Sending due task" in logs
4. Check Redis connection: `redis-cli ping`

### Issue: Payment method not found

**Solution:**
Payment method storage is not yet implemented. See [Best Practices - Payment Method Storage](#1-payment-method-storage).

### Issue: Duplicate billing

**Solution:**
The system prevents duplicate billing within 1 hour. If you need to bill sooner:
```python
# Wait 1 hour, or
# Manually adjust next_billing_date
subscription.next_billing_date = timezone.now()
subscription.save()
```

### Issue: Trial not working

**Solution:**
Check plan has `trial_period_days > 0` and you're passing `trial=True`:
```python
subscription = manager.create_subscription(
    user=user,
    plan=plan,
    payment_method=payment_method,
    trial=True,  # Must be True
)
```

---

## Next Steps

1. **Implement Payment Method Storage** - Choose tokenization or vault strategy
2. **Customize Email Templates** - Update notification templates in `tasks.py`
3. **Add Webhooks** - Implement Iyzico webhooks for real-time updates
4. **Set Up Monitoring** - Add metrics tracking and alerting
5. **Test in Production** - Start with small user base, monitor closely

---

## Support

- **Documentation:** https://github.com/aladagemre/django-iyzico
- **Issues:** https://github.com/aladagemre/django-iyzico/issues
- **Email:** aladagemre@gmail.com

---

**Version:** 0.2.0
**Last Updated:** December 17, 2025
**License:** MIT
