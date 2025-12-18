# Example Django Project with django-iyzico

This is a complete example Django e-commerce project demonstrating how to integrate django-iyzico for payment processing.

## Features Demonstrated

### Payment Processing
- ✅ **Direct Payment Flow** - Immediate payment processing
- ✅ **3D Secure Flow** - Redirect to Iyzico for authentication (most secure)
- ✅ **Webhook Integration** - Automatic webhook handling for payment events
- ✅ Regular Django views for payment checkout
- ✅ Django REST Framework API endpoints
- ✅ Subscription payments (recurring billing)
- ✅ Installment payments with BIN lookup
- ✅ Multi-currency support (TRY, USD, EUR, GBP)
- ✅ Full and partial refunds
- ✅ Complete signal handlers for all events

### Project Structure
```
example/
├── ecommerce_site/          # Django project
│   ├── __init__.py
│   ├── settings.py          # Project settings
│   ├── urls.py              # Main URL configuration
│   └── wsgi.py
├── shop/                    # E-commerce app
│   ├── models.py            # Order and Payment models
│   ├── views.py             # Regular Django views
│   ├── api_views.py         # DRF API views
│   ├── serializers.py       # DRF serializers
│   ├── urls.py              # Shop URLs
│   ├── api_urls.py          # API URLs
│   ├── admin.py             # Admin configuration
│   └── templates/           # HTML templates
├── manage.py
└── requirements.txt
```

## Installation

### 1. Install Dependencies

```bash
cd example
pip install -r requirements.txt
```

### 2. Configure Settings

Create a `.env` file in the example directory:

```env
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database (using SQLite for demo)
DATABASE_URL=sqlite:///db.sqlite3

# Iyzico API credentials (use sandbox for testing)
IYZICO_API_KEY=your-sandbox-api-key
IYZICO_SECRET_KEY=your-sandbox-secret-key
IYZICO_BASE_URL=https://sandbox-api.iyzipay.com

# Optional: Webhook security
IYZICO_WEBHOOK_SECRET=your-webhook-secret

# Optional: Celery (for subscriptions)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 3. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py runserver
```

### 6. (Optional) Run Celery for Subscriptions

In separate terminals:

```bash
# Start Celery worker
celery -A ecommerce_site worker -l info

# Start Celery Beat (for scheduled subscription billing)
celery -A ecommerce_site beat -l info
```

## Usage

### Web Interface (Regular Django Views)

Visit these URLs in your browser:

- **Homepage**: http://localhost:8000/
- **Product Listing**: http://localhost:8000/shop/products/
- **Checkout**: http://localhost:8000/shop/checkout/
- **Subscription Plans**: http://localhost:8000/shop/subscriptions/
- **Order History**: http://localhost:8000/shop/orders/
- **Admin**: http://localhost:8000/admin/

### REST API (Django REST Framework)

API endpoints available at:

- **API Root**: http://localhost:8000/api/
- **Orders**: http://localhost:8000/api/orders/
- **Payments**: http://localhost:8000/api/payments/
- **Subscriptions**: http://localhost:8000/api/subscriptions/
- **Create Payment**: POST http://localhost:8000/api/payments/create/
- **Process Refund**: POST http://localhost:8000/api/payments/{id}/refund/

#### API Authentication

The API uses session authentication for simplicity. In production, use token authentication:

```python
# Example API call with Python requests
import requests

response = requests.post(
    'http://localhost:8000/api/payments/create/',
    json={
        'amount': '100.00',
        'currency': 'TRY',
        'card_holder_name': 'John Doe',
        'card_number': '5528790000000008',
        'expire_month': '12',
        'expire_year': '2030',
        'cvc': '123'
    },
    headers={'Content-Type': 'application/json'}
)

print(response.json())
```

### Test Cards (Sandbox)

Use these test cards in sandbox mode:

**Successful Payment:**
```
Card Number: 5528790000000008
Holder: John Doe
Expire: 12/2030
CVC: 123
```

**3D Secure (OTP: 123456):**
```
Card Number: 5528790000000008
Holder: John Doe
Expire: 12/2030
CVC: 123
```

