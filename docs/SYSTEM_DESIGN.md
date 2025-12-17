# System Design Document
## django-iyzico

**Document Version:** 1.0
**Date:** 2025-12-15
**Author:** Emre Aladag
**Status:** Draft

---

## 1. Introduction

### 1.1 Purpose
This document describes the technical architecture and design of `django-iyzico`, detailing how the functional requirements will be implemented.

### 1.2 Scope
This document covers:
- System architecture
- Component design
- Data models
- API design
- Security architecture
- Integration patterns
- Deployment considerations

### 1.3 References
- [Business Requirements Document (BRD)](BRD.md)
- [Functional Requirements Document (FRD)](FRD.md)
- [Iyzico API Documentation](https://docs.iyzico.com)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Django Application                     │
│                                                          │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ User Views   │────────▶│ Django Admin │             │
│  └──────────────┘         └──────────────┘             │
│         │                         │                     │
│         ▼                         ▼                     │
│  ┌────────────────────────────────────────┐            │
│  │        django-iyzico Package           │            │
│  │                                         │            │
│  │  ┌──────────┐  ┌──────────┐           │            │
│  │  │ Client   │  │ Models   │           │            │
│  │  └──────────┘  └──────────┘           │            │
│  │  ┌──────────┐  ┌──────────┐           │            │
│  │  │ Views    │  │ Signals  │           │            │
│  │  └──────────┘  └──────────┘           │            │
│  │  ┌──────────┐  ┌──────────┐           │            │
│  │  │ Utils    │  │ Admin    │           │            │
│  │  └──────────┘  └──────────┘           │            │
│  └────────────────────────────────────────┘            │
│         │                         ▲                     │
│         │                         │                     │
└─────────┼─────────────────────────┼─────────────────────┘
          │                         │
          ▼                         │
  ┌───────────────┐         ┌──────────────┐
  │ Official      │         │   Iyzico     │
  │ iyzipay SDK   │◀───────▶│   API        │
  └───────────────┘         │              │
                            │ (Webhooks)   │
                            └──────────────┘
```

### 2.2 Component Breakdown

#### 2.2.1 Core Components

**IyzicoClient**
- Wraps official iyzipay SDK
- Provides Django-friendly interface
- Handles configuration from Django settings
- Implements retry logic
- Manages error translation

**Models**
- AbstractIyzicoPayment (base model)
- Transaction tracking
- Status management
- Audit trail

**Views**
- Webhook handler
- 3D Secure callback
- Optional API endpoints

**Signals**
- Payment lifecycle events
- Webhook events
- 3D Secure events

**Admin**
- Transaction list/detail views
- Refund actions
- Filtering and search

**Utils**
- Card data masking
- Amount validation
- Data transformation
- Helper functions

---

## 3. Detailed Component Design

### 3.1 IyzicoClient Architecture

```python
class IyzicoClient:
    """
    Main client for interacting with Iyzico API.

    Wraps official iyzipay SDK with Django-specific features.
    """

    def __init__(self, settings: IyzicoSettings = None):
        """Initialize with Django settings or custom settings."""

    def create_payment(
        self,
        order_data: dict,
        payment_card: dict,
        buyer: dict,
        billing_address: dict,
        shipping_address: dict = None,
    ) -> PaymentResponse:
        """
        Create a payment request.

        Returns:
            PaymentResponse with status, payment_id, etc.
        """

    def create_3ds_payment(self, ...):
        """Initialize 3D Secure payment flow."""

    def complete_3ds_payment(self, token: str):
        """Complete 3D Secure payment after authentication."""

    def refund_payment(self, payment_id: str, amount: Decimal):
        """Initiate refund for a payment."""

    def get_payment(self, payment_id: str):
        """Retrieve payment details from Iyzico."""
```

**Design Decisions:**
- **Wraps SDK:** Doesn't reimplement API, uses official SDK
- **Stateless:** No instance state, all data passed as parameters
- **Type-safe:** Uses type hints for all parameters
- **Testable:** Easy to mock for testing

---

### 3.2 Data Model Design

#### 3.2.1 AbstractIyzicoPayment Model

```python
from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentStatus(models.TextChoices):
    """Payment status choices."""
    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    REFUND_PENDING = "refund_pending", _("Refund Pending")
    REFUNDED = "refunded", _("Refunded")
    CANCELLED = "cancelled", _("Cancelled")


class AbstractIyzicoPayment(models.Model):
    """
    Abstract base model for Iyzico payments.

    Inherit from this in your Django models:

    class Order(AbstractIyzicoPayment):
        # Your order fields
        pass
    """

    # Iyzico IDs
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Payment ID"),
        help_text=_("Iyzico payment ID"),
    )
    conversation_id = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Conversation ID"),
        help_text=_("Unique conversation ID for this payment"),
    )

    # Payment details
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount"),
    )
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Paid Amount"),
        help_text=_("Actual amount paid (may differ due to installments)"),
    )
    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name=_("Currency"),
    )
    locale = models.CharField(
        max_length=5,
        default="tr",
        verbose_name=_("Locale"),
    )

    # Card information (non-sensitive only)
    card_last_four_digits = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        verbose_name=_("Card Last 4 Digits"),
    )
    card_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Type"),
        help_text=_("E.g., CREDIT_CARD, DEBIT_CARD"),
    )
    card_association = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Association"),
        help_text=_("E.g., VISA, MASTER_CARD"),
    )
    card_family = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Family"),
        help_text=_("E.g., Bonus, Axess"),
    )
    installment = models.IntegerField(
        default=1,
        verbose_name=_("Installment"),
    )

    # Buyer information
    buyer_email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Buyer Email"),
    )
    buyer_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Buyer Name"),
    )

    # Error handling
    error_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Error Code"),
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error Message"),
    )

    # Audit
    raw_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Raw Response"),
        help_text=_("Complete response from Iyzico (for debugging)"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]
        verbose_name = _("Iyzico Payment")
        verbose_name_plural = _("Iyzico Payments")

    def __str__(self):
        return f"Payment {self.payment_id} - {self.status}"

    def is_successful(self):
        """Check if payment is successful."""
        return self.status == PaymentStatus.SUCCESS

    def can_be_refunded(self):
        """Check if payment can be refunded."""
        return self.status == PaymentStatus.SUCCESS

    def mask_and_store_card_data(self, payment_response: dict):
        """Extract and store safe card data from payment response."""
        # Implementation in utils.py
