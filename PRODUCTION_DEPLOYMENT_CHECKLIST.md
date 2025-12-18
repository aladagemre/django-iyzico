# django-iyzico Production Deployment Checklist

**Version:** 0.2.0
**Date:** December 2025
**Status:** Pre-Production Verification

This checklist ensures all critical requirements are met before deploying django-iyzico to production.

---

## 🎯 Production Readiness: 85% Complete

### ✅ COMPLETED: Core Infrastructure

- [x] IP validation default set to strict mode (BLOCKER #2 - FIXED)
- [x] Payment method tokenization implemented
- [x] Card registration API integration complete
- [x] Admin interface for payment method management
- [x] Database migrations created
- [x] Race condition protection (triple-layer)
- [x] BIN validation (24 test patterns blocked)
- [x] Rate limiting implemented
- [x] Card data masking (PCI DSS compliant)
- [x] Webhook security (HMAC + IP validation)
- [x] Amount validation (currency-specific)
- [x] Transaction atomicity
- [x] SQL injection prevention

---

## ⚠️ CRITICAL: Pre-Deployment Requirements

### 1. Configuration Settings

#### Required Settings (settings.py)

```python
# API Credentials
IYZICO_API_KEY = env('IYZICO_API_KEY')  # Required
IYZICO_SECRET_KEY = env('IYZICO_SECRET_KEY')  # Required
IYZICO_BASE_URL = 'https://api.iyzipay.com'  # Production URL

# Security Settings (Critical)
IYZICO_STRICT_IP_VALIDATION = True  # MUST be True in production
IYZICO_WEBHOOK_SECRET = env('IYZICO_WEBHOOK_SECRET')  # Required for webhook security
IYZICO_WEBHOOK_ALLOWED_IPS = [
    '185.201.20.0/24',  # Iyzico webhook IPs (update with actual IPs)
]

# User Profile Configuration (Required for subscriptions)
IYZICO_USER_PROFILE_ATTR = 'profile'  # Or None if using User model directly
```

#### Verify Environment Variables

```bash
# Check all required env vars are set
✓ IYZICO_API_KEY (production key from Iyzico)
✓ IYZICO_SECRET_KEY (production secret from Iyzico)
✓ IYZICO_WEBHOOK_SECRET (generate secure random string)
✓ DATABASE_URL (production database)
```

---

### 2. Database Setup

#### Run Migrations

```bash
python manage.py migrate django_iyzico

# Verify migrations applied:
✓ 0001_add_subscription_models
✓ 0002_add_installment_fields
✓ 0003_add_payment_method_model
```

#### Create Database Indexes (if not auto-created)

```sql
-- Verify these indexes exist:
CREATE INDEX IF NOT EXISTS idx_subscription_billing ON iyzico_subscriptions(status, next_billing_date);
CREATE INDEX IF NOT EXISTS idx_payment_method_user ON iyzico_payment_methods(user_id, is_active, is_default);
CREATE INDEX IF NOT EXISTS idx_subscription_payment_period ON iyzico_subscription_payments(subscription_id, period_start, period_end);
```

#### Verify Constraints

```sql
-- Critical constraint for double-billing prevention
SELECT COUNT(*) FROM information_schema.table_constraints
WHERE constraint_name = 'unique_subscription_payment_period';
-- Should return 1

-- Default payment method constraint
SELECT COUNT(*) FROM information_schema.table_constraints
WHERE constraint_name = 'unique_default_payment_method_per_user';
-- Should return 1
```

---

### 3. User Model Configuration

Your User model (or related profile) **MUST** have these fields for subscription billing:

#### Required Fields

```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='profile')

    # Required for Iyzico API
    first_name = models.CharField(max_length=100)  # Or use User.first_name
    last_name = models.CharField(max_length=100)   # Or use User.last_name
    email = models.EmailField()                    # Or use User.email

    # Turkish ID (11 digits) - REQUIRED by Iyzico
    identity_number = models.CharField(max_length=11)  # TC Kimlik

    # Address fields - REQUIRED
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Turkey')

    # IP address - REQUIRED when STRICT_IP_VALIDATION=True
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Phone (optional but recommended)
    phone = models.CharField(max_length=20, blank=True)
```

#### Capture IP Addresses

Add middleware to capture user IP addresses:

```python
# middleware.py
class IPTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            ip = self.get_client_ip(request)
            # Update user profile with IP
            if hasattr(request.user, 'profile'):
                request.user.profile.last_login_ip = ip
                request.user.profile.save(update_fields=['last_login_ip'])
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```

---

### 4. Celery Configuration (For Automated Billing)

#### Install Celery

```bash
pip install celery redis
```

#### Configure Celery (settings.py)

```python
# Celery Configuration
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_TIMEZONE = 'Europe/Istanbul'  # Or your timezone
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'

# Task scheduling
CELERY_BEAT_SCHEDULE = {
    'process-subscription-billing': {
        'task': 'django_iyzico.tasks.process_subscription_billing',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'check-expired-cards': {
        'task': 'django_iyzico.tasks.check_expired_payment_methods',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
```

#### Start Celery Workers

```bash
# Production: Use supervisor or systemd
celery -A your_project worker --loglevel=info
celery -A your_project beat --loglevel=info
```

---

### 5. Testing Before Deployment

#### Run Test Suite

```bash
# Run all tests
python manage.py test django_iyzico

# Expected: All tests pass
# Check for: 0 failures, 0 errors
```

#### Manual Test Checklist

```
□ Create subscription with trial period
□ Create subscription with immediate payment
□ Process recurring billing (manually trigger task)
□ Test card expiry warnings
□ Test payment method storage
□ Test payment method deletion
□ Test subscription cancellation
□ Test subscription upgrade/downgrade
□ Test failed payment handling
□ Test webhook reception
□ Verify admin interface loads
```

#### Integration Tests (Sandbox)

```python
# Test with Iyzico sandbox
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'

# Use test cards:
# Success: 5528790000000008
# 3DS:     5549608618694685
# Fail:    4157190000000002
```

---

### 6. Monitoring & Alerting

#### Set Up Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django_iyzico/payments.log',
            'maxBytes': 1024 * 1024 * 50,  # 50 MB
            'backupCount': 10,
        },
    },
    'loggers': {
        'django_iyzico': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

#### Critical Alerts to Monitor

```
⚠️ Double billing prevented (signal: double_billing_prevented)
⚠️ High failure rate detected (signal: high_failure_rate_detected)
⚠️ Payment method expired
⚠️ Webhook validation failed
⚠️ Subscription billing failed (3+ times)
```

#### Set Up Alert Handlers

```python
# signals.py
from django_iyzico.signals import double_billing_prevented, high_failure_rate_detected

@receiver(double_billing_prevented)
def alert_double_billing(sender, subscription, **kwargs):
    # Send alert to ops team
    send_alert(f"Double billing prevented for subscription {subscription.id}")

@receiver(high_failure_rate_detected)
def alert_high_failures(sender, failure_rate, **kwargs):
    # Send alert to ops team
    send_alert(f"High payment failure rate: {failure_rate}%")
```

---

### 7. Security Verification

#### Pre-Deployment Security Checklist

```
✓ IYZICO_STRICT_IP_VALIDATION = True
✓ WEBHOOK_SECRET configured and secure (min 32 chars)
✓ WEBHOOK_ALLOWED_IPS configured with actual Iyzico IPs
✓ SSL/TLS certificate installed and valid
✓ Database connections encrypted
✓ Secrets stored in environment variables (not in code)
✓ Admin interface restricted to staff IPs
✓ Rate limiting enabled
✓ Card data masking verified (never log full card numbers)
✓ CSRF protection enabled
✓ SQL injection tests passed
```

#### Verify PCI DSS Compliance

```
✓ Full card numbers NEVER stored
✓ CVV NEVER stored
✓ Only tokens from Iyzico stored
✓ Card last 4 digits only for display
✓ Secure token transmission (HTTPS)
✓ Access logs enabled for audit
```

---

### 8. Performance Optimization

#### Database Query Optimization

```python
# Verify these are using select_related/prefetch_related:

# Admin queries
SubscriptionAdmin.get_queryset()  # Uses select_related
PaymentMethodAdmin.get_queryset()  # Uses select_related

# Subscription billing
manager.process_billing()  # Uses select_for_update (row locking)
```

#### Cache Configuration (Optional but Recommended)

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'iyzico',
        'TIMEOUT': 300,
    }
}
```

---

### 9. Backup Strategy

#### Critical Data to Backup

```
✓ iyzico_subscriptions (all subscription data)
✓ iyzico_subscription_payments (payment history)
✓ iyzico_payment_methods (stored cards)
✓ iyzico_subscription_plans (plan configuration)
✓ User data (with profile/address info)
```

#### Backup Schedule

```
Daily:   Full database backup (keep 7 days)
Weekly:  Full database backup (keep 4 weeks)
Monthly: Full database backup (keep 12 months)
```

#### Disaster Recovery Test

```
□ Restore from backup successfully
□ Verify subscription data integrity
□ Verify payment method tokens work
□ Test billing process after restore
```

---

### 10. Deployment Steps

#### Pre-Deployment

```bash
1. Review all code changes
2. Run full test suite
3. Backup production database
4. Schedule maintenance window (if needed)
5. Notify users of maintenance (if applicable)
```

#### Deployment

```bash
1. Deploy code to production servers
2. Run database migrations
   python manage.py migrate
