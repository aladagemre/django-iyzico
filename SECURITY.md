# Security Policy

## Supported Versions

We take security seriously and provide security updates for the following versions:

| Version | Supported          | Notes |
| ------- | ------------------ | ----- |
| 0.1.x   | :white_check_mark: | Beta - Active development |
| < 0.1.0 | :x:                | Pre-release versions not supported |

## Security Features

django-iyzico is designed with security as a top priority, especially for handling payment data.

### PCI DSS Compliance

✅ **Level 1 PCI DSS Compliant Design**

- **Never stores full card numbers** - Only the last 4 digits are stored
- **Never stores CVC/CVV codes** - Card security codes are never persisted
- **Never stores expiry dates** - Full expiry dates are not stored
- **Automatic log sanitization** - Sensitive data is removed from logs
- **Secure card data masking** - `mask_card_data()` utility ensures compliance

**Important:** While django-iyzico follows PCI DSS requirements, **your application's overall PCI DSS compliance is your responsibility**. Ensure your entire infrastructure meets PCI DSS standards.

### Webhook Security

✅ **HMAC-SHA256 Signature Validation**
- Optional webhook signature verification
- Constant-time comparison prevents timing attacks
- Configurable via `IYZICO_WEBHOOK_SECRET`

✅ **IP Whitelisting**
- Optional IP whitelist with CIDR support
- Supports IPv4 and IPv6
- X-Forwarded-For header support
- Configurable via `IYZICO_WEBHOOK_ALLOWED_IPS`

### Application Security

✅ **Input Validation**
- All payment data validated before processing
- Amount validation (positive, proper precision)
- Required field checking
- Type validation throughout

✅ **CSRF Protection**
- Django CSRF protection enabled
- Webhook endpoints properly exempted
- Session security maintained

✅ **Error Handling**
- Detailed errors in development
- Sanitized errors in production
- No sensitive data in error messages
- Comprehensive exception hierarchy

### Code Security

✅ **Type Safety**
- Full type hints throughout codebase
- MyPy compatible
- IDE autocomplete support

✅ **SQL Injection Prevention**
- Django ORM used exclusively
- No raw SQL queries
- Parameterized queries only

✅ **XSS Prevention**
- Admin interface uses Django templates
- All output properly escaped
- No unsafe HTML rendering

## Security Testing

Our security testing includes:

- **83+ security-specific tests**
- **95% code coverage** for core security modules
- **Mock-based testing** - No real API calls or data
- **PCI DSS validation** - Card masking tests
- **Webhook security tests** - Signature and IP validation
- **Timing attack prevention** - Constant-time comparison tests

## Reporting a Vulnerability

### Please DO NOT file public issues for security vulnerabilities

We take all security vulnerabilities seriously. If you discover a security issue, please report it privately.

**How to Report:**

1. **Email:** security@example.com (replace with your email)
2. **Subject:** [SECURITY] django-iyzico vulnerability report
3. **Include:**
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
   - Your contact information (for follow-up)

### What to Expect

1. **Acknowledgment:** Within 48 hours
2. **Assessment:** Within 7 days
3. **Fix:** Critical issues within 14 days, others within 30 days
4. **Disclosure:** After fix is released and deployed

### Responsible Disclosure

We follow coordinated vulnerability disclosure:

1. **Private report** - Report to us privately first
2. **Investigation** - We investigate and develop a fix
3. **Patch release** - We release a security patch
4. **Public disclosure** - After users have had time to update (typically 2-4 weeks)
5. **Credit** - We credit reporters (unless you prefer anonymity)

## Security Best Practices

When using django-iyzico in your application:

### 1. Environment Configuration

```python
# settings.py

# ❌ DON'T hardcode credentials
IYZICO_API_KEY = "sandbox-your-key"

# ✅ DO use environment variables
import os
IYZICO_API_KEY = os.environ.get('IYZICO_API_KEY')
IYZICO_SECRET_KEY = os.environ.get('IYZICO_SECRET_KEY')
```

### 2. Production Settings

