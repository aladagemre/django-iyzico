"""
E-commerce shop models with django-iyzico integration.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse

from django_iyzico.models import AbstractIyzicoPayment


class Product(models.Model):
    """Product model for the shop."""

    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="TRY")
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "shop_products"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"pk": self.pk})

    def is_in_stock(self):
        """Check if product is in stock."""
        return self.stock > 0

    def get_formatted_price(self):
        """Get formatted price with currency symbol."""
        from django_iyzico.currency import format_amount

        return format_amount(self.price, self.currency, show_symbol=True)


class Order(AbstractIyzicoPayment):
    """
    Order model extending AbstractIyzicoPayment for payment processing.

    Inherits all payment fields from django-iyzico:
    - payment_id, conversation_id
    - amount, paid_amount, currency
    - payment_status
    - buyer information
    - card information (masked)
    - timestamps
    - and more...
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    products = models.ManyToManyField(Product, through="OrderItem", related_name="orders")

    # Order-specific fields
    order_number = models.CharField(max_length=100, unique=True, blank=True)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_country = models.CharField(max_length=100, default="Turkey")

    # Payment options
    installment_count = models.IntegerField(default=1)
    installment_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Installment interest rate (%)",
    )

    # Order status
    STATUS_CHOICES = [
        ("CART", "Shopping Cart"),
        ("PENDING_PAYMENT", "Pending Payment"),
        ("PAID", "Paid"),
        ("PROCESSING", "Processing"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
    ]
    order_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="CART")

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "shop_orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["order_status"]),
        ]

    def __str__(self):
        return f"Order #{self.order_number or self.id} - {self.user.username}"

    def save(self, *args, **kwargs):
        # Generate order number if not set
        if not self.order_number:
            import uuid

            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        # Update order status based on payment status
        if self.payment_status == "SUCCESS" and self.order_status == "PENDING_PAYMENT":
            self.order_status = "PAID"
        elif self.payment_status == "FAILED" and self.order_status == "PENDING_PAYMENT":
            self.order_status = "CART"
        elif self.payment_status == "REFUNDED":
            self.order_status = "REFUNDED"

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("order_detail", kwargs={"pk": self.pk})

    def get_total(self):
        """Calculate order total from order items."""
        return sum(item.get_total() for item in self.items.all())

    def get_item_count(self):
        """Get total number of items in order."""
        return sum(item.quantity for item in self.items.all())

    def has_installment(self):
        """Check if order uses installment payment."""
        return self.installment_count > 1

    def get_installment_display(self):
        """Get formatted installment display."""
        if not self.has_installment():
            return "Single Payment"
        return f"{self.installment_count}x Installments"


class OrderItem(models.Model):
    """Order item (product + quantity) in an order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at time of order")
    currency = models.CharField(max_length=3, default="TRY")

    class Meta:
        db_table = "shop_order_items"
        unique_together = ["order", "product"]

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order #{self.order.order_number}"

    def save(self, *args, **kwargs):
        # Store price from product if not set
        if not self.price:
            self.price = self.product.price
            self.currency = self.product.currency
        super().save(*args, **kwargs)

    def get_total(self):
        """Calculate total price for this item."""
        return self.price * self.quantity

    def get_formatted_total(self):
        """Get formatted total with currency symbol."""
        from django_iyzico.currency import format_amount

        return format_amount(self.get_total(), self.currency, show_symbol=True)