```

**Design Decisions:**
- **Abstract Model:** Users extend it, don't modify it
- **JSONField for raw_response:** Full audit trail
- **Status Enum:** Type-safe status handling
- **No Full Card Storage:** PCI DSS compliance
- **Timestamps:** Automatic tracking
- **Helper Methods:** Convenience methods for common checks

#### 3.2.2 Database Schema

```sql
-- Example implementation (user extends AbstractIyzicoPayment)
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,

    -- Iyzico fields (from AbstractIyzicoPayment)
    payment_id VARCHAR(255) UNIQUE,
    conversation_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    amount DECIMAL(10, 2) NOT NULL,
    paid_amount DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'TRY',
    locale VARCHAR(5) DEFAULT 'tr',
    card_last_four_digits VARCHAR(4),
    card_type VARCHAR(50),
    card_association VARCHAR(50),
    card_family VARCHAR(50),
    installment INTEGER DEFAULT 1,
    buyer_email VARCHAR(255),
    buyer_name VARCHAR(255),
    error_code VARCHAR(50),
    error_message TEXT,
    raw_response JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- User's custom fields
    user_id BIGINT REFERENCES users(id),
    product_id BIGINT REFERENCES products(id),
    quantity INTEGER,
    -- ... other order fields
);

-- Indexes for performance
CREATE INDEX idx_orders_payment_id ON orders(payment_id);
CREATE INDEX idx_orders_conversation_id ON orders(conversation_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at);
CREATE INDEX idx_orders_buyer_email ON orders(buyer_email);
```

---

### 3.3 View Architecture

#### 3.3.1 Webhook View

```python
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook_view(request):
    """
    Handle webhooks from Iyzico.

    POST /iyzico/webhook/

    Security:
    - CSRF exempt (external webhook)
    - Optional IP whitelist
    - Optional signature verification
    """
    try:
        # Parse webhook data
        webhook_data = json.loads(request.body)

        # Verify webhook (if configured)
        if settings.IYZICO_VERIFY_WEBHOOK:
            verify_webhook_signature(request, webhook_data)

        # Extract event type and payment ID
        event_type = webhook_data.get("iyziEventType")
        payment_id = webhook_data.get("paymentId")

        # Find transaction
        transaction = find_transaction(payment_id)

        # Process webhook
        process_webhook(event_type, webhook_data, transaction)

        # Trigger signal
        webhook_received.send(
            sender=None,
            event_type=event_type,
            data=webhook_data,
            transaction=transaction,
        )

        # Return success (Iyzico expects 200 OK)
        return JsonResponse({"status": "success"}, status=200)

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        # Still return 200 to avoid webhook retry spam
        return JsonResponse({"status": "error"}, status=200)
