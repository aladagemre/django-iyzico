"""
3D Secure payment views demonstrating the redirect flow.
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django_iyzico.client import IyzicoClient
from django_iyzico.exceptions import ThreeDSecureError, PaymentError
from .models import Product, Order, OrderItem


@login_required
def checkout_3ds_view(request):
    """
    Checkout with 3D Secure payment flow.

    Demonstrates:
    1. Creating order
    2. Initializing 3D Secure payment
    3. Displaying 3DS HTML form (redirects to Iyzico)
    4. User authenticates on Iyzico's page
    5. Iyzico redirects back to callback URL
    6. Callback handler completes payment
    7. Webhook gets triggered for final status
    """

    if request.method == 'POST':
        # Get form data
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        currency = request.POST.get('currency', 'TRY')
        installment_count = int(request.POST.get('installment', 1))

        # Get product
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # Check stock
        if product.stock < quantity:
            messages.error(request, 'Insufficient stock.')
            return redirect('product_detail', pk=product_id)

        # Calculate total
        total = product.price * quantity

        # Create order
        order = Order.objects.create(
            user=request.user,
            amount=total,
            currency=currency,
            order_status='PENDING_PAYMENT',
            installment_count=installment_count,
            conversation_id=f'3DS-ORDER-{Order.objects.count() + 1}',
            shipping_address=request.POST.get('address', ''),
            shipping_city=request.POST.get('city', ''),
            shipping_country='Turkey',
            buyer_name=request.user.first_name or 'Customer',
            buyer_surname=request.user.last_name or 'User',
            buyer_email=request.user.email,
        )

        # Add order item
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price,
            currency=product.currency
        )

        # Store order ID in session for callback
        request.session['pending_order_id'] = order.id

        # Set success/error redirect URLs in session
        request.session['iyzico_success_url'] = f'/shop/orders/{order.id}/success/'
        request.session['iyzico_error_url'] = f'/shop/checkout/error/'

        # Prepare 3D Secure payment data
        client = IyzicoClient()

        order_data = {
            'conversationId': order.conversation_id,
            'price': str(total),
            'paidPrice': str(total),
            'currency': currency,
            'basketId': order.order_number,
            'installment': installment_count,
        }

        payment_card = {
            'cardHolderName': request.POST.get('card_holder'),
            'cardNumber': request.POST.get('card_number'),
            'expireMonth': request.POST.get('expire_month'),
            'expireYear': request.POST.get('expire_year'),
            'cvc': request.POST.get('cvc'),
        }

        buyer = {
            'id': str(request.user.id),
            'name': request.user.first_name or 'Customer',
            'surname': request.user.last_name or 'User',
            'email': request.user.email,
            'identityNumber': '11111111111',
            'registrationAddress': request.POST.get('address', 'Address'),
            'city': request.POST.get('city', 'Istanbul'),
            'country': 'Turkey',
            'zipCode': '34000',
        }

        billing_address = {
            'address': request.POST.get('address', 'Address'),
            'city': request.POST.get('city', 'Istanbul'),
            'country': 'Turkey',
            'zipCode': '34000',
        }

        try:
            # Initialize 3D Secure payment
            # This returns HTML that redirects to Iyzico's 3DS page
            response = client.create_3ds_payment(
                order_data=order_data,
                payment_card=payment_card,
                buyer=buyer,
                billing_address=billing_address,
                shipping_address=billing_address,
                # callback_url is optional - uses IYZICO_CALLBACK_URL from settings
                # callback_url='https://yourdomain.com/payments/callback/'
            )

            if response.is_successful():
                # Get 3D Secure HTML content
                # This is a form that auto-submits and redirects to Iyzico
                html_content = response.three_ds_html_content

                # Store payment info before redirect
                order.payment_status = 'PENDING'
                order.save()

                # Return the HTML - this will redirect user to Iyzico
                # After authentication, Iyzico will call our callback URL
                return HttpResponse(html_content)
            else:
                # 3DS initialization failed
                order.payment_status = 'FAILED'
                order.error_message = response.error_message
                order.save()
                messages.error(request, f'Payment initialization failed: {response.error_message}')
                return redirect('checkout_3ds')

        except ThreeDSecureError as e:
            messages.error(request, f'3D Secure error: {str(e)}')
            return redirect('checkout_3ds')
        except Exception as e:
            messages.error(request, f'Unexpected error: {str(e)}')
            return redirect('checkout_3ds')

    # GET request - show checkout form
    context = {
        'products': Product.objects.filter(is_active=True, stock__gt=0),
    }
    return render(request, 'shop/checkout_3ds.html', context)


@login_required
def payment_success_3ds_view(request, order_id):
    """
    Success page after 3D Secure payment.

    This is called after:
    1. User completes 3DS authentication on Iyzico's page
    2. Iyzico redirects back to callback URL (/payments/callback/)
    3. Callback handler (built into django-iyzico) completes payment
    4. User is redirected here (from session['iyzico_success_url'])
    5. Webhook is also triggered asynchronously
    """

    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Get payment info from session (set by callback handler)
    payment_id = request.session.get('last_payment_id')
    payment_status = request.session.get('last_payment_status')

    # Clean up session
    if 'pending_order_id' in request.session:
        del request.session['pending_order_id']
    if 'last_payment_id' in request.session:
        del request.session['last_payment_id']
    if 'last_payment_status' in request.session:
        del request.session['last_payment_status']

    # The order should already be updated by the callback handler
    # But you can also refresh it from the database
    order.refresh_from_db()

    context = {
        'order': order,
        'payment_id': payment_id,
        'success': payment_status == 'success',
    }

    return render(request, 'shop/payment_success_3ds.html', context)


def payment_error_3ds_view(request):
    """
    Error page after 3D Secure payment failure.

    This is called when payment fails during 3DS flow.
    """

    # Get error info from session (set by callback handler)
    error_message = request.session.get('last_payment_error', 'Payment failed')
    error_code = request.session.get('last_payment_error_code')
    conversation_id = request.session.get('last_payment_conversation_id')

    # Get pending order if available
    order_id = request.session.get('pending_order_id')
    order = None
    if order_id:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            pass

    # Clean up session
    if 'pending_order_id' in request.session:
        del request.session['pending_order_id']
    if 'last_payment_error' in request.session:
        del request.session['last_payment_error']
    if 'last_payment_error_code' in request.session:
        del request.session['last_payment_error_code']
    if 'last_payment_conversation_id' in request.session:
        del request.session['last_payment_conversation_id']

    context = {
        'error_message': error_message,
        'error_code': error_code,
        'conversation_id': conversation_id,
        'order': order,
    }

    return render(request, 'shop/payment_error_3ds.html', context)


# ============================================================================
# IMPORTANT: Webhook Handler
# ============================================================================
#
# The webhook handler is ALREADY BUILT INTO django-iyzico!
# It's automatically available at: /payments/webhook/
#
# You just need to:
# 1. Include django_iyzico.urls in your main urls.py (already done)
# 2. Configure webhook URL in Iyzico merchant panel
# 3. Connect to webhook signals to handle events
#
# See shop/signals.py for webhook signal handler examples
#
# The webhook handler:
# - Validates webhook signature (if IYZICO_WEBHOOK_SECRET is set)
# - Checks IP whitelist (if IYZICO_WEBHOOK_ALLOWED_IPS is set)
# - Triggers webhook_received signal with event data
# - Returns 200 OK (to prevent Iyzico retry spam)
#
# ============================================================================
