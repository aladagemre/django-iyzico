"""
Django REST Framework serializers for shop app.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Product, Order, OrderItem


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""

    formatted_price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'currency',
            'formatted_price',
            'image',
            'stock',
            'in_stock',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_formatted_price(self, obj):
        """Get formatted price with currency symbol."""
        return obj.get_formatted_price()

    def get_in_stock(self, obj):
        """Check if product is in stock."""
        return obj.is_in_stock()


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    formatted_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'quantity',
            'price',
            'currency',
            'formatted_total'
        ]

    def get_formatted_total(self, obj):
        """Get formatted total."""
        return obj.get_formatted_total()


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""

    items = OrderItemSerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    payment_status_display = serializers.CharField(
        source='get_payment_status_display',
        read_only=True
    )
    order_status_display = serializers.CharField(
        source='get_order_status_display',
        read_only=True
    )
    total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            # Order fields
            'id',
            'order_number',
            'user',
            'user_email',
            'order_status',
            'order_status_display',
            'items',
            'total',
            'item_count',

            # Payment fields
            'payment_id',
            'conversation_id',
            'payment_status',
            'payment_status_display',
            'amount',
            'paid_amount',
            'currency',
            'formatted_amount',

            # Installment fields
            'installment_count',
            'installment_rate',

            # Buyer fields
            'buyer_name',
            'buyer_surname',
            'buyer_email',
            'buyer_phone',

            # Shipping fields
            'shipping_address',
            'shipping_city',
            'shipping_country',

            # Timestamps
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'order_number',
            'payment_id',
            'payment_status',
            'paid_amount',
            'created_at',
            'updated_at'
        ]

    def get_formatted_amount(self, obj):
        """Get formatted amount."""
        return obj.get_formatted_amount(show_symbol=True, show_code=True)

    def get_total(self, obj):
        """Get order total."""
        return str(obj.get_total())

    def get_item_count(self, obj):
        """Get item count."""
        return obj.get_item_count()


class PaymentRequestSerializer(serializers.Serializer):
    """Serializer for payment requests."""

    # Order details
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    currency = serializers.ChoiceField(
        choices=['TRY', 'USD', 'EUR', 'GBP'],
        default='TRY'
    )
    installment = serializers.IntegerField(min_value=1, default=1)

    # Card details
    card_holder_name = serializers.CharField(max_length=100)
    card_number = serializers.CharField(max_length=19)
    expire_month = serializers.CharField(max_length=2)
    expire_year = serializers.CharField(max_length=4)
    cvc = serializers.CharField(max_length=4)

    # Shipping details
    shipping_address = serializers.CharField(max_length=500)
    shipping_city = serializers.CharField(max_length=100)
    shipping_country = serializers.CharField(max_length=100, default='Turkey')

    def validate_card_number(self, value):
        """Validate card number format."""
        # Remove spaces and dashes
        card_number = value.replace(' ', '').replace('-', '')

        # Check length
        if not 13 <= len(card_number) <= 19:
            raise serializers.ValidationError('Invalid card number length')

        # Check if all digits
        if not card_number.isdigit():
            raise serializers.ValidationError('Card number must contain only digits')

        return card_number

    def validate_expire_month(self, value):
        """Validate expiry month."""
        try:
            month = int(value)
            if not 1 <= month <= 12:
                raise serializers.ValidationError('Month must be between 1 and 12')
        except ValueError:
            raise serializers.ValidationError('Invalid month format')
        return value

    def validate_expire_year(self, value):
        """Validate expiry year."""
        try:
            year = int(value)
            if year < 2025:
                raise serializers.ValidationError('Card has expired')
        except ValueError:
            raise serializers.ValidationError('Invalid year format')
        return value


class RefundRequestSerializer(serializers.Serializer):
    """Serializer for refund requests."""

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        help_text="Amount to refund (leave empty for full refund)"
    )
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Reason for refund"
    )

    def validate_amount(self, value):
        """Validate refund amount."""
        if value is not None and value <= 0:
            raise serializers.ValidationError('Amount must be positive')
        return value