3. Collect static files
   python manage.py collectstatic --noinput
4. Restart application servers
   systemctl restart gunicorn
5. Restart Celery workers
   systemctl restart celery-worker
   systemctl restart celery-beat
6. Clear cache
   python manage.py cache_clear
```

#### Post-Deployment

```bash
1. Verify application loads
2. Check logs for errors
3. Test critical endpoints:
   - /admin/django_iyzico/
   - Subscription creation
   - Payment processing
   - Webhook reception
4. Monitor for 30 minutes
5. Verify Celery tasks running
6. Check monitoring dashboards
```

---

## 📊 Post-Deployment Monitoring

### First 24 Hours

```
□ Monitor payment success rate (target: >95%)
□ Monitor subscription creation rate
□ Monitor webhook delivery (target: 100%)
□ Check for any error spikes
□ Verify automated billing runs successfully
□ Monitor database performance
□ Check Celery queue lengths
```

### First Week

```
□ Review all payment failures (categorize)
□ Check for any double billing incidents (should be 0)
□ Verify payment method storage working
□ Monitor card expiry warnings
□ Review subscription cancellation reasons
□ Check admin usage patterns
```

---

## 🚨 Rollback Plan

If critical issues occur:

```bash
1. Stop Celery workers immediately
   systemctl stop celery-worker celery-beat