## 3D Secure and Webhook Flow

**⚠️ IMPORTANT:** For production use, you should use the **3D Secure flow** (not direct payment) for maximum security.

### Quick Overview

**3D Secure Flow (Recommended):**
1. User enters card details on your site
2. Your site initializes 3DS payment with Iyzico
3. **User is redirected to Iyzico's secure page**
4. User authenticates (SMS code, bank app, etc.)
5. **Iyzico redirects back to your callback URL**
6. Payment is completed automatically
7. **Webhook notification arrives** (final confirmation)

**Built-in URL Handlers:**
- `/payments/callback/` - Handles 3DS redirects (built into django-iyzico)
- `/payments/webhook/` - Handles webhook notifications (built into django-iyzico)

**You only need to:**
1. Write your checkout view (see `views_3ds.py`)
2. Handle signals to update your orders (see `signals.py`)
3. Configure webhook URL in Iyzico merchant panel

**Complete Documentation:** See [3DS_AND_WEBHOOK_FLOW.md](3DS_AND_WEBHOOK_FLOW.md) for detailed flow explanation, configuration, and testing guide.

---

## Code Examples

### 1. 3D Secure Payment (Recommended)

```python
# views_3ds.py
from django_iyzico.client import IyzicoClient

def checkout_3ds_view(request):
    # Create order
    order = Order.objects.create(...)

    # Initialize 3D Secure payment
    client = IyzicoClient()
    response = client.create_3ds_payment(
        order_data={
            'conversationId': order.conversation_id,
            'price': str(order.amount),
            'paidPrice': str(order.amount),
            'currency': order.currency,
            'basketId': order.order_number,
        },
        payment_card={...},
        buyer={...},
        billing_address={...}
    )

    if response.is_successful():
        # Return HTML that redirects to Iyzico
        html = response.three_ds_html_content
        return HttpResponse(html)
```

**What happens next:**
- User sees Iyzico's authentication page
- After authentication, Iyzico calls `/payments/callback/`
- Your signal handler updates the order
- User is redirected to success page
- Webhook arrives for final confirmation

### 2. One-Time Payment (Direct - No 3DS)

```python
# shop/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from decimal import Decimal
from django_iyzico.client import IyzicoClient
from .models import Order

def checkout_view(request):
    if request.method == 'POST':
        # Create order
        order = Order.objects.create(
            user=request.user,
            amount=Decimal(request.POST['amount']),
            currency='TRY'
        )

        # Process payment
        client = IyzicoClient()
        payment_data = {
            'price': str(order.amount),
            'paidPrice': str(order.amount),
            'currency': order.currency,
            'basketId': f'ORDER-{order.id}',
            'paymentCard': {
                'cardHolderName': request.POST['card_holder'],
                'cardNumber': request.POST['card_number'],
                'expireMonth': request.POST['expire_month'],
                'expireYear': request.POST['expire_year'],
                'cvc': request.POST['cvc'],
            },
            'buyer': {
                'id': str(request.user.id),
                'name': request.user.first_name,
                'surname': request.user.last_name,
                'email': request.user.email,
                'identityNumber': '11111111111',
                'registrationAddress': 'Address',
                'city': 'Istanbul',
                'country': 'Turkey',
            },
        }

        response = client.create_payment(payment_data)

        if response.is_successful():
            order.update_from_response(response)
            messages.success(request, 'Payment successful!')
            return redirect('order_success', order_id=order.id)
        else:
            messages.error(request, f'Payment failed: {response.error_message}')

    return render(request, 'shop/checkout.html')
```

### 2. Subscription Payment

