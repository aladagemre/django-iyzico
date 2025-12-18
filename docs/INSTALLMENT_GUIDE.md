# Installment Payment Guide

Complete guide for implementing installment payments with django-iyzico.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Basic Usage](#basic-usage)
6. [API Reference](#api-reference)
7. [Frontend Integration](#frontend-integration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Examples](#examples)

---

## Overview

Installment payments allow customers to split their purchases into multiple monthly payments. In Turkey, installment payments are very common and most credit cards support 2-12 installment options.

### Features

- ✅ Retrieve installment options by card BIN
- ✅ Display 0% interest campaigns
- ✅ Validate installment selections
- ✅ Process installment payments
- ✅ Track installment details
- ✅ Admin interface for monitoring
- ✅ AJAX/REST API endpoints
- ✅ Caching for performance

### How It Works

1. User enters card number (first 6 digits identify the bank)
2. System fetches available installment options from Iyzico
3. User selects desired installment plan
4. Payment is processed with installment information
5. Installment details are stored with payment record

---

## Quick Start

### 1. Install and Configure

```bash
pip install django-iyzico
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'django_iyzico',
]
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Add URLs

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # ...
    path('iyzico/', include('django_iyzico.installment_urls')),
]
```

### 4. Use in Views

```python
from django_iyzico.installment_client import InstallmentClient
from decimal import Decimal

client = InstallmentClient()

# Get installment options
options = client.get_installment_info(
    bin_number='554960',  # First 6 digits of card
    amount=Decimal('500.00'),
)

# Display options to user
for bank in options:
    for option in bank.installment_options:
        print(f"{option.installment_number}x {option.monthly_price} TRY")
```

---

## Installation

### Requirements

- Python 3.8+
- Django 3.2+
- django-iyzico

### Install Package

```bash
pip install django-iyzico
```

### Add to Django Project

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Add django-iyzico
    'django_iyzico',

    # Your apps
    'yourapp',
]
```

### Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

This will add the following fields to your payment models:
- `installment_rate` - Fee rate percentage
- `monthly_installment_amount` - Monthly payment amount
- `total_with_installment` - Total with fees
- `bin_number` - Card BIN (first 6 digits)

---

## Configuration

### Iyzico Credentials

Set your Iyzico API credentials in `settings.py`:

```python
IYZICO_API_KEY = 'your-api-key'
IYZICO_SECRET_KEY = 'your-secret-key'
IYZICO_BASE_URL = 'https://sandbox-api.iyzipay.com'  # or production URL
```

### Optional: Caching

Installment options are cached for 5 minutes by default. Configure caching:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

---

## Basic Usage

### Retrieving Installment Options

```python
from django_iyzico.installment_client import InstallmentClient
from decimal import Decimal

client = InstallmentClient()

# Get all options for a card
bank_options = client.get_installment_info(
    bin_number='554960',
    amount=Decimal('500.00'),
)

# Process results
for bank in bank_options:
    print(f"Bank: {bank.bank_name}")

    for option in bank.installment_options:
        print(f"  {option.installment_number}x installments")
        print(f"    Monthly: {option.monthly_price} TRY")
        print(f"    Total: {option.total_price} TRY")
        print(f"    Rate: {option.installment_rate}%")

        if option.is_zero_interest:
            print("    ⭐ Zero Interest!")
```

### Getting Best Options

```python
# Get top 5 recommended options
best_options = client.get_best_installment_options(
    bin_number='554960',
    amount=Decimal('1000.00'),
    max_options=5,
)

# These are sorted by:
# 1. Zero interest first
# 2. Lowest total price
# 3. Fewer installments (3-6 preferred)
```

### Validating Selection

```python
# Validate user's installment selection
option = client.validate_installment_option(
    bin_number='554960',
    amount=Decimal('500.00'),
    installment_number=3,
)

if option:
    print(f"✓ Valid: {option.installment_number}x {option.monthly_price} TRY")
else:
    print("✗ Invalid installment selection")
```

### Processing Payment with Installment

```python
from django_iyzico.client import IyzicoClient

# Step 1: Validate installment
installment_client = InstallmentClient()
installment_option = installment_client.validate_installment_option(
    bin_number='554960',
    amount=Decimal('500.00'),
    installment_number=3,
)

if not installment_option:
    raise ValueError('Invalid installment option')

# Step 2: Process payment
iyzico_client = IyzicoClient()
payment_data = {
    'price': '500.00',
    'paidPrice': str(installment_option.total_price),
    'installment': 3,
    # ... other required fields
}

# Step 3: Store installment details
# After successful payment, save:
payment.installment_rate = installment_option.installment_rate
payment.monthly_installment_amount = installment_option.monthly_price
payment.total_with_installment = installment_option.total_price
payment.bin_number = '554960'
payment.save()
```

---

## API Reference

### InstallmentClient

Main client for installment operations.

#### Methods

##### `get_installment_info(bin_number, amount)`

Retrieve all installment options for a card and amount.

**Parameters:**
- `bin_number` (str): First 6 digits of card number
- `amount` (Decimal): Payment amount

**Returns:**
- List[BankInstallmentInfo]: Installment options grouped by bank

**Raises:**
- `IyzicoValidationException`: Invalid parameters
- `IyzicoAPIException`: API error

**Example:**
```python
options = client.get_installment_info('554960', Decimal('500.00'))
```

##### `get_best_installment_options(bin_number, amount, max_options=5)`

Get recommended installment options.

**Parameters:**
- `bin_number` (str): Card BIN
- `amount` (Decimal): Payment amount
- `max_options` (int): Maximum options to return (default: 5)

**Returns:**
- List[InstallmentOption]: Top installment options

**Example:**
```python
best = client.get_best_installment_options('554960', Decimal('1000.00'), max_options=3)
```

##### `validate_installment_option(bin_number, amount, installment_number)`

Validate an installment selection.

**Parameters:**
- `bin_number` (str): Card BIN
- `amount` (Decimal): Payment amount
- `installment_number` (int): Selected installment count

**Returns:**
- InstallmentOption or None: Option if valid, None otherwise

**Example:**
```python
option = client.validate_installment_option('554960', Decimal('500.00'), 3)
if option:
    print(f"Valid: {option.monthly_price} TRY/month")
```

### InstallmentOption

Dataclass representing a single installment option.

**Attributes:**
- `installment_number` (int): Number of installments
- `base_price` (Decimal): Original amount
- `total_price` (Decimal): Total with fees
- `monthly_price` (Decimal): Monthly payment amount
- `installment_rate` (Decimal): Fee rate percentage
- `total_fee` (Decimal): Total installment fee
- `is_zero_interest` (bool): Whether it's 0% interest

**Methods:**
- `to_dict()`: Convert to dictionary

### BankInstallmentInfo

Dataclass representing installment options for a bank.

**Attributes:**
- `bank_name` (str): Bank name
- `bank_code` (int): Bank identifier
- `installment_options` (List[InstallmentOption]): Available options

**Methods:**
- `to_dict()`: Convert to dictionary

### Utility Functions

#### `format_installment_display(installment_count, monthly_payment, currency='TRY', show_total=False, total_with_fees=None, base_amount=None)`

Format installment option for display.

**Returns:** `str` - Formatted display text

**Example:**
```python
from django_iyzico.installment_utils import format_installment_display

display = format_installment_display(
    3,
    Decimal('34.33'),
    'TRY',
    show_total=True,
    total_with_fees=Decimal('103.00'),
    base_amount=Decimal('100.00'),
)
# Returns: "3x 34.33 TRY (Total: 103.00 TRY +3.00 TRY fee)"
```

#### `calculate_installment_payment(base_amount, installment_count, installment_rate=Decimal('0.00'))`

Calculate installment payment breakdown.

**Returns:** `Dict` with payment details

**Example:**
```python
from django_iyzico.installment_utils import calculate_installment_payment

result = calculate_installment_payment(
    Decimal('100.00'),
    3,
    Decimal('3.00'),
)
# Returns:
# {
#     'base_amount': Decimal('100.00'),
#     'installment_count': 3,
#     'total_fee': Decimal('3.00'),
#     'total_with_fees': Decimal('103.00'),
#     'monthly_payment': Decimal('34.33'),
# }
```

---

## Frontend Integration

### AJAX Endpoint

Use the built-in views for AJAX requests:

```javascript
// Fetch installment options when user enters card
async function fetchInstallmentOptions(cardBin, amount) {
    const response = await fetch(
        `/iyzico/installments/?bin=${cardBin}&amount=${amount}`
    );

    const data = await response.json();

    if (data.success) {
        displayOptions(data.banks);
    }
}

// Display options to user
function displayOptions(banks) {
    banks.forEach(bank => {
        console.log(bank.bank_name);

        bank.installment_options.forEach(option => {
            console.log(`${option.installment_number}x ${option.monthly_price}`);
        });
    });
}

// Listen to card input
document.getElementById('card-number').addEventListener('input', (e) => {
    const cardNumber = e.target.value.replace(/\s/g, '');

    if (cardNumber.length >= 6) {
        const bin = cardNumber.substring(0, 6);
        const amount = document.getElementById('amount').value;

        fetchInstallmentOptions(bin, amount);
    }
});
```

### Validate Selection

```javascript
async function validateInstallment(bin, amount, installment) {
    const response = await fetch('/iyzico/installments/validate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            bin: bin,
            amount: amount,
            installment: installment,
        }),
    });

    const data = await response.json();

    if (data.success && data.valid) {
        console.log('Valid installment option');
        console.log('Monthly:', data.option.monthly_price);
    } else {
        console.log('Invalid option');
    }
}
```

### React Component Example

```jsx
import React, { useState, useEffect } from 'react';