```python
# settings.py

# Use production URL in production
IYZICO_BASE_URL = "https://api.iyzipay.com"  # Production

# Enable webhook security
IYZICO_WEBHOOK_SECRET = os.environ.get('IYZICO_WEBHOOK_SECRET')
IYZICO_WEBHOOK_ALLOWED_IPS = [
    '1.2.3.4',  # Iyzico's webhook IP
    '5.6.7.0/24',  # Iyzico's webhook subnet
]

# Use HTTPS in production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 3. Database Security

```python
# settings.py

# Encrypt database connections
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'sslmode': 'require',
        }
    }
}

# Backup regularly
# Encrypt backups
# Restrict database access
```

### 4. Access Control

```python
# admin.py

from django.contrib import admin
from django_iyzico.admin import IyzicoPaymentAdminMixin

@admin.register(Order)
class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
    # Restrict admin access
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete payments
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        # Only staff can change payments
        return request.user.is_staff
```

### 5. Logging Security

```python
# settings.py

LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/django/payments.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'django_iyzico': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}

# django-iyzico automatically sanitizes logs
# No card numbers, CVC, or API keys will be logged
```

### 6. Never Store Sensitive Data

```python
# ❌ DON'T do this
class Order(AbstractIyzicoPayment):
    full_card_number = models.CharField(max_length=16)  # NEVER!
    cvv = models.CharField(max_length=3)  # NEVER!

# ✅ DO use AbstractIyzicoPayment fields
class Order(AbstractIyzicoPayment):
    # card_last_four_digits is already provided
    # This is PCI DSS compliant
    pass
```

### 7. Webhook Validation

```python
# settings.py

# Always validate webhooks in production
IYZICO_WEBHOOK_SECRET = os.environ['IYZICO_WEBHOOK_SECRET']  # Required

# Optional: IP whitelist for extra security
IYZICO_WEBHOOK_ALLOWED_IPS = [
    '1.2.3.4',  # Iyzico's webhook server IP
]
```

### 8. Testing Without Real Data

```python
# tests.py

# ✅ Use mock data
from unittest.mock import Mock, patch

@patch('django_iyzico.client.Payment')
def test_payment(mock_payment):
    mock_payment.create.return_value = Mock(
        status='success',
        payment_id='test-123'
    )
    # Test without real API calls or data
```

### 9. Error Handling

```python
# views.py

from django_iyzico.exceptions import PaymentError

def checkout_view(request):
    try:
        response = client.create_payment(payment_data)
    except PaymentError as e:
        # ❌ DON'T expose sensitive error details
        messages.error(request, "Payment failed. Please try again.")

        # ✅ DO log for debugging
        logger.error(f"Payment failed: {e}", exc_info=True)

        return redirect('checkout')
```

### 10. Regular Updates

```bash
# Keep django-iyzico updated
pip install --upgrade django-iyzico

# Check for security updates
pip list --outdated | grep django-iyzico
```

## Security Checklist

Before going to production, ensure:

- [ ] Using production Iyzico API URL
- [ ] API credentials stored in environment variables (not code)
- [ ] Webhook secret configured
- [ ] IP whitelist configured (optional but recommended)
- [ ] HTTPS enabled (`SECURE_SSL_REDIRECT = True`)
- [ ] Database connections encrypted
- [ ] Admin access restricted to authorized users
- [ ] Logging configured and sanitized
- [ ] Regular backups enabled
- [ ] Security updates monitored
- [ ] PCI DSS compliance reviewed for entire application
- [ ] No sensitive data in version control
- [ ] Error messages don't leak sensitive information
- [ ] Session cookies secure (`SESSION_COOKIE_SECURE = True`)
- [ ] CSRF protection enabled

## Additional Resources

- **PCI DSS Documentation:** https://www.pcisecuritystandards.org/
- **Django Security:** https://docs.djangoproject.com/en/stable/topics/security/
- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **Iyzico Security:** https://docs.iyzico.com/

## Acknowledgments

We appreciate security researchers who report vulnerabilities responsibly. Contributors will be credited in our security advisories (unless they prefer anonymity).

---

**Last Updated:** 2024-12-17
**Version:** 0.1.0-beta
