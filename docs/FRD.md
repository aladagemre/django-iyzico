# Functional Requirements Document (FRD)
## django-iyzico

**Document Version:** 1.0
**Date:** 2025-12-15
**Author:** Emre Aladag
**Status:** Draft

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional requirements for `django-iyzico`, detailing what the system will do and how users will interact with it.

### 1.2 Scope
This FRD covers all functional aspects of the package, including:
- Payment processing flows
- Data models and storage
- API endpoints and views
- Admin interface
- Webhook handling
- Signal system

### 1.3 References
- [Business Requirements Document (BRD)](BRD.md)
- [Iyzico API Documentation](https://docs.iyzico.com)
- [Official iyzipay Python SDK](https://github.com/iyzico/iyzipay-python)

---

## 2. System Overview

### 2.1 User Roles

**Role 1: Django Developer**
- Integrates the package into their Django project
- Configures settings
- Implements payment flows in their views

**Role 2: Site Administrator**
- Views payment transactions in Django admin
- Monitors payment status
- Handles refunds (manual or through admin)

**Role 3: End User (Customer)**
- Provides payment information
- Completes payment flow
- Receives payment confirmation

**Role 4: Iyzico System**
- Processes payments
- Sends webhooks
- Returns payment status

---

## 3. Functional Requirements

### FR-1: Payment Processing

#### FR-1.1: Initialize Payment
**Priority:** Critical
**Description:** Create a payment request with Iyzico

**Inputs:**
- Order/transaction data (amount, currency, basket ID)
- Payment card information
- Buyer information (name, email, address)
- Billing/shipping address

**Process:**
1. Validate input data
2. Create payment request via Iyzico API
3. Handle 3D Secure redirect if enabled
4. Store transaction in database
5. Return payment result

**Outputs:**
- Payment response (success/failure)
- Transaction ID
- 3D Secure HTML (if applicable)

**Acceptance Criteria:**
- Payment is created in Iyzico system
- Transaction is saved to database
- User receives appropriate response
- All required fields are validated

#### FR-1.2: Complete 3D Secure Payment
**Priority:** High
**Description:** Handle 3D Secure callback and complete payment

**Inputs:**
- 3D Secure callback token
- Conversation ID

**Process:**
1. Verify callback authenticity
2. Complete payment with Iyzico
3. Update transaction status
4. Trigger payment signals

**Outputs:**
- Final payment status
- Updated transaction record

**Acceptance Criteria:**
- 3D Secure flow completes successfully
- Transaction status is updated
- Signals are triggered

#### FR-1.3: Handle Payment Response
**Priority:** Critical
**Description:** Process and store payment response data

**Inputs:**
- Iyzico API response

**Process:**
1. Parse response JSON
2. Extract payment details
3. Mask/remove sensitive card data
4. Store safe data only (last 4 digits, card type)
5. Update transaction status

**Outputs:**
- Processed payment record
- Sanitized card information

**Acceptance Criteria:**
- Full card numbers are never stored
- Only last 4 digits retained
- Response is fully parsed
- All relevant data captured

---

### FR-2: Transaction Management

#### FR-2.1: Transaction Model
**Priority:** Critical
**Description:** Abstract base model for payment transactions

**Fields:**
```python
- id (PK)
- payment_id (Iyzico payment ID, unique)
- conversation_id (Iyzico conversation ID)
- status (pending/success/failed/refunded)
- amount (Decimal)
- paid_amount (Decimal)
- currency (default: TRY)
- locale (default: tr)
- payment_type (card/bank_transfer/etc)
- installment (integer)
- card_last_four_digits (string, max 4 chars)
- card_type (string)
- card_association (string)
- card_family (string)
- buyer_email (string)
- buyer_name (string)
- error_code (string, nullable)
- error_message (text, nullable)
- raw_response (JSONField)
- created_at (DateTime)
- updated_at (DateTime)
```

**Features:**
- Abstract model (users extend in their projects)
- Automatic timestamp management
- Status tracking
- Full audit trail via raw_response

**Acceptance Criteria:**
- Model can be extended easily
- All payment data captured
- No sensitive data stored
- Queryable by status, date, etc.

#### FR-2.2: Transaction Status Updates
**Priority:** High
**Description:** Update transaction status based on payment lifecycle

**Status Flow:**
```
pending -> processing -> success
                      -> failed
success -> refund_pending -> refunded
```

**Process:**
1. Create transaction with 'pending' status
2. Update to 'processing' during payment
3. Set final status based on result
4. Allow refund status transition

**Acceptance Criteria:**
- Status transitions are validated
- Invalid transitions are rejected
- Status history is preserved

---

### FR-3: Webhook Handling

#### FR-3.1: Receive Webhook
**Priority:** High
**Description:** Receive and validate webhook from Iyzico

**Endpoint:** `/iyzico/webhook/`
**Method:** POST

**Process:**
1. Receive webhook POST request
2. Verify webhook signature (if implemented by Iyzico)
3. Parse webhook data
4. Trigger appropriate webhook signal
5. Return 200 OK

**Security:**
- CSRF exempt (external webhook)
- Optional signature verification
- IP whitelist support (configuration)

**Acceptance Criteria:**
- Webhook is received successfully
- Invalid webhooks are rejected
- Signal is triggered
- Response is immediate (<1 second)

#### FR-3.2: Process Webhook Events
**Priority:** High
**Description:** Handle different webhook event types

**Event Types:**
- Payment success
- Payment failure
- Refund processed
- Chargeback initiated

**Process:**
1. Identify event type
2. Find related transaction
3. Update transaction status
4. Trigger event-specific signals
5. Execute user-defined handlers (via signals)

**Acceptance Criteria:**
- All event types handled
- Transaction is updated correctly
- Signals are triggered
- Idempotent (duplicate webhooks don't cause issues)

---

### FR-4: Django Admin Interface

#### FR-4.1: Transaction List View
**Priority:** Medium
**Description:** List all transactions in Django admin

**Features:**
- Filterable by status, date, amount
- Searchable by payment_id, buyer email
- Sortable by date, amount
- Status color coding
- Quick view of key details

**Columns:**
- Payment ID
- Status (with color)
- Amount
- Buyer Email
- Created At
- Actions (view details, refund)

**Acceptance Criteria:**
- All transactions visible
- Filters work correctly
- Search finds transactions
- Performance acceptable (< 1s load)

#### FR-4.2: Transaction Detail View
**Priority:** Medium
**Description:** View full transaction details

**Sections:**
- Payment Information (amount, status, IDs)
- Buyer Information (name, email, address)
- Card Information (last 4 digits, type)
- Timeline (created, updated, status changes)
- Raw Response (expandable JSON)

**Actions:**
- Initiate refund (if applicable)
- View in Iyzico dashboard (external link)

**Acceptance Criteria:**
- All data displayed clearly
- Sensitive data not shown
- Actions work correctly

#### FR-4.3: Refund via Admin
**Priority:** Low
**Description:** Process refunds through admin interface

**Process:**
1. Select transaction
2. Choose refund action
3. Confirm refund amount
4. Submit to Iyzico API
5. Update transaction status

**Acceptance Criteria:**
- Refund is processed
- Transaction updated
- Confirmation message shown
- Errors handled gracefully

---

### FR-5: Django REST Framework Support

#### FR-5.1: Transaction Serializer
**Priority:** Medium
**Description:** DRF serializer for transaction data

**Fields:**
- All non-sensitive transaction fields
- Read-only for security

**Features:**
- Excludes sensitive data
- Nested buyer information
- Status choices
- Timestamp formatting

**Acceptance Criteria:**
- Serializer works with DRF views
- Sensitive data excluded
- Validation works

#### FR-5.2: Payment API View
**Priority:** Low
**Description:** Optional DRF view for payment processing

**Endpoint:** `/api/iyzico/payments/`
**Method:** POST

**Features:**
- Token authentication
- Request validation
- Response serialization

**Acceptance Criteria:**
- API endpoint works
- Authentication enforced
- Validation prevents invalid requests

---

### FR-6: Signal System

#### FR-6.1: Payment Lifecycle Signals
**Priority:** Medium
**Description:** Django signals for payment events

**Signals:**
```python
payment_initiated = Signal()  # When payment starts
payment_completed = Signal()  # When payment succeeds
payment_failed = Signal()     # When payment fails
payment_refunded = Signal()   # When refund processed
```

**Arguments:**
- sender: Transaction model class
- instance: Transaction instance
- raw_response: Iyzico API response
- request: HTTP request (if available)

**Usage Example:**
```python
from django_iyzico.signals import payment_completed

@receiver(payment_completed)
def on_payment_completed(sender, instance, **kwargs):
    # Update order status
    # Send confirmation email
    # Add quota to user
```

**Acceptance Criteria:**
- Signals are triggered at correct times
- Arguments are passed correctly
- Multiple receivers can connect
- Exceptions in receivers don't break payment flow

#### FR-6.2: 3D Secure Signals
**Priority:** Low
**Description:** Signals for 3D Secure flow

**Signals:**
```python
threeds_initiated = Signal()   # 3DS flow started
threeds_completed = Signal()   # 3DS completed
threeds_failed = Signal()      # 3DS failed
```

**Acceptance Criteria:**
- 3DS lifecycle tracked
- Signals work like payment signals

#### FR-6.3: Webhook Signals
**Priority:** Medium
**Description:** Signals for webhook events

**Signals:**
```python
webhook_received = Signal()  # Any webhook
```

**Arguments:**
- event_type: Webhook event type
- data: Webhook payload
- transaction: Related transaction (if found)

**Acceptance Criteria:**
- Webhook events trigger signals
- Payload is accessible
- Works with unknown event types

---

### FR-7: Configuration & Settings

#### FR-7.1: Required Settings
**Priority:** Critical
**Description:** Settings that must be configured

**Settings:**
```python
IYZICO_API_KEY = "your-api-key"
IYZICO_SECRET_KEY = "your-secret-key"
IYZICO_BASE_URL = "https://sandbox-api.iyzipay.com"
```

**Validation:**
- Raise ImproperlyConfigured if missing
- Clear error messages

**Acceptance Criteria:**
- Settings are validated on startup
- Missing settings cause clear errors
- Documentation is complete

#### FR-7.2: Optional Settings
**Priority:** Medium
**Description:** Settings with sensible defaults

**Settings:**
```python
IYZICO_LOCALE = "tr"  # Default locale
IYZICO_CURRENCY = "TRY"  # Default currency
IYZICO_STORE_CARD_DATA = True  # Store last 4 digits
IYZICO_ENABLE_3D_SECURE = True  # Enable 3DS
IYZICO_CALLBACK_URL = "/iyzico/callback/"
IYZICO_WEBHOOK_URL = "/iyzico/webhook/"
```

**Acceptance Criteria:**
- Defaults work out of the box
- Customizable per project
- Documented

---

### FR-8: Error Handling

#### FR-8.1: Custom Exceptions
**Priority:** High
**Description:** Django-friendly exceptions

**Exception Classes:**
```python
IyzicoError              # Base exception
PaymentError             # Payment processing failed
ValidationError          # Invalid data
ConfigurationError       # Settings misconfigured
WebhookError            # Webhook processing failed
CardError               # Card-related error
ThreeDSecureError       # 3DS failed
```

**Features:**
- Include Iyzico error codes
- Include error messages
- Loggable and debuggable

**Acceptance Criteria:**
- All error types covered
- Errors are raised appropriately
- Error messages are helpful

#### FR-8.2: Error Logging
**Priority:** Medium
**Description:** Log errors for debugging

**Process:**
1. Catch exceptions
2. Log with appropriate level
3. Include context (transaction ID, user, etc.)
4. Preserve stack traces

**Acceptance Criteria:**
- Errors are logged
- Log level is appropriate
- Logs are searchable

---

### FR-9: Utilities

#### FR-9.1: Card Data Masking
**Priority:** Critical
**Description:** Utility to mask sensitive card data

**Function:**
```python
def mask_card_data(payment_details: dict) -> dict:
    """Remove sensitive card data, keep last 4 digits."""
```

**Process:**
1. Deep copy payment details
2. Remove full card number
3. Keep last 4 digits
4. Remove CVC
5. Keep card type, family, association

**Acceptance Criteria:**
- Full card number never stored
- CVC never stored
- Last 4 digits retained
- Non-sensitive data preserved

#### FR-9.2: Amount Validation
**Priority:** High
**Description:** Validate payment amounts

**Function:**
```python
def validate_amount(amount: Decimal, currency: str) -> bool:
    """Validate amount is positive and has correct precision."""
```

**Validation:**
- Amount > 0
- Maximum 2 decimal places
- Within Iyzico limits

**Acceptance Criteria:**
- Invalid amounts rejected
- Clear error messages
- Currency-aware validation

---

## 4. User Stories

### US-1: Django Developer Integrates Payment
**As a** Django developer
**I want to** integrate Iyzico payments easily
**So that** I can add payment functionality quickly

**Acceptance Criteria:**
- Can install via pip
- Can configure in <10 minutes
- Can process first payment in <1 hour

### US-2: Admin Views Transactions
**As a** site administrator
**I want to** view all payment transactions
**So that** I can monitor payment status and handle issues

**Acceptance Criteria:**
- Can see all transactions in admin
- Can filter and search
- Can view full details

### US-3: Developer Handles Payment Success
**As a** Django developer
**I want to** receive a signal when payment succeeds
**So that** I can update my order and send confirmation

**Acceptance Criteria:**
- Signal is triggered on success
- Transaction data is accessible
- Can connect multiple handlers

### US-4: System Receives Webhook
**As a** payment system
**I want to** receive webhook notifications from Iyzico
**So that** payment status is updated in real-time

**Acceptance Criteria:**
- Webhook endpoint receives POST
- Transaction is updated
- Response is immediate

---

## 5. Acceptance Criteria Summary

### Phase 1 (MVP)
- [ ] Payment processing works
- [ ] Transaction model stores all data
- [ ] No sensitive card data stored
- [ ] Settings configuration works
- [ ] Basic error handling
- [ ] Tests pass (>80% coverage)

### Phase 2 (Enhanced)
- [ ] Webhook handling works
- [ ] Admin interface functional
- [ ] Signals trigger correctly
- [ ] DRF support works
- [ ] Tests pass (>90% coverage)
- [ ] Documentation complete

### Phase 3 (Advanced)
- [ ] 3D Secure flow works
- [ ] Refund processing works
- [ ] All utilities functional
- [ ] Performance benchmarks met
- [ ] Production-ready

---

## 6. Out of Scope

The following are NOT included in v1.0:

- Subscription management
- Installment payments
- Multi-currency beyond TRY
- Payment method tokenization
- Split payments
- Marketplace payments
- Mobile SDK integration

These may be added in future versions based on demand.

---

## 7. Approval

**Prepared by:** Emre Aladag
**Date:** 2025-12-15
**Version:** 1.0

**Status:** ⏳ Draft - Awaiting System Design

---

## Next Steps

1. Review and finalize FRD
2. Create System Design Document
3. Map FRD to technical architecture
4. Begin implementation