```python
# shop/views.py
from django_iyzico.subscription_models import SubscriptionPlan
from django_iyzico.subscription_manager import SubscriptionManager

def subscribe_view(request, plan_id):
    plan = SubscriptionPlan.objects.get(id=plan_id)

    if request.method == 'POST':
        manager = SubscriptionManager()

        subscription = manager.create_subscription(
            plan=plan,
            user=request.user,
            payment_method={
                'cardHolderName': request.POST['card_holder'],
                'cardNumber': request.POST['card_number'],
                'expireMonth': request.POST['expire_month'],
                'expireYear': request.POST['expire_year'],
                'cvc': request.POST['cvc'],
            }
        )

        if subscription.status == 'ACTIVE':
            messages.success(request, 'Subscription activated!')
            return redirect('subscription_success')

    return render(request, 'shop/subscribe.html', {'plan': plan})
```

### 3. API Payment (DRF)

```python
# shop/api_views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django_iyzico.client import IyzicoClient
from .models import Order

@api_view(['POST'])
def create_payment(request):
    # Create order
    order = Order.objects.create(
        user=request.user,
        amount=request.data['amount'],
        currency=request.data.get('currency', 'TRY')
    )

    # Process payment
    client = IyzicoClient()
    payment_data = {
        'price': str(order.amount),
        'paidPrice': str(order.amount),
        'currency': order.currency,
        'basketId': f'ORDER-{order.id}',
        'paymentCard': {
            'cardHolderName': request.data['card_holder_name'],
            'cardNumber': request.data['card_number'],
            'expireMonth': request.data['expire_month'],
            'expireYear': request.data['expire_year'],
            'cvc': request.data['cvc'],
        },
        # ... buyer info
    }

    response = client.create_payment(payment_data)

    if response.is_successful():
        order.update_from_response(response)
        return Response({
            'status': 'success',
            'order_id': order.id,
            'payment_id': order.payment_id
        })
    else:
        return Response({
            'status': 'error',
            'message': response.error_message
        }, status=400)
```

## Project Features

### Models

The example includes:
- `Product` - Products for sale
- `Order` - Customer orders (extends AbstractIyzicoPayment)
- Integration with django-iyzico subscription models

### Views

**Regular Django Views:**
- Product listing
- Shopping cart
- Checkout with payment
- Order confirmation
- Subscription plans
- Order history

**REST API Views:**
- Payment creation
- Payment status
- Refund processing
- Subscription management
- Order listing

### Admin Interface

Access the admin at `/admin/` to:
- Manage products
- View orders and payments
- Process refunds
- Manage subscription plans
- View subscription details

### Signal Handlers

The example includes signal handlers for:
- Payment completion (send confirmation email)
- Payment failure (log and notify)
- Subscription activation (grant access)
- Subscription cancellation (revoke access)

## Testing

### Run Tests

```bash
python manage.py test shop
```

### Manual Testing Checklist

- [ ] Create an order and pay with test card
- [ ] Test 3D Secure flow
- [ ] Create a subscription
- [ ] Test installment payments
- [ ] Process a refund
- [ ] Test webhook delivery
- [ ] Test API endpoints
- [ ] Test multi-currency payments

## Production Deployment

Before deploying to production:

1. **Set DEBUG=False** in settings
2. **Use production Iyzico credentials**
3. **Configure ALLOWED_HOSTS**
4. **Set up proper database** (PostgreSQL recommended)
5. **Configure Redis for Celery** (for subscriptions)
6. **Set up SSL/TLS** (HTTPS required)
7. **Configure webhook URL** in Iyzico merchant panel
8. **Enable webhook security** (signature validation, IP whitelist)
9. **Set up logging and monitoring**
10. **Configure email backend** for notifications

## Troubleshooting

### Payment Fails

- Check API credentials are correct
- Ensure using sandbox URL for testing
- Verify card details are correct
- Check Iyzico API logs

### Webhook Not Working

- Ensure webhook URL is publicly accessible
- Check webhook signature validation settings
- Verify IP whitelist configuration
- Test with ngrok for local development

### Subscription Not Billing

- Ensure Celery worker is running
- Check Celery Beat is running
- Verify Redis is accessible
- Check subscription status in admin

## Support

- **Documentation**: See main README.md
- **Issues**: https://github.com/aladagemre/django-iyzico/issues
- **Iyzico Docs**: https://dev.iyzipay.com/

## License

This example project is provided as-is for demonstration purposes.
