"""
Advanced Usage Examples for django-iyzico

This file contains comprehensive real-world examples demonstrating
advanced patterns and best practices for using django-iyzico.

Author: Emre Aladag
Version: 0.1.0-beta
"""

from decimal import Decimal
from typing import Optional, Dict, Any
import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from django_iyzico.client import IyzicoClient
from django_iyzico.exceptions import PaymentError, CardError, ValidationError
from django_iyzico.signals import payment_completed, payment_failed
from django_iyzico.utils import (
    generate_basket_id,
    calculate_installment_amount,
    validate_amount,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Example 1: E-Commerce Checkout Flow with Complete Error Handling
# =============================================================================


@login_required
@require_http_methods(["GET", "POST"])
def ecommerce_checkout(request: HttpRequest) -> HttpResponse:
    """
    Complete e-commerce checkout flow with:
    - Shopping cart validation
    - 3D Secure payment
    - Comprehensive error handling
    - User feedback
    - Order creation in transaction
    """
    from myapp.models import Order, CartItem

    if request.method == "GET":
        # Display checkout form
        cart_items = CartItem.objects.filter(user=request.user, ordered=False).select_related(
            "product"
        )

        total_amount = sum(item.get_total_price() for item in cart_items)

        context = {
            "cart_items": cart_items,
            "total_amount": total_amount,
            "basket_id": generate_basket_id(),
        }
        return render(request, "checkout.html", context)

    # POST - Process payment
    try:
        # Validate cart
        cart_items = CartItem.objects.filter(user=request.user, ordered=False).select_related(
            "product"
        )

        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect("cart")

        # Calculate total
        total_amount = sum(item.get_total_price() for item in cart_items)

        # Validate amount
        if total_amount <= 0:
            messages.error(request, "Invalid cart total.")
            return redirect("cart")

        validate_amount(total_amount)

        # Create order and process payment in atomic transaction
        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                user=request.user,
                conversation_id=f"ORDER-{uuid.uuid4()}",
                amount=total_amount,
                paid_amount=total_amount,
                currency="TRY",
                status="pending",
                buyer_email=request.user.email,
                buyer_name=request.user.first_name,
                buyer_surname=request.user.last_name,
            )

            # Link cart items to order
            for item in cart_items:
                item.order = order
                item.ordered = True
                item.save()

            # Prepare payment data
            basket_items = [
                {
                    "id": str(item.product.id),
                    "name": item.product.name[:128],  # Max 128 chars
                    "category1": item.product.category.name if item.product.category else "Product",
                    "itemType": "PHYSICAL",
                    "price": str(item.get_total_price()),
                }
                for item in cart_items
            ]

            # Get card data from form
            card_data = {
                "cardHolderName": request.POST.get("card_holder_name"),
                "cardNumber": request.POST.get("card_number").replace(" ", ""),
                "expireMonth": request.POST.get("expire_month"),
                "expireYear": request.POST.get("expire_year"),
                "cvc": request.POST.get("cvc"),
            }

            # Store masked card data
            order.mask_and_store_card_data({"card": card_data})

            # Prepare buyer data
            buyer_data = {
                "id": str(request.user.id),
                "name": request.user.first_name,
                "surname": request.user.last_name,
                "email": request.user.email,
                "identityNumber": "11111111111",  # Turkish ID number
                "registrationAddress": request.POST.get("address", "Address"),
                "city": request.POST.get("city", "Istanbul"),
                "country": "Turkey",
                "zipCode": request.POST.get("zip_code", "34000"),
            }

            # Prepare address data
            billing_address = {
                "address": request.POST.get("address", "Address"),
                "city": request.POST.get("city", "Istanbul"),
                "country": "Turkey",
                "zipCode": request.POST.get("zip_code", "34000"),
            }

            shipping_address = billing_address.copy()

            # Initialize payment client
            client = IyzicoClient()

            # Create 3D Secure payment
            order_data = {
                "conversationId": order.conversation_id,
                "price": str(total_amount),
                "paidPrice": str(total_amount),
                "basketId": f"BASKET-{order.id}",
                "installment": 1,
            }

            callback_url = request.build_absolute_uri(reverse("payment_callback"))

            response = client.create_3ds_payment(
                order_data=order_data,
                payment_card=card_data,
                buyer=buyer_data,
                billing_address=billing_address,
                shipping_address=shipping_address,
                basket_items=basket_items,
                callback_url=callback_url,
            )

            # Store 3DS token in session for callback verification
            request.session["payment_order_id"] = order.id
            request.session["payment_token"] = response.token

            # Update order with response
            order.update_from_response(response, save=True)

            # Return 3DS HTML content
            return HttpResponse(response.three_ds_html_content)

    except ValidationError as e:
        logger.warning(f"Validation error during checkout: {e}")
        messages.error(request, f"Invalid data: {e.message}")
        return redirect("checkout")

    except CardError as e:
        logger.warning(f"Card error during checkout: {e}")
        messages.error(request, "Card declined. Please check your card details.")
        return redirect("checkout")

    except PaymentError as e:
        logger.error(f"Payment error during checkout: {e}", exc_info=True)
        messages.error(request, "Payment failed. Please try again.")
        return redirect("checkout")

    except Exception as e:
        logger.error(f"Unexpected error during checkout: {e}", exc_info=True)
        messages.error(request, "An error occurred. Please try again.")
        return redirect("checkout")


