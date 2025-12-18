# Multi-Currency Support Guide

Complete guide for using multi-currency payments with django-iyzico.

## Table of Contents

1. [Overview](#overview)
2. [Supported Currencies](#supported-currencies)
3. [Quick Start](#quick-start)
4. [Currency Validation](#currency-validation)
5. [Currency Formatting](#currency-formatting)
6. [Currency Conversion](#currency-conversion)
7. [Model Methods](#model-methods)
8. [Admin Interface](#admin-interface)
9. [Best Practices](#best-practices)
10. [Examples](#examples)

---

## Overview

django-iyzico v0.2.0 introduces comprehensive multi-currency support, allowing you to process payments in multiple currencies and perform currency conversions.

### Features

- ✅ Support for 4 major currencies (TRY, USD, EUR, GBP)
- ✅ Currency validation and normalization
- ✅ Locale-aware formatting with symbols
- ✅ Currency conversion utilities
- ✅ Model helper methods
- ✅ Enhanced admin interface
- ✅ Comprehensive testing

---

## Supported Currencies

| Code | Name | Symbol | Decimal Places |
|------|------|--------|----------------|
| TRY | Turkish Lira | ₺ | 2 |
| USD | US Dollar | $ | 2 |
| EUR | Euro | € | 2 |
| GBP | British Pound Sterling | £ | 2 |

### Default Currency

The default currency is **TRY** (Turkish Lira), as Iyzico is a Turkish payment gateway.

---

## Quick Start

### Basic Usage

```python
from decimal import Decimal
from django_iyzico.currency import (
    Currency,
    format_amount,
    CurrencyConverter,
)

# Format amount with currency symbol
formatted = format_amount(Decimal('1234.56'), 'USD')
print(formatted)  # $1,234.56

# Convert between currencies
converter = CurrencyConverter()
eur_amount = converter.convert(
    Decimal('100.00'),
    'USD',
    'EUR'
)
print(f"100 USD = {eur_amount} EUR")
```

### With Payment Models

```python
from django_iyzico.models import Payment

payment = Payment.objects.get(id=1)

# Get formatted amount with symbol
print(payment.get_formatted_amount())  # $100.00

# Get currency symbol
print(payment.get_currency_symbol())  # $

# Convert to another currency
try_amount = payment.convert_to_currency('TRY')
print(f"Amount in TRY: {try_amount}")
```

---

## Currency Validation

### Validating Currency Codes

```python
from django_iyzico.currency import (
    is_valid_currency,
    validate_currency,
)

# Check if valid
if is_valid_currency('USD'):
    print("USD is supported")

# Validate and normalize
try:
    currency = validate_currency('usd')  # Case-insensitive
    print(currency)  # 'USD'
except ValueError as e:
    print(f"Invalid currency: {e}")
```

### Currency Enum

```python
from django_iyzico.currency import Currency

# Get all supported currencies
currencies = Currency.values()
print(currencies)  # ['TRY', 'USD', 'EUR', 'GBP']

# Get Django field choices
choices = Currency.choices()
# [('TRY', 'Turkish Lira (TRY)'), ...]

# Get default currency
default = Currency.default()  # 'TRY'
```

### Getting Currency Info

```python
from django_iyzico.currency import get_currency_info

info = get_currency_info('USD')
print(info['symbol'])  # $
print(info['name'])  # US Dollar
print(info['decimal_places'])  # 2
```

---

## Currency Formatting

### Basic Formatting

```python
from decimal import Decimal
from django_iyzico.currency import format_amount

# Format with symbol (default)
amount = format_amount(Decimal('1234.56'), 'USD')
print(amount)  # $1,234.56

# Format without symbol
amount = format_amount(
    Decimal('1234.56'),
    'USD',
    show_symbol=False
)
print(amount)  # 1,234.56

# Format with currency code
amount = format_amount(
    Decimal('1234.56'),
    'EUR',
    show_code=True
)
print(amount)  # €1.234,56 EUR
```

### Locale-Aware Formatting

Different currencies use different thousands and decimal separators:

```python
# USD: 1,234.56 (comma thousands, dot decimal)
format_amount(Decimal('1234.56'), 'USD')

# TRY: 1.234,56 (dot thousands, comma decimal)
format_amount(Decimal('1234.56'), 'TRY')

# EUR: 1.234,56 (dot thousands, comma decimal)
format_amount(Decimal('1234.56'), 'EUR')
```

### Parsing Formatted Amounts

```python
from django_iyzico.currency import parse_amount

# Parse USD format
amount = parse_amount('$1,234.56', 'USD')
print(amount)  # Decimal('1234.56')

# Parse TRY format
amount = parse_amount('₺1.234,56', 'TRY')
print(amount)  # Decimal('1234.56')
```

---

## Currency Conversion

### Basic Conversion

```python
from decimal import Decimal
from django_iyzico.currency import CurrencyConverter

converter = CurrencyConverter()

# Convert USD to EUR
eur = converter.convert(
    Decimal('100.00'),
    'USD',
    'EUR'
)
print(f"100 USD = {eur} EUR")

# Convert TRY to USD
usd = converter.convert(
    Decimal('3000.00'),
    'TRY',
    'USD'
)
print(f"3000 TRY = {usd} USD")
```

### Getting Exchange Rates

```python
converter = CurrencyConverter()

# Get rate between currencies
rate = converter.get_rate('USD', 'TRY')
print(f"1 USD = {rate} TRY")

# Calculate manually
amount_try = Decimal('100.00') * rate
```

### Custom Exchange Rates

```python
from decimal import Decimal

# Use custom rates (e.g., from live API)
custom_rates = {
    'TRY': Decimal('1.00'),
    'USD': Decimal('0.034'),
    'EUR': Decimal('0.031'),
    'GBP': Decimal('0.027'),
}

converter = CurrencyConverter(rates=custom_rates)

# Now uses custom rates
result = converter.convert(Decimal('100.00'), 'TRY', 'USD')
```

### Updating Rates

```python
converter = CurrencyConverter()

# Update specific rates
converter.update_rates({
    'USD': Decimal('0.035'),
    'EUR': Decimal('0.032'),
})

# Rates are updated for future conversions
```

---

## Model Methods

### Formatting Methods

```python
payment = Payment.objects.get(id=1)

# Get formatted amount with symbol
formatted = payment.get_formatted_amount()
print(formatted)  # $1,234.56

# Get formatted amount without symbol
formatted = payment.get_formatted_amount(show_symbol=False)
print(formatted)  # 1,234.56

# Get formatted amount with code
formatted = payment.get_formatted_amount(show_code=True)
print(formatted)  # $1,234.56 USD

# Get formatted paid amount
paid = payment.get_formatted_paid_amount()
```

### Currency Info Methods

```python
payment = Payment.objects.get(id=1)

# Get currency symbol
symbol = payment.get_currency_symbol()
print(symbol)  # $

# Get currency name
name = payment.get_currency_name()
print(name)  # US Dollar

# Get complete currency info
info = payment.get_currency_info()
print(info['symbol'])  # $
print(info['name'])  # US Dollar
```

### Conversion Methods

```python
payment = Payment.objects.get(id=1)

# Convert to another currency
eur_amount = payment.convert_to_currency('EUR')
print(f"Amount in EUR: {eur_amount}")

# Get amount in TRY (base currency)
try_amount = payment.get_amount_in_try()
print(f"Amount in TRY: {try_amount}")

# Check currency
if payment.is_currency('USD'):
    print("Payment is in USD")
```

---

## Admin Interface

### Enhanced Display

The admin interface automatically displays currency information with symbols:

```python
from django.contrib import admin
from django_iyzico.admin import IyzicoPaymentAdminMixin
from myapp.models import Order

@admin.register(Order)
class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
    # Includes currency-enhanced display methods
    pass
```

### Currency Display Features

- ✅ Amount displayed with currency symbols ($, €, £, ₺)
- ✅ Currency column shows symbol and name
- ✅ Proper number formatting per currency locale
- ✅ Multi-currency filtering

### Custom Currency Display

```python
class CustomOrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):

    def get_amount_with_conversion(self, obj):
        """Show amount with TRY conversion."""
        formatted = obj.get_formatted_amount()

        if not obj.is_currency('TRY'):
            try_amount = obj.get_amount_in_try()
            return format_html(
                '{} <span style="color: #666;">(~₺{})</span>',
                formatted,
                try_amount
            )

        return formatted

    get_amount_with_conversion.short_description = 'Amount'
```

---

## Best Practices

### 1. Always Validate Currency Codes

```python
# ✅ Good
from django_iyzico.currency import validate_currency

try:
    currency = validate_currency(user_input)
    process_payment(currency)
except ValueError as e:
    return error_response(str(e))

# ❌ Bad
currency = user_input.upper()  # No validation
process_payment(currency)
```

### 2. Use Model Methods for Display

```python
# ✅ Good
formatted = payment.get_formatted_amount(show_symbol=True)

# ❌ Bad
formatted = f"{payment.amount} {payment.currency}"
```

### 3. Store Exchange Rates

```python
# ✅ Good - Store rate used at time of transaction
payment.exchange_rate_used = converter.get_rate('USD', 'TRY')
payment.save()

# ❌ Bad - Rely on current rates for historical data
```

### 4. Update Exchange Rates Regularly

```python
# Good practice: Update rates from live API
def update_exchange_rates():
    """Update rates from external API."""
    import requests

    response = requests.get('https://api.exchangerate.host/latest?base=TRY')
    rates = response.json()['rates']

    converter = CurrencyConverter()
    converter.update_rates({
        'USD': Decimal(str(rates['USD'])),
        'EUR': Decimal(str(rates['EUR'])),
        'GBP': Decimal(str(rates['GBP'])),
    })

    return converter
```

### 5. Handle Currency Mismatch

```python
# ✅ Good - Check currency before operations
if payment1.currency != payment2.currency:
    # Convert to common currency
    payment2_converted = payment2.convert_to_currency(payment1.currency)
    total = payment1.amount + payment2_converted
else:
    total = payment1.amount + payment2.amount

# ❌ Bad - Add without checking
total = payment1.amount + payment2.amount  # May be different currencies!
```

---

## Examples

### Example 1: Multi-Currency Payment Processing

```python
from decimal import Decimal
from django_iyzico.client import IyzicoClient
from django_iyzico.currency import validate_currency, format_amount

def process_multi_currency_payment(amount, currency, card_info):
    """Process payment in any supported currency."""
    # Validate currency
    currency = validate_currency(currency)

    # Create payment
    client = IyzicoClient()
    result = client.create_payment({
        'price': str(amount),
        'paidPrice': str(amount),
        'currency': currency,
        # ... other fields
    })

    if result.is_successful():
        # Display formatted amount
        formatted = format_amount(amount, currency, show_symbol=True)
        print(f"Payment successful: {formatted}")

    return result
```

### Example 2: Currency Conversion Report

```python
from django_iyzico.currency import CurrencyConverter, format_amount

def generate_revenue_report(payments):
    """Generate multi-currency revenue report."""
    converter = CurrencyConverter()

    # Group by currency
    by_currency = {}
    for payment in payments:
        curr = payment.currency
        if curr not in by_currency:
            by_currency[curr] = Decimal('0.00')
        by_currency[curr] += payment.amount

    # Display each currency
    print("Revenue by Currency:")
    print("-" * 50)

    total_try = Decimal('0.00')
    for currency, amount in by_currency.items():
        formatted = format_amount(amount, currency, show_symbol=True)
        print(f"{currency}: {formatted}")

        # Convert to TRY for total
        try_amount = converter.convert(amount, currency, 'TRY')
        total_try += try_amount

    print("-" * 50)
    print(f"Total (TRY): {format_amount(total_try, 'TRY', show_symbol=True)}")
```

### Example 3: Currency Selector Widget

```python
from django import forms
from django_iyzico.currency import Currency

class PaymentForm(forms.Form):
    """Payment form with currency selection."""

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    currency = forms.ChoiceField(
        choices=Currency.choices(),
        initial=Currency.default(),
    )

    def get_formatted_amount(self):
        """Get formatted amount with currency."""
        from django_iyzico.currency import format_amount

        amount = self.cleaned_data['amount']
        currency = self.cleaned_data['currency']

        return format_amount(amount, currency, show_symbol=True)
```

### Example 4: Price Comparison

```python
from django_iyzico.currency import compare_amounts

def show_best_price(product_prices):
    """Show best price across currencies."""
    if not product_prices:
        return None

    # Sort by value (converted to common currency)
    best = min(product_prices, key=lambda p: (
        p.amount if p.currency == 'TRY'
        else p.convert_to_currency('TRY')
    ))

    formatted = best.get_formatted_amount(show_symbol=True, show_code=True)
    print(f"Best price: {formatted}")

    return best
```

---

## Integration with External APIs

### Fetching Live Exchange Rates

```python
import requests
from decimal import Decimal
from django_iyzico.currency import CurrencyConverter

def get_live_converter():
    """Get converter with live exchange rates."""
    # Using exchangerate.host API (free)
    response = requests.get(
        'https://api.exchangerate.host/latest',
        params={'base': 'TRY'}
    )

    data = response.json()
    rates = data['rates']

    # Create converter with live rates
    converter = CurrencyConverter(rates={
        'TRY': Decimal('1.00'),
        'USD': Decimal(str(rates['USD'])),
        'EUR': Decimal(str(rates['EUR'])),
        'GBP': Decimal(str(rates['GBP'])),
    })

    return converter
```

---

## Troubleshooting

### Common Issues

#### 1. "Unsupported currency" Error

**Problem:** Trying to use unsupported currency

**Solution:**
```python
from django_iyzico.currency import Currency

# Check supported currencies
supported = Currency.values()
print(f"Supported: {supported}")

# Only use supported currencies
if currency_code in supported:
    process_payment(currency_code)
```

#### 2. Formatting Doesn't Match Locale

**Problem:** Numbers formatted incorrectly

**Solution:** Use built-in formatting functions
```python
# ✅ Correct
from django_iyzico.currency import format_amount
formatted = format_amount(amount, currency)

# ❌ Wrong
formatted = f"{amount} {currency}"
```

#### 3. Conversion Rates Outdated

**Problem:** Using default rates

**Solution:** Update rates regularly
```python
# Update rates from live API
converter = get_live_converter()

# Or set custom rates
converter.update_rates({
    'USD': Decimal('0.034'),
    # ... other rates
})
```

---

## Additional Resources

- [Currency Module API Reference](../django_iyzico/currency.py)
- [Model Currency Methods](../django_iyzico/models.py)
- [Currency Tests](../tests/test_currency.py)
- [Iyzico Multi-Currency Documentation](https://dev.iyzipay.com/)

---

**Last Updated:** December 2025
**Version:** 0.2.0
