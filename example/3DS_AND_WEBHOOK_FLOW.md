# 3D Secure and Webhook Flow Guide

Complete guide to understanding the 3D Secure payment flow and webhook integration with django-iyzico.

## Table of Contents

1. [Flow Overview](#flow-overview)
2. [3D Secure Flow](#3d-secure-flow)
3. [Webhook Integration](#webhook-integration)
4. [Signal Handlers](#signal-handlers)
5. [Configuration](#configuration)
6. [Testing](#testing)

---

## Flow Overview

django-iyzico supports two payment flows:

### 1. Direct Payment (No 3DS)
```
User -> Your Site -> Iyzico API -> Response -> Your Site
```
- Simple, immediate response
- No user redirection
- Lower security (may have restrictions)

### 2. 3D Secure Payment (With Redirect)
```
User -> Your Site -> Iyzico API (Initialize) ->
  -> Iyzico 3DS Page (User Authenticates) ->
  -> Callback URL (Your Site) ->
  -> Iyzico API (Complete) ->
  -> Success/Error Page (Your Site)

(In parallel: Webhook notification arrives)
```
- Higher security
- User authenticates on Iyzico's page
- Required for many cards
- Webhook provides final confirmation

---

## 3D Secure Flow

### Step-by-Step Process

#### Step 1: Initialize Payment
**Your Code:** `views_3ds.py:checkout_3ds_view()`

```python
from django_iyzico.client import IyzicoClient

client = IyzicoClient()

# Initialize 3DS payment
response = client.create_3ds_payment(
    order_data={
        'conversationId': 'ORDER-123',
        'price': '100.00',
        'paidPrice': '100.00',
        'currency': 'TRY',
        'basketId': 'BASKET-123',
        'installment': 1,
    },
    payment_card={
        'cardHolderName': 'John Doe',
        'cardNumber': '5528790000000008',
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
    },
    buyer={...},
    billing_address={...},
    # callback_url is optional - defaults to /payments/callback/
)

# Get 3DS HTML content
if response.is_successful():
    html = response.three_ds_html_content
    # This HTML contains a form that auto-submits
    # and redirects user to Iyzico's 3DS page
    return HttpResponse(html)
```

**What Happens:**
- Your site sends payment details to Iyzico
- Iyzico returns HTML with a hidden form
- Form auto-submits and redirects user to Iyzico
- User sees Iyzico's authentication page

#### Step 2: User Authentication
**User Experience:**
- User is on Iyzico's secure page (iyzico.com domain)
- Enters SMS code / authenticates with their bank
- Bank verifies the transaction
- User does NOT see your site during this step

#### Step 3: Callback
**Built-in:** `/payments/callback/` (django-iyzico handles this automatically)

**What Happens:**
1. Iyzico redirects user back to your callback URL
2. URL includes `token` parameter: `/payments/callback/?token=abc123...`
3. django-iyzico's callback handler:
   - Extracts token
   - Calls `client.complete_3ds_payment(token)`
   - Triggers `threeds_completed` or `threeds_failed` signal
   - Redirects to success/error URL (from session or settings)

**Your Signal Handler:** `signals.py:on_threeds_completed()`

```python
@receiver(threeds_completed)
def on_threeds_completed(sender, payment_id, conversation_id, response, request, **kwargs):
    # Find and update order
    order = Order.objects.get(conversation_id=conversation_id)
    order.payment_id = payment_id
    order.payment_status = 'SUCCESS'
    order.save()

    # Reduce stock, send email, etc.
```

#### Step 4: Success Page
**Your Code:** `views_3ds.py:payment_success_3ds_view()`

User is redirected to your success page (configured via `request.session['iyzico_success_url']`)

```python
def payment_success_3ds_view(request, order_id):
    order = Order.objects.get(id=order_id)
    # Order is already updated by signal handler
    return render(request, 'payment_success.html', {'order': order})
```

#### Step 5: Webhook (Asynchronous)
**Built-in:** `/payments/webhook/` (django-iyzico handles this automatically)

Iyzico sends webhook notification (may arrive before or after user redirect):

```json
POST /payments/webhook/
{
    "iyziEventType": "PAYMENT_AUTH",
    "paymentId": "12345",
    "conversationId": "ORDER-123",
    "status": "success",
    ...
}
```

**Your Signal Handler:** `signals.py:on_webhook_received()`

```python
@receiver(webhook_received)
def on_webhook_received(sender, event_type, payment_id, conversation_id, data, request, **kwargs):
    if event_type == 'PAYMENT_AUTH':
        # Final confirmation
        order = Order.objects.get(conversation_id=conversation_id)
        order.payment_status = 'SUCCESS'
        order.save()
```

---

## Webhook Integration

### Configuration

#### 1. Settings Configuration

```python
# settings.py

# Webhook secret for signature validation (HIGHLY RECOMMENDED)
IYZICO_WEBHOOK_SECRET = 'your-webhook-secret-from-iyzico'

# IP whitelist for security (OPTIONAL)
IYZICO_WEBHOOK_ALLOWED_IPS = [
    '1.2.3.4',           # Single IP
    '5.6.7.0/24',        # CIDR block
]
```

#### 2. Iyzico Merchant Panel Configuration

1. Log in to Iyzico merchant panel
2. Go to **Settings** > **Webhooks**
3. Set webhook URL: `https://yourdomain.com/payments/webhook/`
4. Set webhook secret (copy to Django settings)
5. Enable webhook notifications

#### 3. URL Configuration

**Already configured in `ecommerce_site/urls.py`:**

```python
urlpatterns = [
    # This includes both callback and webhook URLs:
    # - /payments/callback/ (for 3DS redirects)
    # - /payments/webhook/ (for webhook notifications)
    path('payments/', include('django_iyzico.urls')),
]
```

### Webhook Security

django-iyzico webhook handler automatically provides:

1. **Signature Validation**
   - HMAC-SHA256 signature verification
   - Prevents spoofed webhooks
   - Enabled when `IYZICO_WEBHOOK_SECRET` is set

2. **IP Whitelisting**
   - Only accepts webhooks from Iyzico IPs
   - Supports CIDR notation
   - Enabled when `IYZICO_WEBHOOK_ALLOWED_IPS` is set

3. **Constant-Time Comparison**
   - Prevents timing attacks
   - Built-in to signature verification

### Webhook Event Types

Common webhook events:

| Event Type | Description | When Triggered |
|-----------|-------------|----------------|
| `PAYMENT_AUTH` | Payment authorized | After successful payment |
| `PAYMENT_FAIL` | Payment failed | After failed payment |
| `REFUND_SUCCESS` | Refund processed | After successful refund |
| `REFUND_FAIL` | Refund failed | After failed refund |
| `CHARGEBACK` | Chargeback received | When customer disputes charge |
| `SETTLEMENT` | Funds settled | When funds transferred to merchant |

---

## Signal Handlers

django-iyzico provides 5 key signals for payments:

### 1. `threeds_completed`
**When:** After successful 3DS authentication and payment
**Use For:** Update order, reduce stock, send confirmation

```python
@receiver(threeds_completed)
def on_threeds_completed(sender, payment_id, conversation_id, response, request, **kwargs):
    # Update order immediately
    order = Order.objects.get(conversation_id=conversation_id)
    order.payment_id = payment_id
    order.payment_status = 'SUCCESS'
    order.save()
```

### 2. `threeds_failed`
**When:** When 3DS authentication or payment fails
**Use For:** Update order, send failure notification

```python
@receiver(threeds_failed)
def on_threeds_failed(sender, conversation_id, error_code, error_message, request, **kwargs):
    order = Order.objects.get(conversation_id=conversation_id)
    order.payment_status = 'FAILED'
    order.error_message = error_message
    order.save()
```

### 3. `webhook_received`
**When:** When webhook notification arrives
**Use For:** Final confirmation, reconciliation, delayed events

```python
@receiver(webhook_received)
def on_webhook_received(sender, event_type, payment_id, conversation_id, data, request, **kwargs):
    # Handle different event types
    if event_type == 'PAYMENT_AUTH':
        # Payment confirmed
        pass
    elif event_type == 'CHARGEBACK':
        # Handle chargeback
        pass
```

### 4. `payment_completed` (Direct payments only)
**When:** After successful direct payment (no 3DS)
**Use For:** Same as `threeds_completed` but for direct payments

### 5. `payment_failed` (Direct payments only)
**When:** When direct payment fails
**Use For:** Same as `threeds_failed` but for direct payments

---

## Configuration

### Required URLs

Configured in `ecommerce_site/urls.py`:

```python
urlpatterns = [
    # Includes:
    # - /payments/callback/ (3DS callback)
    # - /payments/webhook/ (webhook notifications)
    path('payments/', include('django_iyzico.urls')),
]
```

### Success/Error Redirect URLs

**Method 1: Session (Recommended)**

```python
# Before initiating 3DS payment
request.session['iyzico_success_url'] = '/shop/orders/123/success/'
request.session['iyzico_error_url'] = '/shop/checkout/error/'
```

**Method 2: Django Settings**

```python
# settings.py
IYZICO_SUCCESS_URL = '/payment/success/'
IYZICO_ERROR_URL = '/payment/error/'
```

### Webhook Configuration

```python
# settings.py

# Required for production
IYZICO_WEBHOOK_SECRET = config('IYZICO_WEBHOOK_SECRET')

# Recommended for production
IYZICO_WEBHOOK_ALLOWED_IPS = [
    '1.2.3.4',  # Iyzico's webhook server IPs
]
```

---

## Testing

### Testing 3D Secure Flow

**1. Start Development Server**
```bash
python manage.py runserver
```

**2. For Local Testing with Webhooks**
Use ngrok to expose your local server:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from ngrok.com

# Start ngrok
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

**3. Configure Iyzico Merchant Panel**
- Callback URL: `https://abc123.ngrok.io/payments/callback/`
- Webhook URL: `https://abc123.ngrok.io/payments/webhook/`

**4. Initiate Test Payment**
```bash
# Visit checkout page
http://localhost:8000/shop/checkout/3ds/

# Use test card
Card: 5528 7900 0000 0008
Holder: John Doe
Expiry: 12/2030
CVC: 123
```

**5. Authenticate on Iyzico**
- You'll be redirected to Iyzico's page
- Enter SMS code: **123456** (sandbox)
- You'll be redirected back to your site

**6. Check Logs**
```python
# Django logs
INFO: 3DS payment completed: payment_id=xxx, conversation_id=ORDER-123
INFO: Order 1 updated after 3DS completion
INFO: Webhook received: event_type=PAYMENT_AUTH, payment_id=xxx
```

### Testing Webhooks Manually

```bash
# Send test webhook
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "iyziEventType": "PAYMENT_AUTH",
    "paymentId": "12345",
    "conversationId": "ORDER-123",
    "status": "success"
  }'
```

### Test Webhook Signature

```python
import hmac
import hashlib

payload = b'{"iyziEventType":"PAYMENT_AUTH",...}'
secret = 'your-webhook-secret'

signature = hmac.new(
    secret.encode('utf-8'),
    payload,
    hashlib.sha256
).hexdigest()

# Include in request header
# X-Iyzico-Signature: {signature}
```

---

## Summary

✅ **3D Secure Flow:**
1. Initialize payment → Get HTML → User redirected to Iyzico
2. User authenticates → Redirected to callback URL
3. Callback handler completes payment → Triggers signal
4. User redirected to success/error page
5. Webhook arrives (asynchronous confirmation)

✅ **Key Files:**
- `views_3ds.py` - 3DS payment views
- `signals.py` - Signal handlers for all events
- Built-in: `/payments/callback/` - 3DS callback handler
- Built-in: `/payments/webhook/` - Webhook handler

✅ **Built-In Features:**
- Callback URL handler (no code needed)
- Webhook handler (no code needed)
- Signature validation
- IP whitelisting
- Signal system for event handling

✅ **You Only Need To:**
1. Configure URLs (done in example)
2. Set success/error redirect URLs
3. Write signal handlers to update your orders
4. Configure webhook URL in Iyzico panel

**Everything else is handled automatically by django-iyzico!**