```

**Design Decisions:**
- **CSRF Exempt:** Required for external webhooks
- **Always 200 OK:** Even on error (avoids retry spam)
- **Async Processing:** Consider Celery for heavy processing
- **Idempotent:** Handle duplicate webhooks gracefully
- **Logged:** All webhooks logged for audit

#### 3.3.2 3D Secure Callback View

```python
from django.shortcuts import redirect
from django.urls import reverse


def threeds_callback_view(request):
    """
    Handle 3D Secure callback from Iyzico.

    GET /iyzico/callback/?token=xxx

    Flow:
    1. Receive callback with token
    2. Complete payment with Iyzico
    3. Update transaction status
    4. Redirect to success/failure page
    """
    token = request.GET.get("token")

    if not token:
        return redirect("payment_error")

    try:
        # Complete 3DS payment
        client = IyzicoClient()
        response = client.complete_3ds_payment(token)

        # Update transaction
        transaction = update_transaction_from_response(response)

        # Trigger signal
        if response.is_successful():
            threeds_completed.send(
                sender=transaction.__class__,
                instance=transaction,
                response=response,
            )
            return redirect("payment_success", payment_id=transaction.payment_id)
        else:
            threeds_failed.send(
                sender=transaction.__class__,
                instance=transaction,
                error=response.error_message,
            )
            return redirect("payment_error")

    except Exception as e:
        logger.error(f"3DS callback failed: {e}", exc_info=True)
        return redirect("payment_error")
```

---

### 3.4 Signal Architecture

#### 3.4.1 Signal Definitions

```python
# django_iyzico/signals.py

from django.dispatch import Signal

# Payment lifecycle signals
payment_initiated = Signal()  # When payment starts
payment_completed = Signal()  # When payment succeeds
payment_failed = Signal()     # When payment fails
payment_refunded = Signal()   # When refund processed

# 3D Secure signals
threeds_initiated = Signal()
threeds_completed = Signal()
threeds_failed = Signal()

# Webhook signals
webhook_received = Signal()
```

#### 3.4.2 Signal Usage Example

```python
# In user's Django project
from django.dispatch import receiver
from django_iyzico.signals import payment_completed

@receiver(payment_completed)
def handle_payment_completed(sender, instance, response, **kwargs):
    """
    Handle successful payment.

    Args:
        sender: Transaction model class
        instance: Transaction instance
        response: Iyzico response dict
        **kwargs: Additional context
    """
    # Update order status
    instance.status = "paid"
    instance.save()

    # Send confirmation email
    send_order_confirmation_email(instance)

    # Add quota (if applicable)
    add_quota_to_user(instance.user, instance.quantity)

    # Log to analytics
    track_conversion(instance)