# =============================================================================
# Example 2: Subscription Service with Recurring Payments
# =============================================================================


@login_required
@require_http_methods(["POST"])
def subscribe_to_premium(request: HttpRequest) -> JsonResponse:
    """
    Subscription service example:
    - Create subscription record
    - Process initial payment
    - Schedule recurring payments
    - Handle trial periods

    Note: Full subscription support coming in v0.2.0
    This example shows current workaround pattern.
    """
    from myapp.models import Subscription, Payment
    from django.utils.dateutil import relativedelta

    try:
        plan_id = request.POST.get("plan_id")

        # Get plan details (your custom model)
        from myapp.models import SubscriptionPlan

        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        # Check for existing active subscription
        existing = Subscription.objects.filter(user=request.user, status="active").first()

        if existing:
            return JsonResponse(
                {"success": False, "error": "You already have an active subscription."}, status=400
            )

        with transaction.atomic():
            # Create subscription record
            subscription = Subscription.objects.create(
                user=request.user,
                plan=plan,
                status="pending",
                start_date=timezone.now(),
                next_billing_date=timezone.now() + relativedelta(months=1),
                amount=plan.monthly_price,
            )

            # Create initial payment
            payment = Payment.objects.create(
                subscription=subscription,
                user=request.user,
                conversation_id=f"SUB-{subscription.id}-{uuid.uuid4()}",
                amount=plan.monthly_price,
                currency="TRY",
                buyer_email=request.user.email,
                buyer_name=request.user.first_name,
                buyer_surname=request.user.last_name,
            )

            # Prepare payment data
            client = IyzicoClient()

            card_data = {
                "cardHolderName": request.POST.get("card_holder_name"),
                "cardNumber": request.POST.get("card_number").replace(" ", ""),
                "expireMonth": request.POST.get("expire_month"),
                "expireYear": request.POST.get("expire_year"),
                "cvc": request.POST.get("cvc"),
            }

            buyer_data = {
                "id": str(request.user.id),
                "name": request.user.first_name,
                "surname": request.user.last_name,
                "email": request.user.email,
                "identityNumber": "11111111111",
                "registrationAddress": "Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            }

            billing_address = {
                "address": "Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            }

            order_data = {
                "conversationId": payment.conversation_id,
                "price": str(plan.monthly_price),
                "paidPrice": str(plan.monthly_price),
                "basketId": f"SUB-{subscription.id}",
            }

            # Process payment
            response = client.create_payment(
                order_data=order_data,
                payment_card=card_data,
                buyer=buyer_data,
                billing_address=billing_address,
            )

            payment.update_from_response(response)

            if response.is_successful():
                # Activate subscription
                subscription.status = "active"
                subscription.save()

                # Schedule next payment (using Celery task)
                from myapp.tasks import schedule_subscription_renewal

                schedule_subscription_renewal.apply_async(
                    args=[subscription.id], eta=subscription.next_billing_date
                )

                return JsonResponse(
                    {
                        "success": True,
                        "subscription_id": subscription.id,
                        "message": f"Successfully subscribed to {plan.name}!",
                    }
                )
            else:
                subscription.status = "failed"
                subscription.save()

                return JsonResponse(
                    {
                        "success": False,
                        "error": response.error_message or "Payment failed",
                    },
                    status=400,
                )

    except Exception as e:
        logger.error(f"Subscription error: {e}", exc_info=True)
        return JsonResponse(
            {
                "success": False,
                "error": "An error occurred. Please try again.",
            },
            status=500,
        )


# =============================================================================
# Example 3: Marketplace Split Payments (Multi-Vendor)
# =============================================================================


@login_required
@transaction.atomic
def marketplace_checkout(request: HttpRequest) -> HttpResponse:
    """
    Marketplace example with multiple vendors:
    - Split payments between vendors
    - Platform commission handling
    - Individual vendor payouts

    Note: This is a simplified example. Full marketplace support
    requires Iyzico's SubMerchant API (coming in future versions).
    """
    from myapp.models import MarketplaceOrder, OrderItem

    if request.method == "POST":
        try:
            cart_items = request.session.get("cart_items", [])

            if not cart_items:
                messages.error(request, "Cart is empty")
                return redirect("cart")

            # Group items by vendor
            vendor_groups = {}
            for item in cart_items:
                vendor_id = item["vendor_id"]
                if vendor_id not in vendor_groups:
                    vendor_groups[vendor_id] = []
                vendor_groups[vendor_id].append(item)

            # Create main order
            total_amount = sum(Decimal(item["price"]) * item["quantity"] for item in cart_items)

            main_order = MarketplaceOrder.objects.create(
                buyer=request.user,
                conversation_id=f"MARKET-{uuid.uuid4()}",
                total_amount=total_amount,
                status="pending",
            )

            # Create sub-orders for each vendor
            for vendor_id, items in vendor_groups.items():
                vendor_total = sum(Decimal(item["price"]) * item["quantity"] for item in items)

                # Platform takes 10% commission
                platform_commission = vendor_total * Decimal("0.10")
                vendor_payout = vendor_total - platform_commission

                # Create vendor order item
                OrderItem.objects.create(
                    marketplace_order=main_order,
                    vendor_id=vendor_id,
                    amount=vendor_total,
                    platform_commission=platform_commission,
                    vendor_payout=vendor_payout,
                )

            # Process single payment to platform
            # (Individual vendor payouts handled separately)
            client = IyzicoClient()

            # ... (payment processing similar to Example 1)

            messages.success(request, "Order placed successfully!")
            return redirect("order_confirmation", order_id=main_order.id)

        except Exception as e:
            logger.error(f"Marketplace checkout error: {e}", exc_info=True)
            messages.error(request, "Checkout failed. Please try again.")
            return redirect("cart")

    return render(request, "marketplace_checkout.html")


# =============================================================================
# Example 4: Installment Payment Calculator and Display
# =============================================================================


@require_http_methods(["GET"])
def get_installment_options(request: HttpRequest) -> JsonResponse:
    """
    Calculate and return available installment options for a product.

    Query params:
    - amount: Product price
    - card_bin: First 6 digits of card (optional, for bank-specific rates)

    Returns: List of installment options with calculated amounts
    """
    try:
        amount = Decimal(request.GET.get("amount", "0"))
        card_bin = request.GET.get("card_bin", "")

        validate_amount(amount)

        # Define installment rates (these would come from Iyzico API in production)
        # Different banks have different rates
        installment_rates = {
            1: Decimal("0.00"),  # No installment - no fee
            2: Decimal("0.02"),  # 2% fee
            3: Decimal("0.03"),  # 3% fee
            6: Decimal("0.06"),  # 6% fee
            9: Decimal("0.09"),  # 9% fee
            12: Decimal("0.12"),  # 12% fee
        }

        options = []
        for installment_count, rate in installment_rates.items():
            total_with_fee = amount * (1 + rate)
            monthly_payment = calculate_installment_amount(total_with_fee, installment_count)

            options.append(
                {
                    "installment_count": installment_count,
                    "monthly_payment": str(monthly_payment),
                    "total_amount": str(total_with_fee),
                    "fee_amount": str(amount * rate),
                    "fee_rate": str(rate * 100),  # As percentage
                    "display_text": (
                        f"{installment_count}x {monthly_payment} TRY"
                        if installment_count > 1
                        else "Single payment (no fee)"
                    ),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "base_amount": str(amount),
                "installment_options": options,
            }
        )

    except ValidationError as e:
        return JsonResponse(
            {
                "success": False,
                "error": str(e),
            },
            status=400,
        )

    except Exception as e:
        logger.error(f"Installment calculation error: {e}", exc_info=True)
        return JsonResponse(
            {
                "success": False,
                "error": "Failed to calculate installments",
            },
            status=500,
        )


# =============================================================================
# Example 5: Bulk Refund Processing with Async Tasks
# =============================================================================


def bulk_refund_orders(order_ids: list, reason: str, refund_percentage: int = 100):
    """
    Process bulk refunds for multiple orders.

    This is typically called from a Celery task for async processing.

    Args:
        order_ids: List of order IDs to refund
        reason: Refund reason
        refund_percentage: Percentage to refund (1-100)

    Returns:
        Dict with success/failure counts and details
    """
    from myapp.models import Order

    results = {
        "total": len(order_ids),
        "successful": 0,
        "failed": 0,
        "errors": [],
    }

    for order_id in order_ids:
        try:
            order = Order.objects.get(id=order_id)

            # Validate order can be refunded
            if not order.can_be_refunded():
                results["failed"] += 1
                results["errors"].append(
                    {
                        "order_id": order_id,
                        "error": f"Order {order_id} cannot be refunded (status: {order.status})",
                    }
                )
                continue

            # Calculate refund amount
            if refund_percentage == 100:
                refund_amount = None  # Full refund
            else:
                refund_amount = order.amount * (Decimal(refund_percentage) / 100)

            # Process refund
            response = order.process_refund(
                amount=refund_amount,
                reason=reason,
            )

            if response.is_successful():
                results["successful"] += 1
                logger.info(f"Refunded order {order_id}: {refund_amount or 'full'}")
            else:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "order_id": order_id,
                        "error": response.error_message,
                    }
                )

        except Order.DoesNotExist:
            results["failed"] += 1
            results["errors"].append(
                {
                    "order_id": order_id,
                    "error": "Order not found",
                }
            )

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(
                {
                    "order_id": order_id,
                    "error": str(e),
                }
            )
            logger.error(f"Error refunding order {order_id}: {e}", exc_info=True)

    return results


