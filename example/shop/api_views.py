"""
Django REST Framework API views for shop app.
"""

from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django_iyzico.client import IyzicoClient
from django_iyzico.exceptions import PaymentError
from django_iyzico.installment_client import InstallmentClient
from .models import Product, Order, OrderItem
from .serializers import (
    ProductSerializer,
    OrderSerializer,
    PaymentRequestSerializer,
    RefundRequestSerializer,
)


class StandardResultsPagination(PageNumberPagination):
    """Standard pagination for API views."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ============================================================================
# Product API ViewSet
# ============================================================================


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet for products.

    list: Get all active products
    retrieve: Get a specific product
    """

    queryset = Product.objects.filter(is_active=True, stock__gt=0)
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    pagination_class = StandardResultsPagination
    filterset_fields = ["currency", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at", "name"]
    ordering = ["-created_at"]


# ============================================================================
# Order API ViewSet
# ============================================================================


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet for orders.

    list: Get user's orders
    retrieve: Get a specific order
    refund: Process a refund
    """

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filterset_fields = ["order_status", "payment_status", "currency"]
    search_fields = ["order_number", "buyer_email"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Return only orders for the current user."""
        return Order.objects.filter(user=self.request.user).exclude(order_status="CART")

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        """
        Process a refund for an order.

        POST /api/orders/{id}/refund/
        {
            "amount": "50.00",  # Optional, leave empty for full refund
            "reason": "Customer request"  # Optional
        }
        """

        order = self.get_object()

        # Check if order can be refunded
        if not order.can_be_refunded():
            return Response(
                {"error": "This order cannot be refunded"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Validate request data
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refund_amount = serializer.validated_data.get("amount")
        reason = serializer.validated_data.get("reason", "")

        try:
            # Process refund
            if refund_amount:
                response = order.process_refund(amount=refund_amount, reason=reason)
            else:
                response = order.process_refund(reason=reason)

            if response.is_successful():
                return Response(
                    {
                        "status": "success",
                        "message": "Refund processed successfully",
                        "refund_amount": str(refund_amount) if refund_amount else str(order.amount),
                        "order": OrderSerializer(order).data,
                    }
                )
            else:
                return Response(
                    {"error": response.error_message}, status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# Payment API Views
# ============================================================================


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_payment(request):
    """
    Create a payment for an order.

    POST /api/payments/create/
    {
        "product_id": 1,
        "quantity": 2,
        "currency": "TRY",
        "installment": 1,
        "card_holder_name": "John Doe",
        "card_number": "5528790000000008",
        "expire_month": "12",
        "expire_year": "2030",
        "cvc": "123",
        "shipping_address": "123 Main St",
        "shipping_city": "Istanbul",
        "shipping_country": "Turkey"
    }

    Demonstrates:
    - Payment creation via API
    - Order creation
    - Iyzico integration
    - Multi-currency support
    - Installment payment
    """

    # Validate request data
    serializer = PaymentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Get product
    product = get_object_or_404(Product, id=data["product_id"], is_active=True)

    # Check stock
    if product.stock < data["quantity"]:
        return Response({"error": "Insufficient stock"}, status=status.HTTP_400_BAD_REQUEST)

    # Calculate total
    total = product.price * data["quantity"]

    # Create order
    order = Order.objects.create(
        user=request.user,
        amount=total,
        currency=data["currency"],
        order_status="PENDING_PAYMENT",
        installment_count=data["installment"],
        conversation_id=f"API-ORDER-{Order.objects.count() + 1}",
        shipping_address=data["shipping_address"],
        shipping_city=data["shipping_city"],
        shipping_country=data["shipping_country"],
        buyer_name=request.user.first_name or "Customer",
        buyer_surname=request.user.last_name or "User",
        buyer_email=request.user.email,
    )

    # Add order item
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=data["quantity"],
        price=product.price,
        currency=product.currency,
    )

    # Prepare payment data
    client = IyzicoClient()

    payment_data = {
        "price": str(total),
        "paidPrice": str(total),
        "currency": data["currency"],
        "basketId": order.order_number,
        "installment": data["installment"],
        "paymentCard": {
            "cardHolderName": data["card_holder_name"],
            "cardNumber": data["card_number"],
            "expireMonth": data["expire_month"],
            "expireYear": data["expire_year"],
            "cvc": data["cvc"],
        },
        "buyer": {
            "id": str(request.user.id),
            "name": request.user.first_name or "Customer",
            "surname": request.user.last_name or "User",
            "email": request.user.email,
            "identityNumber": "11111111111",
            "registrationAddress": data["shipping_address"],
            "city": data["shipping_city"],
            "country": data["shipping_country"],
            "zipCode": "34000",
        },
        "shippingAddress": {
            "address": data["shipping_address"],
            "city": data["shipping_city"],
            "country": data["shipping_country"],
            "zipCode": "34000",
        },
        "billingAddress": {
            "address": data["shipping_address"],
            "city": data["shipping_city"],
            "country": data["shipping_country"],
            "zipCode": "34000",
        },
    }

    try:
        # Process payment
        response = client.create_payment(payment_data)

        if response.is_successful():
            # Update order from response
            order.update_from_response(response)

            # Reduce stock
            product.stock -= data["quantity"]
            product.save()

            return Response(
                {
                    "status": "success",
                    "message": "Payment processed successfully",
                    "order": OrderSerializer(order).data,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            # Payment failed
            order.payment_status = "FAILED"
            order.error_message = response.error_message
            order.save()

            return Response(
                {"status": "error", "message": response.error_message, "order_id": order.id},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except PaymentError as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_installment_options(request):
    """
    Get installment options for a card BIN and price.

    POST /api/installments/options/
    {
        "bin_number": "552879",
        "price": "1000.00"
    }

    Demonstrates:
    - InstallmentClient usage via API
    - BIN-based installment lookup
    """

    bin_number = request.data.get("bin_number", "")[:6]
    price_str = request.data.get("price", "0")

    if len(bin_number) != 6:
        return Response(
            {"error": "BIN number must be 6 digits"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        price = Decimal(price_str)
    except (ValueError, TypeError):
        return Response({"error": "Invalid price format"}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({"options": options_data})

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_stats(request):
    """
    Get payment statistics for the current user.

    GET /api/payments/stats/

    Demonstrates:
    - Payment analytics
    - Multi-currency aggregation
    """

    user_orders = Order.objects.filter(user=request.user)

    # Calculate stats
    total_orders = user_orders.count()
    successful_orders = user_orders.filter(payment_status="SUCCESS").count()
    failed_orders = user_orders.filter(payment_status="FAILED").count()
    pending_orders = user_orders.filter(payment_status="PENDING").count()

    # Calculate total spent per currency
    from django.db.models import Sum

    currency_totals = (
        user_orders.filter(payment_status="SUCCESS")
        .values("currency")
        .annotate(total=Sum("amount"))
    )

    return Response(
        {
            "total_orders": total_orders,
            "successful_orders": successful_orders,
            "failed_orders": failed_orders,
            "pending_orders": pending_orders,
            "total_spent_by_currency": {
                item["currency"]: str(item["total"]) for item in currency_totals
            },
        }
    )