```

---

### 3.5 Admin Interface Design

#### 3.5.1 Admin Class

```python
from django.contrib import admin
from django.utils.html import format_html


class IyzicoPaymentAdminMixin:
    """
    Mixin for Django admin to display Iyzico payment data.

    Usage:
    class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
        pass
    """

    list_display = [
        "payment_id",
        "status_badge",
        "amount_display",
        "buyer_email",
        "card_last_four_digits",
        "created_at",
    ]

    list_filter = [
        "status",
        "currency",
        "card_association",
        "created_at",
    ]

    search_fields = [
        "payment_id",
        "conversation_id",
        "buyer_email",
        "buyer_name",
    ]

    readonly_fields = [
        "payment_id",
        "conversation_id",
        "raw_response_display",
        "created_at",
        "updated_at",
    ]

    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            "success": "green",
            "pending": "orange",
            "processing": "blue",
            "failed": "red",
            "refunded": "gray",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def amount_display(self, obj):
        """Display amount with currency."""
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = "Amount"

    def raw_response_display(self, obj):
        """Display raw response as formatted JSON."""
        import json
        if obj.raw_response:
            formatted = json.dumps(obj.raw_response, indent=2)
            return format_html("<pre>{}</pre>", formatted)
        return "-"
    raw_response_display.short_description = "Raw Response"
```

---

### 3.6 Security Architecture

#### 3.6.1 Card Data Security

**PCI DSS Compliance:**
```python
def mask_card_data(payment_details: dict) -> dict:
    """
    Remove sensitive card data before storage.

    Kept:
    - Last 4 digits
    - Card type/family/association
    - Cardholder name

    Removed:
    - Full card number
    - CVC/CVV
    - Expiry date (full)
    """
    safe_data = payment_details.copy()

    if "card" in safe_data:
        card = safe_data["card"]
        card_number = card.get("cardNumber", "")

        # Keep only last 4 digits
        safe_data["card"] = {
            "lastFourDigits": card_number[-4:] if len(card_number) >= 4 else "",
            "cardHolderName": card.get("cardHolderName", ""),
            # CVC removed
            # Full expiry removed
        }

    return safe_data
```

#### 3.6.2 Webhook Security

**Signature Verification:**
```python
def verify_webhook_signature(request, webhook_data):
    """
    Verify webhook signature (if Iyzico provides it).

    Note: As of 2025, Iyzico may not provide webhook signatures.
    This is a placeholder for future implementation.
    """
    # TODO: Implement when Iyzico adds signature support
    pass
```

**IP Whitelist:**
```python
IYZICO_WEBHOOK_ALLOWED_IPS = [
    "185.84.184.0/24",  # Iyzico IP range (example)
]

def verify_webhook_ip(request):
    """Verify webhook comes from Iyzico IP range."""
    client_ip = get_client_ip(request)

    for ip_range in settings.IYZICO_WEBHOOK_ALLOWED_IPS:
        if ip_in_range(client_ip, ip_range):
            return True

    raise PermissionDenied("Invalid webhook source IP")
```

---

### 3.7 Error Handling Strategy

#### 3.7.1 Exception Hierarchy

```
IyzicoError (base)
├── PaymentError
│   ├── CardError
│   └── ThreeDSecureError
├── ValidationError
├── ConfigurationError
└── WebhookError
```

#### 3.7.2 Error Response Format

```python
class IyzicoErrorResponse:
    """Standardized error response."""

    def __init__(self, error_code: str, error_message: str, error_group: str = None):
        self.error_code = error_code
        self.error_message = error_message
        self.error_group = error_group
        self.success = False

    def to_dict(self):
        return {
            "success": False,
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "errorGroup": self.error_group,
        }
```

---

### 3.8 Performance Considerations

#### 3.8.1 Database Optimization

- Index on `payment_id`, `conversation_id`, `status`
- Index on `created_at` for date range queries
- JSONField for `raw_response` (queryable in PostgreSQL)

#### 3.8.2 Caching Strategy

```python
# Cache Iyzico settings (they rarely change)
from django.core.cache import cache