# =============================================================================
# Example 6: Payment Status Webhook Handler with Custom Logic
# =============================================================================

from django.dispatch import receiver


@receiver(payment_completed)
def handle_payment_success(sender, instance, **kwargs):
    """
    Handle successful payment with custom business logic.

    This signal is triggered when a payment completes successfully,
    including from webhook updates.
    """
    logger.info(f"Payment completed: {instance.payment_id}")

    # 1. Update user subscription/access
    if hasattr(instance, "subscription"):
        subscription = instance.subscription
        subscription.status = "active"
        subscription.save()

    # 2. Send confirmation email
    from django.core.mail import send_mail

    send_mail(
        subject=f"Payment Confirmation - Order {instance.conversation_id}",
        message=f"""
        Dear {instance.buyer_name},

        Your payment of {instance.amount} {instance.currency} has been processed successfully.

        Order ID: {instance.conversation_id}
        Payment ID: {instance.payment_id}
        Amount: {instance.amount} {instance.currency}

        Thank you for your purchase!
        """,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[instance.buyer_email],
        fail_silently=True,
    )

    # 3. Update inventory
    if hasattr(instance, "items"):
        for item in instance.items.all():
            product = item.product
            product.stock -= item.quantity
            product.save()

    # 4. Send to analytics
    try:
        import analytics

        analytics.track(
            user_id=str(instance.user_id) if hasattr(instance, "user_id") else None,
            event="Payment Completed",
            properties={
                "order_id": instance.conversation_id,
                "amount": float(instance.amount),
                "currency": instance.currency,
                "payment_method": instance.card_association,
            },
        )
    except Exception as e:
        logger.warning(f"Analytics tracking failed: {e}")

    # 5. Cache invalidation
    cache_key = f"user_orders_{instance.user_id}"
    cache.delete(cache_key)


