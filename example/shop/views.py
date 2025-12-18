"""
Regular Django views for shop app.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from django_iyzico.client import IyzicoClient
from django_iyzico.exceptions import PaymentError
from django_iyzico.installment_client import InstallmentClient
from django_iyzico.subscription_manager import SubscriptionManager
from django_iyzico.subscription_models import SubscriptionPlan
from django_iyzico.utils import get_client_ip

from .models import Order, OrderItem, Product

logger = logging.getLogger(__name__)


# ============================================================================
# Product Views
# ============================================================================


class ProductListView(ListView):
    """List all active products."""

    model = Product
    template_name = "shop/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        return Product.objects.filter(is_active=True, stock__gt=0)


class ProductDetailView(DetailView):
    """Show product details."""

    model = Product
    template_name = "shop/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.filter(is_active=True)


# ============================================================================
# Checkout Views
# ============================================================================


@login_required
def checkout_view(request):
    """
    Checkout page for payment processing.

    Demonstrates:
    - Creating an order
    - Processing payment with Iyzico
    - Handling payment response
    - Multi-currency support
    - Installment options
    """

    if request.method == "POST":
        # Get form data with safe type conversions
        product_id = request.POST.get("product_id")
        currency = request.POST.get("currency", "TRY")

        # Safe int conversions with validation
        try:
            quantity = int(request.POST.get("quantity", 1))
            if quantity < 1:
                quantity = 1
            elif quantity > 100:  # Reasonable upper limit
                quantity = 100
        except (ValueError, TypeError):
            logger.warning(f"Invalid quantity value: {request.POST.get('quantity')}")
            quantity = 1

        try:
            installment_count = int(request.POST.get("installment", 1))
            if installment_count < 1:
                installment_count = 1
            elif installment_count > 12:  # Max 12 installments
                installment_count = 12
        except (ValueError, TypeError):
            logger.warning(f"Invalid installment value: {request.POST.get('installment')}")
            installment_count = 1

        # Get product
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # Check stock
        if product.stock < quantity:
            messages.error(request, "Insufficient stock.")
            return redirect("product_detail", pk=product_id)

        # Calculate total
        total = product.price * quantity

        # Create order
        order = Order.objects.create(
            user=request.user,
            amount=total,
            currency=currency,
            order_status="PENDING_PAYMENT",
            installment_count=installment_count,
            conversation_id=f"ORDER-{Order.objects.count() + 1}",
            shipping_address=request.POST.get("address", ""),
            shipping_city=request.POST.get("city", ""),
            shipping_country="Turkey",
            buyer_name=request.user.first_name or "Customer",
            buyer_surname=request.user.last_name or "User",
            buyer_email=request.user.email,
        )

        # Add order item
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price,
            currency=product.currency,
        )

        # Prepare payment data
        client = IyzicoClient()

        # Order data (required)
        order_data = {
            "price": str(total),
            "paidPrice": str(total),
            "currency": currency,
            "basketId": order.order_number,
            "conversationId": order.conversation_id,
            "installment": installment_count,
        }

        # Payment card data (required)
        payment_card = {
            "cardHolderName": request.POST.get("card_holder"),
            "cardNumber": request.POST.get("card_number"),
            "expireMonth": request.POST.get("expire_month"),
            "expireYear": request.POST.get("expire_year"),
            "cvc": request.POST.get("cvc"),
        }

        # Validate required card fields before API call
        required_card_fields = ["card_holder", "card_number", "expire_month", "expire_year", "cvc"]
        missing_fields = [f for f in required_card_fields if not request.POST.get(f)]
        if missing_fields:
            logger.warning(f"Missing card fields in checkout: {missing_fields}")
            messages.error(request, "Please fill in all card details.")
            return redirect("checkout")

        # Basic card number validation (length check only - actual validation done by Iyzico)
        card_number = request.POST.get("card_number", "").replace(" ", "").replace("-", "")
        if not card_number.isdigit() or len(card_number) < 13 or len(card_number) > 19:
            messages.error(request, "Invalid card number format.")
            return redirect("checkout")

        # Buyer information (required)
        # IMPORTANT: In production, identity_number should come from user profile
        # This is required for Turkish regulations.
        identity_number = request.POST.get("identity_number")
        if not identity_number:
            messages.error(request, "Identity number is required for Turkish regulations.")
            return redirect("checkout")

        buyer = {
            "id": str(request.user.id),
            "name": request.user.first_name or "Customer",
            "surname": request.user.last_name or "User",
            "email": request.user.email,
            "identityNumber": identity_number,
            "registrationAddress": request.POST.get("address", "Address"),
            "city": request.POST.get("city", "Istanbul"),
            "country": "Turkey",
            "zipCode": "34000",
        }

        # Billing address (required)
        billing_address = {
            "address": request.POST.get("address", "Address"),
            "city": request.POST.get("city", "Istanbul"),
            "country": "Turkey",
            "zipCode": "34000",
        }

        # Shipping address (optional, defaults to billing address)
        shipping_address = {
            "address": request.POST.get("address", "Address"),
            "city": request.POST.get("city", "Istanbul"),
            "country": "Turkey",
            "zipCode": "34000",
        }

        try:
            # Process payment with correct method signature
            response = client.create_payment(
                order_data=order_data,
                payment_card=payment_card,
                buyer=buyer,
                billing_address=billing_address,
                shipping_address=shipping_address,
            )

            if response.is_successful():
                # Update order from response
                order.update_from_response(response)

                # Reduce stock
                product.stock -= quantity
                product.save()

                messages.success(request, "Payment successful!")
                return redirect("order_success", order_id=order.id)
            else:
                # Payment failed
                order.payment_status = "FAILED"
                order.error_message = response.error_message
                order.save()
                messages.error(request, f"Payment failed: {response.error_message}")
                return redirect("checkout")

        except PaymentError as e:
            logger.error(f"Payment error in checkout: {e}", exc_info=True)
            messages.error(request, f"Payment error: {str(e)}")
            return redirect("checkout")

    # GET request - show checkout form
    context = {
        "products": Product.objects.filter(is_active=True, stock__gt=0),
    }
    return render(request, "shop/checkout.html", context)


@login_required
def get_installment_options(request):
    """
    AJAX view to get installment options for a card BIN.

    Demonstrates:
    - InstallmentClient usage
    - BIN-based installment lookup
    - JSON response
    """

    if request.method == "POST":
        bin_number = request.POST.get("bin_number", "")[:6]

        # Safe Decimal conversion
        try:
            price = Decimal(request.POST.get("price", "0"))
            if price <= 0:
                return JsonResponse({"error": "Invalid price"}, status=400)
        except (InvalidOperation, ValueError, TypeError) as e:
            logger.warning(f"Invalid price value: {request.POST.get('price')} - {e}")
            return JsonResponse({"error": "Invalid price format"}, status=400)

        if len(bin_number) != 6:
            return JsonResponse({"error": "Invalid BIN number"}, status=400)

        try:
            client = InstallmentClient()
            options = client.get_installment_info(bin_number, price)

            # Convert to JSON-serializable format
            options_data = [
                {
                    "installment_count": opt.installment_count,
                    "installment_price": str(opt.installment_price),
                    "total_price": str(opt.total_price),
                    "installment_rate": str(opt.installment_rate),
                    "is_zero_interest": opt.installment_rate == 0,
                }
                for opt in options
            ]

            return JsonResponse({"options": options_data})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "POST required"}, status=405)


@login_required
def order_success_view(request, order_id):
    """Show order success page."""

    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "shop/order_success.html", {"order": order})


# ============================================================================
# Order Management Views
# ============================================================================


class OrderListView(LoginRequiredMixin, ListView):
    """List user's orders."""

    model = Order
    template_name = "shop/order_list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).exclude(order_status="CART")


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Show order details."""

    model = Order
    template_name = "shop/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


# ============================================================================
# Subscription Views
# ============================================================================


@login_required
def subscription_plans_view(request):
    """
    Show available subscription plans.

    Demonstrates:
    - SubscriptionPlan listing
    - Subscription creation
    """

    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(request, "shop/subscription_plans.html", {"plans": plans})


@login_required
def subscribe_view(request, plan_id):
    """
    Subscribe to a plan.

    Demonstrates:
    - SubscriptionManager usage
    - Subscription creation with payment
    - Trial period handling
    """

    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

    if request.method == "POST":
        manager = SubscriptionManager()

        payment_method = {
            "cardHolderName": request.POST.get("card_holder"),
            "cardNumber": request.POST.get("card_number"),
            "expireMonth": request.POST.get("expire_month"),
            "expireYear": request.POST.get("expire_year"),
            "cvc": request.POST.get("cvc"),
        }

        # IMPORTANT: In production, identity_number should come from user profile
        # This is required for Turkish regulations.
        identity_number = request.POST.get("identity_number")
        if not identity_number:
            messages.error(request, "Identity number is required for Turkish regulations.")
            return redirect("subscribe", plan_id=plan_id)

        buyer_info = {
            "name": request.user.first_name or "Customer",
            "surname": request.user.last_name or "User",
            "email": request.user.email,
            "identityNumber": identity_number,
            "registrationAddress": request.POST.get("address", "Address"),
            "city": request.POST.get("city", "Istanbul"),
            "country": "Turkey",
            "zipCode": "34000",
        }

        try:
            subscription = manager.create_subscription(
                plan=plan, user=request.user, payment_method=payment_method, buyer_info=buyer_info
            )

            if subscription.status in ["ACTIVE", "TRIALING"]:
                messages.success(request, "Subscription activated successfully!")
                return redirect("subscription_detail", subscription_id=subscription.id)
            else:
                messages.error(request, "Subscription activation failed.")
                return redirect("subscription_plans")

        except Exception as e:
            logger.exception(f"Error creating subscription for plan {plan_id}: {e}")
            messages.error(request, "An error occurred while processing your subscription.")
            return redirect("subscribe", plan_id=plan_id)

    return render(request, "shop/subscribe.html", {"plan": plan})


@login_required
def subscription_detail_view(request, subscription_id):
    """Show subscription details."""

    from django_iyzico.subscription_models import Subscription

    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)

    return render(request, "shop/subscription_detail.html", {"subscription": subscription})


# ============================================================================
# Refund Views
# ============================================================================


@login_required
def refund_request_view(request, order_id):
    """
    Request a refund for an order.

    Demonstrates:
    - Refund processing
    - Partial vs full refunds
    """

    order = get_object_or_404(Order, id=order_id, user=request.user)

    if not order.can_be_refunded():
        messages.error(request, "This order cannot be refunded.")
        return redirect("order_detail", pk=order_id)

    if request.method == "POST":
        refund_amount_str = request.POST.get("refund_amount")
        reason = request.POST.get("reason", "")

        # Get client IP address for audit trail (uses centralized function)
        ip_address = get_client_ip(request) or "127.0.0.1"

        try:
            refund_amount = None
            if refund_amount_str:
                # Safe Decimal conversion for partial refund
                try:
                    refund_amount = Decimal(refund_amount_str)
                    if refund_amount <= 0:
                        messages.error(request, "Refund amount must be greater than zero.")
                        return render(request, "shop/refund_request.html", {"order": order})
                    # Validate refund amount doesn't exceed order amount
                    if refund_amount > order.amount:
                        messages.error(request, "Refund amount cannot exceed order amount.")
                        return render(request, "shop/refund_request.html", {"order": order})
                except (InvalidOperation, ValueError, TypeError) as e:
                    logger.warning(f"Invalid refund amount: {refund_amount_str} - {e}")
                    messages.error(request, "Invalid refund amount format.")
                    return render(request, "shop/refund_request.html", {"order": order})

            if refund_amount:
                # Partial refund
                response = order.process_refund(
                    ip_address=ip_address, amount=refund_amount, reason=reason
                )
            else:
                # Full refund
                response = order.process_refund(ip_address=ip_address, reason=reason)

            if response.is_successful():
                messages.success(request, "Refund processed successfully!")
                return redirect("order_detail", pk=order_id)
            else:
                messages.error(request, f"Refund failed: {response.error_message}")

        except Exception as e:
            logger.exception(f"Error processing refund for order {order_id}: {e}")
            messages.error(request, "An error occurred while processing your refund.")

    return render(request, "shop/refund_request.html", {"order": order})