def get_iyzico_options():
    """Get Iyzico options with caching."""
    cache_key = "iyzico_options"
    options = cache.get(cache_key)

    if options is None:
        options = {
            "api_key": settings.IYZICO_API_KEY,
            "secret_key": settings.IYZICO_SECRET_KEY,
            "base_url": settings.IYZICO_BASE_URL,
        }
        cache.set(cache_key, options, timeout=3600)  # 1 hour

    return options
```

#### 3.8.3 Async Processing

```python
# Use Celery for heavy operations
from celery import shared_task

@shared_task
def process_webhook_async(webhook_data):
    """Process webhook asynchronously."""
    # Heavy processing here
    pass
```

---

### 3.9 Testing Strategy

#### 3.9.1 Test Structure

```
tests/
├── test_client.py         # IyzicoClient tests
├── test_models.py         # Model tests
├── test_views.py          # View tests
├── test_signals.py        # Signal tests
├── test_admin.py          # Admin interface tests
├── test_utils.py          # Utility function tests
├── test_integration.py    # End-to-end tests
└── fixtures/
    ├── payment_responses.json
    └── webhook_payloads.json
```

#### 3.9.2 Mock Strategy

```python
# Use responses library to mock Iyzico API
import responses

@responses.activate
def test_create_payment():
    """Test payment creation."""
    # Mock Iyzico API response
    responses.add(
        responses.POST,
        "https://sandbox-api.iyzipay.com/payment/auth",
        json={"status": "success", "paymentId": "12345"},
        status=200,
    )

    # Test client
    client = IyzicoClient()
    response = client.create_payment(...)

    assert response.is_successful()
    assert response.payment_id == "12345"
```

---

### 3.10 Deployment Architecture

#### 3.10.1 Environment Configuration

```python
# Development
IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
IYZICO_API_KEY = "sandbox-api-key"
IYZICO_SECRET_KEY = "sandbox-secret-key"

# Production
IYZICO_BASE_URL = "https://api.iyzipay.com"
IYZICO_API_KEY = os.getenv("IYZICO_API_KEY")
IYZICO_SECRET_KEY = os.getenv("IYZICO_SECRET_KEY")
```

#### 3.10.2 Monitoring

```python
# Log all payment operations
import logging

logger = logging.getLogger("django_iyzico")

# In payment processing:
logger.info(f"Payment initiated: {conversation_id}")
logger.info(f"Payment completed: {payment_id}")
logger.error(f"Payment failed: {error_message}")
```

---

## 4. API Reference

### 4.1 IyzicoClient API

```python
# Create client
from django_iyzico import IyzicoClient

client = IyzicoClient()

# Create payment
response = client.create_payment(
    order_data={
        "price": "100.00",
        "paidPrice": "100.00",
        "currency": "TRY",
        "basketId": "B12345",
    },
    payment_card={
        "cardHolderName": "John Doe",
        "cardNumber": "5528790000000008",
        "expireMonth": "12",
        "expireYear": "2030",
        "cvc": "123",
    },
    buyer={
        "id": "BY123",
        "name": "John",
        "surname": "Doe",
        "email": "john@example.com",
        "identityNumber": "11111111111",
        "registrationAddress": "Address",
        "city": "Istanbul",
        "country": "Turkey",
        "zipCode": "34000",
    },
    billing_address={...},
)

# Check response
if response.is_successful():
    payment_id = response.payment_id
    # Handle success
else:
    error_message = response.error_message
    # Handle error
```

---

## 5. Approval

**Prepared by:** Emre Aladag
**Date:** 2025-12-15
**Version:** 1.0

**Status:** ⏳ Draft - Ready for Review

---

## Next Steps

1. Review BRD, FRD, and System Design
2. Approve architecture
3. Begin Phase 1 implementation
4. Iterate based on feedback
