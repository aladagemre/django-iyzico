"""
Admin configuration for shop app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django_iyzico.admin import IyzicoPaymentAdminMixin
from .models import Product, Order, OrderItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model."""

    list_display = [
        'name',
        'price_display',
        'stock',
        'is_active',
        'created_at'
    ]
    list_filter = ['is_active', 'currency', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']

    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'description', 'image')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'currency', 'stock', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def price_display(self, obj):
        """Display formatted price."""
        return obj.get_formatted_price()
    price_display.short_description = 'Price'


class OrderItemInline(admin.TabularInline):
    """Inline for order items."""

    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price', 'currency', 'total_display']
    can_delete = False

    def total_display(self, obj):
        """Display formatted total."""
        if obj.pk:
            return obj.get_formatted_total()
        return '-'
    total_display.short_description = 'Total'


@admin.register(Order)
class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
    """
    Admin for Order model with django-iyzico integration.

    Inherits all payment admin features:
    - Color-coded payment status
    - Bulk refund actions
    - Advanced filtering
    - CSV export
    - Payment details display
    """

    # Combine payment and order fields in list display
    list_display = [
        'order_number',
        'user',
        'order_status',
        'get_payment_status_admin',  # From IyzicoPaymentAdminMixin
        'get_amount_display_admin',  # From IyzicoPaymentAdminMixin
        'get_currency_display_admin',  # From IyzicoPaymentAdminMixin
        'installment_display',
        'created_at'
    ]

    list_filter = [
        'order_status',
        'payment_status',  # From AbstractIyzicoPayment
        'currency',
        'created_at',
        'installment_count'
    ]

    search_fields = [
        'order_number',
        'user__username',
        'user__email',
        'payment_id',
        'conversation_id',
        'buyer_email'
    ]

    readonly_fields = [
        'order_number',
        'created_at',
        'updated_at',
        'payment_id',
        'get_raw_response_display_admin',  # From IyzicoPaymentAdminMixin
    ]

    inlines = [OrderItemInline]

    fieldsets = (
        ('Order Information', {
            'fields': (
                'order_number',
                'user',
                'order_status',
                'notes'
            )
        }),
        ('Shipping Details', {
            'fields': (
                'shipping_address',
                'shipping_city',
                'shipping_country'
            )
        }),
        ('Payment Information', {
            'fields': (
                'payment_id',
                'conversation_id',
                'payment_status',
                'amount',
                'paid_amount',
                'currency',
            ),
            'classes': ('wide',)
        }),
        ('Installment Details', {
            'fields': (
                'installment_count',
                'installment_rate',
            ),
            'classes': ('collapse',)
        }),
        ('Buyer Information', {
            'fields': (
                'buyer_name',
                'buyer_surname',
                'buyer_email',
                'buyer_phone',
            ),
            'classes': ('collapse',)
        }),
        ('Card Information', {
            'fields': (
                'card_association',
                'card_family',
                'card_bank_name',
                'card_last_four_digits',
            ),
            'classes': ('collapse',)
        }),
        ('Raw API Response', {
            'fields': ('get_raw_response_display_admin',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = [
        'mark_as_processing',
        'mark_as_shipped',
        'refund_payment',  # From IyzicoPaymentAdminMixin
    ]

    def installment_display(self, obj):
        """Display installment information."""
        if obj.has_installment():
            if obj.installment_rate == 0:
                return format_html(
                    '<span style="color: green;">{}x (0% Interest)</span>',
                    obj.installment_count
                )
            return format_html(
                '{}x ({}% Interest)',
                obj.installment_count,
                obj.installment_rate
            )
        return '-'
    installment_display.short_description = 'Installment'

    @admin.action(description='Mark selected orders as Processing')
    def mark_as_processing(self, request, queryset):
        """Mark orders as processing."""
        count = queryset.update(order_status='PROCESSING')
        self.message_user(request, f'{count} orders marked as processing.')

    @admin.action(description='Mark selected orders as Shipped')
    def mark_as_shipped(self, request, queryset):
        """Mark orders as shipped."""
        count = queryset.update(order_status='SHIPPED')
        self.message_user(request, f'{count} orders marked as shipped.')


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin for OrderItem model."""

    list_display = [
        'order',
        'product',
        'quantity',
        'price',
        'currency',
        'total_display'
    ]
    list_filter = ['currency', 'order__created_at']
    search_fields = [
        'order__order_number',
        'product__name'
    ]
    readonly_fields = ['total_display']

    def total_display(self, obj):
        """Display formatted total."""
        return obj.get_formatted_total()
    total_display.short_description = 'Total'