@receiver(payment_failed)
def handle_payment_failure(sender, instance, **kwargs):
    """Handle failed payment."""
    logger.warning(f"Payment failed: {instance.payment_id} - {instance.error_message}")

    # Send failure notification
    from django.core.mail import send_mail

    send_mail(
        subject=f"Payment Failed - Order {instance.conversation_id}",
        message=f"""
        Dear {instance.buyer_name},

        Your payment attempt has failed.

        Reason: {instance.error_message}

        Please try again or contact support if the problem persists.
        """,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[instance.buyer_email],
        fail_silently=True,
    )

    # Log for fraud detection
    if instance.error_code in ["5006", "5015"]:  # Card declined or blocked
        logger.warning(
            f"Potential fraud attempt: {instance.buyer_email}, " f"error: {instance.error_code}"
        )


# =============================================================================
# Example 7: Payment Report Generation
# =============================================================================


@login_required
def generate_payment_report(request: HttpRequest) -> HttpResponse:
    """
    Generate detailed payment report for admin/accounting.

    Query params:
    - start_date: Report start date (YYYY-MM-DD)
    - end_date: Report end date (YYYY-MM-DD)
    - format: 'csv' or 'pdf'
    """
    import csv
    from datetime import datetime
    from django.http import HttpResponse
    from myapp.models import Order

    # Check admin permission
    if not request.user.is_staff:
        messages.error(request, "Permission denied")
        return redirect("home")

    try:
        start_date = datetime.strptime(request.GET.get("start_date", ""), "%Y-%m-%d")
        end_date = datetime.strptime(request.GET.get("end_date", ""), "%Y-%m-%d")
    except ValueError:
        messages.error(request, "Invalid date format")
        return redirect("admin_reports")

    # Get payments in date range
    payments = Order.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date, status="success"
    ).order_by("created_at")

    # Generate CSV report
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="payments_{start_date.date()}_to_{end_date.date()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "Payment ID",
            "Conversation ID",
            "Date",
            "Amount",
            "Currency",
            "Buyer Email",
            "Buyer Name",
            "Card Type",
            "Installment",
            "Status",
        ]
    )

    for payment in payments:
        writer.writerow(
            [
                payment.payment_id,
                payment.conversation_id,
                payment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                payment.amount,
                payment.currency,
                payment.buyer_email,
                payment.get_buyer_full_name(),
                payment.card_association or "N/A",
                payment.installment,
                payment.get_status_display(),
            ]
        )

    return response