function InstallmentSelector({ amount, onSelect }) {
    const [cardBin, setCardBin] = useState('');
    const [options, setOptions] = useState([]);

    useEffect(() => {
        if (cardBin.length >= 6) {
            fetchOptions();
        }
    }, [cardBin]);

    const fetchOptions = async () => {
        const response = await fetch(
            `/iyzico/installments/best/?bin=${cardBin}&amount=${amount}`
        );
        const data = await response.json();

        if (data.success) {
            setOptions(data.options);
        }
    };

    return (
        <div>
            <input
                type="text"
                onChange={(e) => setCardBin(e.target.value.substring(0, 6))}
                placeholder="Card number"
            />

            {options.map(opt => (
                <div key={opt.installment_number} onClick={() => onSelect(opt)}>
                    <span>{opt.installment_number}x</span>
                    <span>{opt.monthly_price} TRY</span>
                    {opt.is_zero_interest && <span>0% Interest!</span>}
                </div>
            ))}
        </div>
    );
}
```

---

## Best Practices

### 1. Always Validate

Always validate installment selections before processing payment:

```python
# ✅ Good
option = client.validate_installment_option(bin, amount, installment)
if option:
    process_payment(option)

# ❌ Bad
process_payment_without_validation(installment)
```

### 2. Cache Appropriately

Installment options are cached for 5 minutes. For real-time accuracy, consider shorter cache times for high-value transactions.

### 3. Handle Errors Gracefully

```python
try:
    options = client.get_installment_info(bin, amount)
