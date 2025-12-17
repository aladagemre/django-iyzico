"""
Django admin interface for django-iyzico.

Provides a comprehensive admin interface for payment management and monitoring.
"""

import csv
from typing import Any, List, Optional

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from .models import PaymentStatus


class IyzicoPaymentAdminMixin:
    """
    Reusable admin mixin for Iyzico payment models.

    Add this mixin to your ModelAdmin to get full-featured payment administration:

    Example:
        from django.contrib import admin
        from django_iyzico.admin import IyzicoPaymentAdminMixin
        from .models import Order

        @admin.register(Order)
        class OrderAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
            # Add any order-specific fields to list_display
            list_display = IyzicoPaymentAdminMixin.list_display + ['product', 'quantity']

    Features:
    - Color-coded status badges
    - Searchable by payment_id, conversation_id, buyer_email
    - Filterable by status, created_at, currency
    - Read-only fields (for data integrity)
    - Organized fieldsets
    - Admin actions (refund, export CSV)
    - Link to Iyzico dashboard
    """

    # List display configuration
    list_display = [
        'payment_id',
        'get_status_badge',
        'get_amount_display_admin',
        'buyer_email',
        'get_buyer_name',
        'get_card_display_admin',
        'created_at',
    ]

    # List filters
    list_filter = [
        'status',
        'created_at',
        'currency',
        'card_association',
        'card_type',
    ]

    # Search fields
    search_fields = [
        'payment_id',
        'conversation_id',
        'buyer_email',
        'buyer_name',
        'buyer_surname',
    ]

    # Read-only fields (all except status for manual updates)
    readonly_fields = [
        'payment_id',
        'conversation_id',
        'amount',
        'paid_amount',
        'currency',
        'locale',
        'card_last_four_digits',
        'card_type',
        'card_association',
        'card_family',
        'card_bank_name',
        'card_bank_code',
        'installment',
        'buyer_email',
        'buyer_name',
        'buyer_surname',
        'error_code',
        'error_message',
        'error_group',
        'get_raw_response_display',
        'created_at',
        'updated_at',
        'get_iyzico_dashboard_link',
    ]

    # Date hierarchy
    date_hierarchy = 'created_at'

    # Ordering
    ordering = ['-created_at']

    # Items per page
    list_per_page = 50

    # Fieldsets for organized display
    fieldsets = [
        (
            _('Payment Information'),
            {
                'fields': (
                    'payment_id',
                    'conversation_id',
                    'status',
                    'get_iyzico_dashboard_link',
                )
            }
        ),
        (
            _('Amounts'),
            {
                'fields': (
                    'amount',
                    'paid_amount',
                    'currency',
                    'installment',
                )
            }
        ),
        (
            _('Buyer Information'),
            {
                'fields': (
                    'buyer_email',
                    'buyer_name',
                    'buyer_surname',
                )
            }
        ),
        (
            _('Card Information'),
            {
                'fields': (
                    'card_last_four_digits',
                    'card_type',
                    'card_association',
                    'card_family',
                    'card_bank_name',
                    'card_bank_code',
                ),
                'classes': ('collapse',),
            }
        ),
        (
            _('Status & Errors'),
            {
                'fields': (
                    'error_code',
                    'error_message',
                    'error_group',
                ),
                'classes': ('collapse',),
            }
        ),
        (
            _('Metadata'),
            {
                'fields': (
                    'locale',
                    'created_at',
                    'updated_at',
                    'get_raw_response_display',
                ),
                'classes': ('collapse',),
            }
        ),
    ]

    # Actions
    actions = ['refund_payment', 'export_csv']

    def get_status_badge(self, obj: Any) -> str:
        """
        Display colored status badge.

        Args:
            obj: Payment instance

        Returns:
            HTML badge with colored status
        """
        status_colors = {
            PaymentStatus.SUCCESS: '#28a745',      # Green
            PaymentStatus.FAILED: '#dc3545',       # Red
            PaymentStatus.PENDING: '#ffc107',      # Yellow/Orange
            PaymentStatus.PROCESSING: '#17a2b8',   # Blue
            PaymentStatus.REFUND_PENDING: '#fd7e14', # Orange
            PaymentStatus.REFUNDED: '#6c757d',     # Gray
            PaymentStatus.CANCELLED: '#343a40',    # Dark gray
        }

        color = status_colors.get(obj.status, '#6c757d')
        status_display = obj.get_status_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            status_display
        )

    get_status_badge.short_description = _('Status')
    get_status_badge.admin_order_field = 'status'

    def get_amount_display_admin(self, obj: Any) -> str:
        """
        Display formatted amount with currency.

        Args:
            obj: Payment instance

        Returns:
            Formatted amount string
        """
        if obj.paid_amount and obj.paid_amount != obj.amount:
            return format_html(
                '{} {} <span style="color: #666;">(paid: {} {})</span>',
                obj.amount,
                obj.currency,
                obj.paid_amount,
                obj.currency
            )
        return f"{obj.amount} {obj.currency}"

    get_amount_display_admin.short_description = _('Amount')
    get_amount_display_admin.admin_order_field = 'amount'

    def get_buyer_name(self, obj: Any) -> str:
        """
        Get buyer's full name.

        Args:
            obj: Payment instance

        Returns:
            Full name or dash if not available
        """
        full_name = obj.get_buyer_full_name()
        return full_name if full_name else '-'

    get_buyer_name.short_description = _('Buyer Name')
    get_buyer_name.admin_order_field = 'buyer_name'

    def get_card_display_admin(self, obj: Any) -> str:
        """
        Display card information safely.

        Args:
            obj: Payment instance

        Returns:
            Masked card display string
        """
        return obj.get_card_display() or '-'

    get_card_display_admin.short_description = _('Card')

    def get_raw_response_display(self, obj: Any) -> str:
        """
        Display raw response as formatted JSON.

        Args:
            obj: Payment instance

        Returns:
            HTML formatted JSON
        """
        if not obj.raw_response:
            return '-'

        import json

        try:
            # Pretty print JSON
            formatted = json.dumps(obj.raw_response, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; '
                'border-radius: 5px; max-height: 400px; overflow: auto;">{}</pre>',
                formatted
            )
        except (TypeError, ValueError):
            return str(obj.raw_response)

    get_raw_response_display.short_description = _('Raw Response')

    def get_iyzico_dashboard_link(self, obj: Any) -> str:
        """
        Get link to Iyzico dashboard for this payment.

        Args:
            obj: Payment instance

        Returns:
            HTML link to Iyzico dashboard
        """
        if not obj.payment_id:
            return '-'

        # Iyzico merchant dashboard URL (update if different)
        dashboard_url = f"https://merchant.iyzipay.com/payment/{obj.payment_id}"

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">'
            'View in Iyzico Dashboard →</a>',
            dashboard_url
        )

    get_iyzico_dashboard_link.short_description = _('Iyzico Dashboard')

    def refund_payment(self, request: HttpRequest, queryset: QuerySet) -> None:
        """
        Admin action to refund payments.

        Args:
            request: HTTP request
            queryset: Selected payment objects
        """
        # Import here to avoid circular import
        from .client import IyzicoClient

        client = IyzicoClient()
        refunded_count = 0
        failed_count = 0

        for payment in queryset:
            # Check if payment can be refunded
            if not payment.can_be_refunded():
                self.message_user(
                    request,
                    f"Payment {payment.payment_id} cannot be refunded (status: {payment.get_status_display()})",
                    level='warning'
                )
                failed_count += 1
                continue

            try:
                # Check if payment has process_refund method
                if hasattr(payment, 'process_refund'):
                    payment.process_refund()
                    refunded_count += 1
                else:
                    self.message_user(
                        request,
                        f"Payment {payment.payment_id} model does not support refunds. "
                        "Please implement process_refund() method.",
                        level='error'
                    )
                    failed_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to refund payment {payment.payment_id}: {str(e)}",
                    level='error'
                )
                failed_count += 1

        # Success message
        if refunded_count > 0:
            self.message_user(
                request,
                f"Successfully refunded {refunded_count} payment(s).",
                level='success'
            )

        if failed_count > 0:
            self.message_user(
                request,
                f"Failed to refund {failed_count} payment(s).",
                level='warning'
            )

    refund_payment.short_description = _('Refund selected payments')

    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        """
        Admin action to export payments to CSV.

        Args:
            request: HTTP request
            queryset: Selected payment objects

        Returns:
            CSV file response
        """
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="iyzico_payments.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow([
            'Payment ID',
            'Conversation ID',
            'Status',
            'Amount',
            'Paid Amount',
            'Currency',
            'Installment',
            'Buyer Email',
            'Buyer Name',
            'Buyer Surname',
            'Card Last 4',
            'Card Association',
            'Card Type',
            'Card Bank',
            'Error Code',
            'Error Message',
            'Created At',
            'Updated At',
        ])

        # Write data
        for payment in queryset:
            writer.writerow([
                payment.payment_id or '',
                payment.conversation_id or '',
                payment.get_status_display(),
                str(payment.amount),
                str(payment.paid_amount) if payment.paid_amount else '',
                payment.currency,
                payment.installment,
                payment.buyer_email or '',
                payment.buyer_name or '',
                payment.buyer_surname or '',
                payment.card_last_four_digits or '',
                payment.card_association or '',
                payment.card_type or '',
                payment.card_bank_name or '',
                payment.error_code or '',
                payment.error_message or '',
                payment.created_at.isoformat() if payment.created_at else '',
                payment.updated_at.isoformat() if payment.updated_at else '',
            ])

        self.message_user(
            request,
            f"Exported {queryset.count()} payment(s) to CSV.",
            level='success'
        )

        return response

    export_csv.short_description = _('Export selected payments to CSV')

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Optional[Any] = None
    ) -> bool:
        """
        Prevent deletion of successful payments.

        Args:
            request: HTTP request
            obj: Payment instance (if checking for specific object)

        Returns:
            True if deletion is allowed, False otherwise
        """
        # Allow deletion in general (list view)
        if obj is None:
            return True

        # Prevent deletion of successful payments
        if obj.status == PaymentStatus.SUCCESS:
            return False

        # Allow deletion of other statuses
        return True

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Optimize queryset with select_related if available.

        Args:
            request: HTTP request

        Returns:
            Optimized queryset
        """
        qs = super().get_queryset(request)

        # Add any select_related or prefetch_related here if needed
        # For now, the base queryset is sufficient

        return qs