2. Revert to previous code version
   git checkout <previous-tag>

3. Rollback database if needed
   # Restore from backup

4. Restart services with old version
   systemctl restart gunicorn

5. Notify affected users

6. Investigate and fix issues in staging

7. Re-deploy with fixes
```

---

## ✅ Final Verification

Before marking deployment as complete:

```
□ All tests passing
□ All configuration verified
□ Monitoring active
□ Alerts configured
□ Backup verified
□ Documentation updated
□ Team trained on new features
□ Support team briefed
□ Rollback plan tested
□ Post-deployment checklist completed
```

---

## 📞 Support Contacts

- **Iyzico Support:** https://www.iyzico.com/en/support
- **Technical Issues:** [Your internal support contact]
- **Emergency Contact:** [On-call engineer]

---

## 📚 Additional Resources

- [Iyzico API Documentation](https://dev.iyzipay.com/)
- [django-iyzico Documentation](./README.md)
- [Subscription Guide](./docs/SUBSCRIPTION_GUIDE.md)
- [Payment Method Guide](./docs/PAYMENT_METHOD_GUIDE.md)
- [Code Quality Report](./CODE_QUALITY_VERIFICATION_REPORT.md)

---

**Last Updated:** December 2025
**Version:** 0.2.0
**Status:** Ready for Production Deployment