# =============================================================================
# Example 8: Testing Utilities
# =============================================================================


def create_test_payment(
    user,
    amount: Decimal = Decimal("100.00"),
    status: str = "success",
) -> "Order":
    """
    Create a test payment for development/testing.

    Args:
        user: User instance
        amount: Payment amount
        status: Payment status

    Returns:
        Order instance
    """
    from myapp.models import Order

    order = Order.objects.create(
        user=user,
        conversation_id=f"TEST-{uuid.uuid4()}",
        payment_id=f"test-payment-{uuid.uuid4()}",
        amount=amount,
        paid_amount=amount,
        currency="TRY",
        status=status,
        buyer_email=user.email,
        buyer_name=user.first_name,
        buyer_surname=user.last_name,
        card_last_four_digits="0008",
        card_type="CREDIT_CARD",
        card_association="VISA",
        card_family="Bonus",
        card_bank_name="Test Bank",
    )

    return order


# =============================================================================
# Best Practices Summary
# =============================================================================

"""
BEST PRACTICES:

1. Error Handling:
   - Always use try-except blocks
   - Handle specific exceptions (CardError, PaymentError, ValidationError)
   - Log errors appropriately
   - Provide user-friendly error messages

2. Security:
   - Never log full card numbers
   - Use HTTPS in production
   - Validate all input data
   - Use CSRF protection (except webhooks)
   - Enable webhook signature validation

3. Database:
   - Use transactions for payment operations
   - Use select_related/prefetch_related for performance
   - Add appropriate indexes
   - Enable connection pooling

4. Async Processing:
   - Use Celery for long-running tasks
   - Process webhooks quickly (< 5 seconds)
   - Queue bulk operations
   - Handle retries gracefully

5. Testing:
   - Use sandbox environment for testing
   - Mock Iyzico API calls in unit tests
   - Test error scenarios
   - Verify webhook handling

6. Monitoring:
   - Log all payment operations
   - Set up error alerts
   - Monitor response times
   - Track conversion rates

7. User Experience:
   - Show clear error messages
   - Provide payment status updates
   - Send confirmation emails
   - Display receipts

8. Performance:
   - Cache settings
   - Use database indexes
   - Minimize API calls
   - Optimize queries
"""