except IyzicoValidationException as e:
    # User input error
    return HttpResponse(f"Invalid input: {e}", status=400)
except IyzicoAPIException as e:
    # API error
    logger.error(f"Iyzico API error: {e}")
    return HttpResponse("Service temporarily unavailable", status=503)
```

### 4. Display Zero Interest Prominently

```python
for option in options:
    if option.is_zero_interest:
        # Highlight this option
        display_with_badge(option, "0% Interest Campaign!")
```

### 5. Store Complete Installment Data

```python
# Store all installment details for reporting
payment.installment = option.installment_number
payment.installment_rate = option.installment_rate
payment.monthly_installment_amount = option.monthly_price
payment.total_with_installment = option.total_price
payment.bin_number = card_bin
payment.save()
```

### 6. Inform Users About Total Cost

```python
if option.total_price > option.base_price:
    fee = option.total_price - option.base_price
    message = f"Note: You'll pay {fee} TRY more with installments"
```

---

## Troubleshooting

### Common Issues

#### 1. "BIN number must be 6 digits"

**Problem:** Invalid card BIN format

**Solution:**
```python
# Extract first 6 digits properly
card_number = '5549 6000 0000 0006'
bin_number = card_number.replace(' ', '')[:6]  # '554960'
```

#### 2. "No installment options returned"

**Possible causes:**
- Card BIN not recognized
- Amount too low for installments
- Bank doesn't support installments

**Solution:**
```python
options = client.get_installment_info(bin, amount)

if not options:
    # Offer single payment only
    single_payment_flow()
```

#### 3. Caching Issues

**Problem:** Stale installment data

**Solution:**
```python
# Clear cache manually if needed
from django.core.cache import cache
cache_key = f'installment_{bin}_{amount}'
cache.delete(cache_key)
```

#### 4. "Selected installment not available"

**Problem:** User selected invalid option

**Solution:**
```python
# Always validate before processing
option = client.validate_installment_option(bin, amount, installment)

if not option:
    return JsonResponse({
        'error': 'Please select a valid installment option',
    }, status=400)
```

---

## Examples

### Complete Checkout Flow

```python
from django.views import View
from django.http import JsonResponse
from decimal import Decimal

from django_iyzico.installment_client import InstallmentClient
from django_iyzico.client import IyzicoClient

class CheckoutView(View):
    def post(self, request):
        # Get form data
        card_number = request.POST['card_number']
        amount = Decimal(request.POST['amount'])
        installment = int(request.POST['installment'])

        # Extract BIN
        card_bin = card_number.replace(' ', '')[:6]

        # Step 1: Validate installment
        client = InstallmentClient()
        option = client.validate_installment_option(
            card_bin,
            amount,
            installment,
        )

        if not option:
            return JsonResponse({
                'error': 'Invalid installment option'
            }, status=400)

        # Step 2: Process payment with installment
        iyzico = IyzicoClient()
        payment_result = iyzico.create_payment({
            'price': str(amount),
            'paidPrice': str(option.total_price),
            'installment': installment,
            # ... other fields
        })

        if payment_result['status'] == 'success':
            # Step 3: Store installment details
            payment = Payment.objects.create(
                amount=amount,
                installment=installment,
                installment_rate=option.installment_rate,
                monthly_installment_amount=option.monthly_price,
                total_with_installment=option.total_price,
                bin_number=card_bin,
            )

            return JsonResponse({
                'success': True,
                'payment_id': payment.id,
            })

        return JsonResponse({
            'error': 'Payment failed'
        }, status=400)
```

See `examples/installment_examples.py` for more examples.

---

## Additional Resources

- [Iyzico Installment API Documentation](https://dev.iyzipay.com/)
- [Example Code](../examples/installment_examples.py)
- [Test Suite](../tests/test_installment_client.py)
- [Admin Guide](./ADMIN_GUIDE.md)

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/django-iyzico/issues
- Documentation: https://django-iyzico.readthedocs.io/

---

**Last Updated:** December 2025
**Version:** 0.2.0
