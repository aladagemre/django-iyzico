"""
Django admin interface for django-iyzico.

Provides a comprehensive admin interface for payment management and monitoring.
"""

import logging
from typing import Any, Optional

from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import PaymentStatus

logger = logging.getLogger(__name__)


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
        "payment_id",
        "get_status_badge",
        "get_amount_display_admin",
        "get_installment_display_admin",  # Added in v0.2.0
        "buyer_email",
        "get_buyer_name",
        "get_card_display_admin",
        "created_at",
    ]

    # List filters
    list_filter = [
        "status",
        "created_at",
        "currency",
        "card_association",
        "card_type",
        "installment",  # Added in v0.2.0
    ]

    # Search fields
    search_fields = [
        "payment_id",
        "conversation_id",
        "buyer_email",
        "buyer_name",
        "buyer_surname",
    ]

    # Read-only fields (all except status for manual updates)
    readonly_fields = [
        "payment_id",
        "conversation_id",
        "amount",
        "paid_amount",
        "currency",
        "locale",
        "card_last_four_digits",
        "card_type",
        "card_association",
        "card_family",
        "card_bank_name",
        "card_bank_code",
        "installment",
        "installment_rate",  # Added in v0.2.0
        "monthly_installment_amount",  # Added in v0.2.0
        "total_with_installment",  # Added in v0.2.0
        "bin_number",  # Added in v0.2.0
        "get_installment_details_admin",  # Added in v0.2.0
        "buyer_email",
        "buyer_name",
        "buyer_surname",
        "error_code",
        "error_message",
        "error_group",
        "get_raw_response_display",
        "created_at",
        "updated_at",
        "get_iyzico_dashboard_link",
    ]

    # Date hierarchy
    date_hierarchy = "created_at"

    # Ordering
    ordering = ["-created_at"]

    # Items per page
    list_per_page = 50

    # Fieldsets for organized display
    fieldsets = [
        (
            _("Payment Information"),
            {
                "fields": (
                    "payment_id",
                    "conversation_id",
                    "status",
                    "get_iyzico_dashboard_link",
                )
            },
        ),
        (
            _("Amounts"),
            {
                "fields": (
                    "amount",
                    "paid_amount",
                    "currency",
                    "installment",
                )
            },
        ),
        (
            _("Installment Details"),  # Added in v0.2.0
            {
                "fields": (
                    "installment_rate",
                    "monthly_installment_amount",
                    "total_with_installment",
                    "bin_number",
                    "get_installment_details_admin",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Buyer Information"),
            {
                "fields": (
                    "buyer_email",
                    "buyer_name",
                    "buyer_surname",
                )
            },
        ),
        (
            _("Card Information"),
            {
                "fields": (
                    "card_last_four_digits",
                    "card_type",
                    "card_association",
                    "card_family",
                    "card_bank_name",
                    "card_bank_code",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Status & Errors"),
            {
                "fields": (
                    "error_code",
                    "error_message",
                    "error_group",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "locale",
                    "created_at",
                    "updated_at",
                    "get_raw_response_display",
                ),
                "classes": ("collapse",),
            },
        ),
    ]

    # Actions
    actions = ["refund_payment", "export_csv"]

    def get_status_badge(self, obj: Any) -> str:
        """
        Display colored status badge.

        Args:
            obj: Payment instance

        Returns:
            HTML badge with colored status
        """
        status_colors = {
            PaymentStatus.SUCCESS: "#28a745",  # Green
            PaymentStatus.FAILED: "#dc3545",  # Red
            PaymentStatus.PENDING: "#ffc107",  # Yellow/Orange
            PaymentStatus.PROCESSING: "#17a2b8",  # Blue
            PaymentStatus.REFUND_PENDING: "#fd7e14",  # Orange
            PaymentStatus.REFUNDED: "#6c757d",  # Gray
            PaymentStatus.CANCELLED: "#343a40",  # Dark gray
        }

        color = status_colors.get(obj.status, "#6c757d")
        status_display = obj.get_status_display()

        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            status_display,
        )

    get_status_badge.short_description = _("Status")
    get_status_badge.admin_order_field = "status"

    def get_amount_display_admin(self, obj: Any) -> str:
        """
        Display formatted amount with currency symbol and code.

        Args:
            obj: Payment instance

        Returns:
            Formatted amount string with currency symbol
        """
        # Try to get formatted amount with symbol
        try:
            if hasattr(obj, "get_formatted_amount"):
                formatted = obj.get_formatted_amount(show_symbol=True, show_code=False)

                # Show paid amount if different
                if obj.paid_amount and obj.paid_amount != obj.amount:
                    paid_formatted = obj.get_formatted_paid_amount(
                        show_symbol=True, show_code=False
                    )
                    return format_html(
                        '{} <span style="color: #666;">(paid: {})</span>', formatted, paid_formatted
                    )

                return formatted
        except Exception:
            # Fallback to simple display
            pass

        # Fallback display without symbol
        if obj.paid_amount and obj.paid_amount != obj.amount:
            return format_html(
                '{} {} <span style="color: #666;">(paid: {} {})</span>',
                obj.amount,
                obj.currency,
                obj.paid_amount,
                obj.currency,
            )
        return f"{obj.amount} {obj.currency}"

    get_amount_display_admin.short_description = _("Amount")
    get_amount_display_admin.admin_order_field = "amount"

    def get_buyer_name(self, obj: Any) -> str:
        """
        Get buyer's full name.

        Args:
            obj: Payment instance

        Returns:
            Full name or dash if not available
        """
        full_name = obj.get_buyer_full_name()
        return full_name if full_name else "-"

    get_buyer_name.short_description = _("Buyer Name")
    get_buyer_name.admin_order_field = "buyer_name"

    def get_card_display_admin(self, obj: Any) -> str:
        """
        Display card information safely.

        Args:
            obj: Payment instance

        Returns:
            Masked card display string
        """
        return obj.get_card_display() or "-"

    get_card_display_admin.short_description = _("Card")

    def get_installment_display_admin(self, obj: Any) -> str:
        """
        Display installment information in list view.

        Args:
            obj: Payment instance

        Returns:
            Formatted installment display string
        """
        if not hasattr(obj, "has_installment") or not obj.has_installment():
            return "-"

        # Use the model's get_installment_display method if available
        if hasattr(obj, "get_installment_display"):
            display = obj.get_installment_display()

            # Add badge for zero-interest installments
            if hasattr(obj, "installment_rate") and obj.installment_rate == 0:
                return format_html(
                    '{} <span style="background-color: #28a745; color: white; '
                    'padding: 2px 6px; border-radius: 3px; font-size: 10px;">0% Interest</span>',
                    display,
                )

            return display

        # Fallback if method not available
        if hasattr(obj, "installment") and obj.installment > 1:
            return f"{obj.installment}x installments"

        return "-"

    get_installment_display_admin.short_description = _("Installment")
    get_installment_display_admin.admin_order_field = "installment"

    def get_installment_details_admin(self, obj: Any) -> str:
        """
        Display detailed installment information in detail view.

        Args:
            obj: Payment instance

        Returns:
            HTML formatted installment details
        """
        from django.utils.html import escape

        if not hasattr(obj, "has_installment") or not obj.has_installment():
            return format_html(
                '<p style="color: #666;">No installment applied - single payment</p>'
            )

        # Get installment details if method is available
        if hasattr(obj, "get_installment_details"):
            details = obj.get_installment_details()
        else:
            # Build details from available fields
            details = {}
            if hasattr(obj, "installment"):
                details["installment_count"] = obj.installment
            if hasattr(obj, "installment_rate"):
                details["installment_rate"] = obj.installment_rate
            if hasattr(obj, "monthly_installment_amount"):
                details["monthly_payment"] = obj.monthly_installment_amount
            if hasattr(obj, "total_with_installment"):
                details["total_with_fees"] = obj.total_with_installment
            if hasattr(obj, "amount"):
                details["base_amount"] = obj.amount

        if not details:
            return format_html('<p style="color: #666;">Installment details not available</p>')

        # Build HTML table with properly escaped values
        currency = escape(str(obj.currency)) if hasattr(obj, "currency") else "TRY"
        html_parts = []

        html_parts.append(
            '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        )
        html_parts.append('<tr style="background: #f5f5f5;">')
        html_parts.append(
            '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Detail</th>'
        )
        html_parts.append(
            '<th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Value</th>'
        )
        html_parts.append("</tr>")

        # Add rows for each detail - escape all dynamic values
        if "installment_count" in details:
            html_parts.append("<tr>")
            html_parts.append(
                '<td style="padding: 8px; border: 1px solid #ddd; '
                'font-weight: bold;">Installment Count</td>'
            )
            count = escape(str(details["installment_count"]))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd;">' f"{count}x</td>"
            )
            html_parts.append("</tr>")

        if "base_amount" in details:
            html_parts.append("<tr>")
            html_parts.append(
                '<td style="padding: 8px; border: 1px solid #ddd;">' "Base Amount</td>"
            )
            amount = escape(str(details["base_amount"]))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd;">' f"{amount} {currency}</td>"
            )
            html_parts.append("</tr>")

        if "monthly_payment" in details:
            html_parts.append("<tr>")
            html_parts.append(
                '<td style="padding: 8px; border: 1px solid #ddd; '
                'font-weight: bold;">Monthly Payment</td>'
            )
            monthly = escape(str(details["monthly_payment"]))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd; '
                f'font-size: 14px; font-weight: bold;">'
                f"{monthly} {currency}</td>"
            )
            html_parts.append("</tr>")

        if "installment_rate" in details:
            rate = details["installment_rate"]
            is_zero = rate == 0
            color = "#28a745" if is_zero else "#dc3545"
            rate_text = f"{escape(str(rate))}%"
            if is_zero:
                rate_text += " (Zero Interest)"
            html_parts.append("<tr>")
            html_parts.append(
                '<td style="padding: 8px; border: 1px solid #ddd;">' "Installment Rate</td>"
            )
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd; '
                f'color: {color}; font-weight: bold;">{rate_text}</td>'
            )
            html_parts.append("</tr>")

        if "total_fee" in details:
            html_parts.append("<tr>")
            html_parts.append('<td style="padding: 8px; border: 1px solid #ddd;">' "Total Fee</td>")
            fee = escape(str(details["total_fee"]))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd;">' f"{fee} {currency}</td>"
            )
            html_parts.append("</tr>")

        if "total_with_fees" in details:
            html_parts.append("<tr>")
            html_parts.append(
                '<td style="padding: 8px; border: 1px solid #ddd; '
                'font-weight: bold;">Total with Fees</td>'
            )
            total = escape(str(details["total_with_fees"]))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd; '
                f'font-weight: bold;">{total} {currency}</td>'
            )
            html_parts.append("</tr>")

        if hasattr(obj, "bin_number") and obj.bin_number:
            html_parts.append("<tr>")
            html_parts.append('<td style="padding: 8px; border: 1px solid #ddd;">' "Card BIN</td>")
            bin_num = escape(str(obj.bin_number))
            html_parts.append(
                f'<td style="padding: 8px; border: 1px solid #ddd;">' f"{bin_num}</td>"
            )
            html_parts.append("</tr>")

        html_parts.append("</table>")

        # Add calculation note if there's a fee
        if details.get("installment_rate", 0) > 0:
            base = details.get("base_amount", 0)
            total = details.get("total_with_fees", 0)
            if base and total:
                fee_amount = total - base
                html_parts.append('<p style="margin-top: 10px; color: #666; ' 'font-size: 12px;">')
                fee_escaped = escape(str(fee_amount))
                html_parts.append(
                    f"<em>Customer pays {fee_escaped} {currency} "
                    f"more due to installment fees</em>"
                )
                html_parts.append("</p>")

        return format_html("".join(html_parts))

    get_installment_details_admin.short_description = _("Installment Details")

    def get_currency_display_admin(self, obj: Any) -> str:
        """
        Display currency with symbol and name.

        Args:
            obj: Payment instance

        Returns:
            HTML formatted currency display
        """
        try:
            if hasattr(obj, "get_currency_symbol") and hasattr(obj, "get_currency_name"):
                symbol = obj.get_currency_symbol()
                name = obj.get_currency_name()
                code = obj.currency

                return format_html(
                    '<span style="font-size: 16px;">{}</span> '
                    '<strong>{}</strong> <span style="color: #666;">({}</span>)',
                    symbol,
                    code,
                    name,
                )
        except Exception:
            # Fallback to simple display
            pass

        return obj.currency

    get_currency_display_admin.short_description = _("Currency")
    get_currency_display_admin.admin_order_field = "currency"

    def get_raw_response_display(self, obj: Any) -> str:
        """
        Display raw response as formatted JSON.

        Sanitizes any remaining sensitive data before display for security.

        Args:
            obj: Payment instance

        Returns:
            HTML formatted JSON
        """
        if not obj.raw_response:
            return "-"

        import json

        from .utils import sanitize_log_data

        try:
            # Sanitize data to ensure no sensitive information is displayed
            # (in case of old records stored before sanitization was added)
            safe_response = sanitize_log_data(obj.raw_response)
            # Pretty print JSON
            formatted = json.dumps(safe_response, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background: #f5f5f5; padding: 10px; '
                'border-radius: 5px; max-height: 400px; overflow: auto;">{}</pre>',
                formatted,
            )
        except (TypeError, ValueError):
            return str(obj.raw_response)

    get_raw_response_display.short_description = _("Raw Response")

    def get_iyzico_dashboard_link(self, obj: Any) -> str:
        """
        Get link to Iyzico dashboard for this payment.

        Args:
            obj: Payment instance

        Returns:
            HTML link to Iyzico dashboard
        """
        if not obj.payment_id:
            return "-"

        # Iyzico merchant dashboard URL (update if different)
        dashboard_url = f"https://merchant.iyzipay.com/payment/{obj.payment_id}"

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">'
            "View in Iyzico Dashboard →</a>",
            dashboard_url,
        )

    get_iyzico_dashboard_link.short_description = _("Iyzico Dashboard")

    def refund_payment(self, request: HttpRequest, queryset: QuerySet) -> None:
        """
        Admin action to refund payments.

        Args:
            request: HTTP request
            queryset: Selected payment objects
        """
        # Import here to avoid circular import
        from .utils import get_client_ip

        refunded_count = 0
        failed_count = 0

        # Get admin user's IP for audit trail (uses centralized function that respects settings)
        ip_address = get_client_ip(request) or "127.0.0.1"

        for payment in queryset:
            # Check if payment can be refunded
            if not payment.can_be_refunded():
                self.message_user(
                    request,
                    f"Payment {payment.payment_id} cannot be refunded "
                    f"(status: {payment.get_status_display()})",
                    level="warning",
                )
                failed_count += 1
                continue

            try:
                # Check if payment has process_refund method
                if hasattr(payment, "process_refund"):
                    payment.process_refund(ip_address=ip_address)
                    refunded_count += 1
                else:
                    self.message_user(
                        request,
                        f"Payment {payment.payment_id} model does not support refunds. "
                        "Please implement process_refund() method.",
                        level="error",
                    )
                    failed_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to refund payment {payment.payment_id}: {str(e)}",
                    level="error",
                )
                failed_count += 1

        # Success message
        if refunded_count > 0:
            self.message_user(
                request, f"Successfully refunded {refunded_count} payment(s).", level="success"
            )

        if failed_count > 0:
            self.message_user(
                request, f"Failed to refund {failed_count} payment(s).", level="warning"
            )

    refund_payment.short_description = _("Refund selected payments")

    def _sanitize_csv_field(self, value: Any) -> str:
        """
        Sanitize a field value to prevent CSV injection attacks.

        CSV injection (formula injection) occurs when a CSV field starts with
        characters like =, +, -, @ which can be interpreted as formulas by
        spreadsheet applications.

        Args:
            value: Field value to sanitize

        Returns:
            Sanitized string value safe for CSV export
        """
        if value is None:
            return ""

        str_value = str(value)

        # Prefix with single quote if value starts with formula-trigger characters
        # This prevents spreadsheet applications from executing formulas
        if str_value and str_value[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
            return "'" + str_value

        return str_value

    def export_csv(self, request: HttpRequest, queryset: QuerySet) -> HttpResponse:
        """
        Admin action to export payments to CSV.

        Includes CSV injection protection to prevent formula attacks.

        Args:
            request: HTTP request
            queryset: Selected payment objects

        Returns:
            CSV file response
        """
        import csv

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="iyzico_payments.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow(
            [
                "Payment ID",
                "Conversation ID",
                "Status",
                "Amount",
                "Paid Amount",
                "Currency",
                "Installment",
                "Buyer Email",
                "Buyer Name",
                "Buyer Surname",
                "Card Last 4",
                "Card Association",
                "Card Type",
                "Card Bank",
                "Error Code",
                "Error Message",
                "Created At",
                "Updated At",
            ]
        )

        # Write data with CSV injection protection
        for payment in queryset:
            writer.writerow(
                [
                    self._sanitize_csv_field(payment.payment_id),
                    self._sanitize_csv_field(payment.conversation_id),
                    self._sanitize_csv_field(payment.get_status_display()),
                    str(payment.amount),
                    str(payment.paid_amount) if payment.paid_amount else "",
                    self._sanitize_csv_field(payment.currency),
                    payment.installment,
                    self._sanitize_csv_field(payment.buyer_email),
                    self._sanitize_csv_field(payment.buyer_name),
                    self._sanitize_csv_field(payment.buyer_surname),
                    self._sanitize_csv_field(payment.card_last_four_digits),
                    self._sanitize_csv_field(payment.card_association),
                    self._sanitize_csv_field(payment.card_type),
                    self._sanitize_csv_field(payment.card_bank_name),
                    self._sanitize_csv_field(payment.error_code),
                    self._sanitize_csv_field(payment.error_message),
                    payment.created_at.isoformat() if payment.created_at else "",
                    payment.updated_at.isoformat() if payment.updated_at else "",
                ]
            )

        self.message_user(
            request, f"Exported {queryset.count()} payment(s) to CSV.", level="success"
        )

        return response

    export_csv.short_description = _("Export selected payments to CSV")

    def has_delete_permission(self, request: HttpRequest, obj: Optional[Any] = None) -> bool:
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


# Subscription Admin Classes
try:
    from .subscription_models import (
        CardBrand,
        PaymentMethod,
        Subscription,
        SubscriptionPayment,
        SubscriptionPlan,
        SubscriptionStatus,
    )

    @admin.register(PaymentMethod)
    class PaymentMethodAdmin(admin.ModelAdmin):
        """
        Admin interface for payment methods (stored cards).

        Features:
        - View stored payment methods
        - Search by user, card details
        - Filter by card brand, active status
        - Security: NEVER displays full card numbers
        - Actions to deactivate cards
        - Expiry warnings
        """

        list_display = [
            "id",
            "user",
            "get_display_name",
            "get_card_brand_badge",
            "card_type",
            "card_bank_name",
            "get_expiry_display",
            "get_usage_stats",
            "is_default",
            "is_active",
            "last_used_at",
        ]

        list_filter = [
            "card_brand",
            "card_type",
            "is_default",
            "is_active",
            "is_verified",
            "created_at",
        ]

        search_fields = [
            "user__email",
            "user__username",
            "card_last_four",
            "card_holder_name",
            "card_token",
        ]

        readonly_fields = [
            "card_token",
            "card_user_key",
            "bin_number",
            "is_verified",
            "created_at",
            "updated_at",
            "last_used_at",
            "get_detailed_usage_stats",
        ]

        fieldsets = [
            (
                _("User & Status"),
                {
                    "fields": (
                        "user",
                        "is_default",
                        "is_active",
                        "is_verified",
                        "nickname",
                    )
                },
            ),
            (
                _("Card Information"),
                {
                    "fields": (
                        "card_last_four",
                        "card_brand",
                        "card_type",
                        "card_family",
                        "card_bank_name",
                        "card_holder_name",
                        "bin_number",
                    )
                },
            ),
            (
                _("Expiry"),
                {
                    "fields": (
                        "expiry_month",
                        "expiry_year",
                    )
                },
            ),
            (
                _("Security Tokens (PCI DSS Compliant)"),
                {
                    "fields": (
                        "card_token",
                        "card_user_key",
                    ),
                    "description": "These are secure tokens from Iyzico, not actual card numbers.",
                    "classes": ("collapse",),
                },
            ),
            (
                _("Usage Analytics"),
                {
                    "fields": ("get_detailed_usage_stats",),
                    "description": "Comprehensive usage statistics for this payment method.",
                },
            ),
            (
                _("Metadata"),
                {
                    "fields": (
                        "metadata",
                        "created_at",
                        "updated_at",
                        "last_used_at",
                    ),
                    "classes": ("collapse",),
                },
            ),
        ]

        date_hierarchy = "created_at"
        ordering = ["-is_default", "-created_at"]
        list_per_page = 50

        actions = ["deactivate_cards", "set_as_default", "delete_from_iyzico"]

        def get_card_brand_badge(self, obj: PaymentMethod) -> str:
            """Display card brand with colored badge."""
            brand_colors = {
                CardBrand.VISA: "#1A1F71",  # Visa blue
                CardBrand.MASTERCARD: "#EB001B",  # Mastercard red
                CardBrand.AMEX: "#006FCF",  # Amex blue
                CardBrand.TROY: "#00A3E0",  # Troy blue
                CardBrand.OTHER: "#6c757d",  # Gray
            }

            color = brand_colors.get(obj.card_brand, "#6c757d")
            brand_display = obj.get_card_brand_display()

            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
                color,
                brand_display,
            )

        get_card_brand_badge.short_description = _("Brand")
        get_card_brand_badge.admin_order_field = "card_brand"

        def get_expiry_display(self, obj: PaymentMethod) -> str:
            """Display expiry date with warnings."""
            expiry_text = f"{obj.expiry_month}/{obj.expiry_year}"

            if obj.is_expired():
                return format_html(
                    '<span style="color: #dc3545; font-weight: bold;">{} (EXPIRED)</span>',
                    expiry_text,
                )
            elif obj.expires_soon(within_days=30):
                return format_html(
                    '<span style="color: #fd7e14; font-weight: bold;">{} (Expires Soon)</span>',
                    expiry_text,
                )
            else:
                return expiry_text

        get_expiry_display.short_description = _("Expiry")

        def get_usage_stats(self, obj: PaymentMethod) -> str:
            """
            Display payment method usage statistics.

            Shows total successful payments and total amount billed using this card.
            """
            from decimal import Decimal

            from django.db.models import Count, Sum
            from django.utils.html import escape

            # Get successful subscription payments using this card
            # Note: We need to check if there's a payment_method foreign key
            # Since PaymentMethod stores tokens, we match by card_token in metadata
            # For now, we'll count subscriptions that might use this card
            # A more accurate approach would be to link SubscriptionPayment to PaymentMethod
            user_subscriptions = obj.user.iyzico_subscriptions.filter(
                status__in=["active", "cancelled", "expired"]
            )

            total_payments = 0
            total_amount = Decimal("0.00")

            currency = "TRY"  # Default currency
            for subscription in user_subscriptions:
                stats = subscription.payments.filter(status="success").aggregate(
                    count=Count("id"), total=Sum("amount")
                )

                if stats["count"]:
                    total_payments += stats["count"]
                    total_amount += stats["total"] or Decimal("0.00")
                    # Get currency from subscription plan if available
                    if hasattr(subscription, "plan") and subscription.plan:
                        currency = getattr(subscription.plan, "currency", "TRY") or "TRY"

            if total_payments == 0:
                return format_html('<span style="color: #999;">No usage</span>')

            # Format amount with currency from subscription plan
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">{} payment(s)</span><br>'
                '<span style="color: #6c757d; font-size: 11px;">{} total</span>',
                total_payments,
                f"{total_amount:.2f} {escape(currency)}",
            )

        get_usage_stats.short_description = _("Usage")

        def get_detailed_usage_stats(self, obj: PaymentMethod) -> str:
            """
            Display detailed payment method usage statistics in admin detail view.

            Shows comprehensive analytics including:
            - Total successful payments
            - Total amount billed
            - Active subscriptions using this card
            - Last usage date
            """
            from decimal import Decimal

            from django.db.models import Count, Sum
            from django.utils.html import escape

            # Get all user subscriptions
            user_subscriptions = obj.user.iyzico_subscriptions.all()

            # Active subscriptions
            active_subscriptions = user_subscriptions.filter(
                status__in=["active", "trialing"]
            ).count()

            # Payment statistics
            total_payments = 0
            total_amount = Decimal("0.00")
            successful_payments = 0
            failed_payments = 0
            currency = "TRY"  # Default currency

            for subscription in user_subscriptions:
                payment_stats = subscription.payments.aggregate(
                    total_count=Count("id"),
                    success_count=Count("id", filter=Q(status="success")),
                    failed_count=Count("id", filter=Q(status="failure")),
                    total_amount=Sum("amount", filter=Q(status="success")),
                )

                total_payments += payment_stats["total_count"] or 0
                successful_payments += payment_stats["success_count"] or 0
                failed_payments += payment_stats["failed_count"] or 0
                total_amount += payment_stats["total_amount"] or Decimal("0.00")

                # Get currency from subscription plan if available
                if hasattr(subscription, "plan") and subscription.plan:
                    currency = getattr(subscription.plan, "currency", "TRY") or "TRY"

            # Build HTML output with escaped values
            html_parts = []
            html_parts.append(
                '<div style="background: #f8f9fa; padding: 15px; '
                'border-radius: 5px; margin: 10px 0;">'
            )

            # Header
            html_parts.append(
                '<h3 style="margin-top: 0; color: #495057;">' "Payment Method Usage Analytics</h3>"
            )

            # Statistics grid
            html_parts.append(
                '<div style="display: grid; '
                "grid-template-columns: repeat(2, 1fr); "
                'gap: 15px; margin-bottom: 15px;">'
            )

            # Active Subscriptions
            active_count = escape(str(active_subscriptions))
            html_parts.append(
                f"""
                <div style="background: white; padding: 12px;
                     border-radius: 4px; border-left: 4px solid #28a745;">
                    <div style="font-size: 24px; font-weight: bold;
                         color: #28a745;">{active_count}</div>
                    <div style="color: #6c757d; font-size: 12px;">
                        Active Subscriptions</div>
                </div>
            """
            )

            # Total Payments
            success_count = escape(str(successful_payments))
            html_parts.append(
                f"""
                <div style="background: white; padding: 12px;
                     border-radius: 4px; border-left: 4px solid #007bff;">
                    <div style="font-size: 24px; font-weight: bold;
                         color: #007bff;">{success_count}</div>
                    <div style="color: #6c757d; font-size: 12px;">
                        Successful Payments</div>
                </div>
            """
            )

            # Total Amount
            amount_str = escape(f"{total_amount:.2f}")
            currency_str = escape(currency)
            html_parts.append(
                f"""
                <div style="background: white; padding: 12px;
                     border-radius: 4px; border-left: 4px solid #17a2b8;">
                    <div style="font-size: 24px; font-weight: bold;
                         color: #17a2b8;">{amount_str} {currency_str}</div>
                    <div style="color: #6c757d; font-size: 12px;">
                        Total Amount Billed</div>
                </div>
            """
            )

            # Failed Payments
            failure_color = "#dc3545" if failed_payments > 0 else "#6c757d"
            failed_count = escape(str(failed_payments))
            html_parts.append(
                f"""
                <div style="background: white; padding: 12px;
                     border-radius: 4px;
                     border-left: 4px solid {failure_color};">
                    <div style="font-size: 24px; font-weight: bold;
                         color: {failure_color};">{failed_count}</div>
                    <div style="color: #6c757d; font-size: 12px;">
                        Failed Payments</div>
                </div>
            """
            )

            html_parts.append("</div>")  # Close grid

            # Last Used
            if obj.last_used_at:
                from django.utils.timesince import timesince

                html_parts.append(
                    '<div style="color: #6c757d; font-size: 13px; ' 'margin-top: 10px;">'
                )
                timesince_str = escape(timesince(obj.last_used_at))
                html_parts.append(f"<strong>Last Used:</strong> {timesince_str} ago ")
                date_str = escape(obj.last_used_at.strftime("%Y-%m-%d %H:%M"))
                html_parts.append(f"({date_str})")
                html_parts.append("</div>")
            else:
                html_parts.append(
                    '<div style="color: #999; font-size: 13px; '
                    'margin-top: 10px;">Never used for payments</div>'
                )

            # Card Info
            html_parts.append(
                '<div style="margin-top: 15px; padding-top: 15px; '
                'border-top: 1px solid #dee2e6;">'
            )
            html_parts.append('<div style="color: #6c757d; font-size: 12px;">')
            brand = escape(obj.get_card_brand_display())
            last_four = escape(str(obj.card_last_four))
            html_parts.append(f"<strong>Card:</strong> {brand} ending in {last_four}<br>")
            month = escape(str(obj.expiry_month))
            year = escape(str(obj.expiry_year))
            html_parts.append(f"<strong>Expires:</strong> {month}/{year}")

            if obj.is_expired():
                html_parts.append(
                    ' <span style="color: #dc3545; font-weight: bold;">EXPIRED</span>'
                )
            elif obj.expires_soon(within_days=30):
                html_parts.append(
                    ' <span style="color: #fd7e14; font-weight: bold;">EXPIRES SOON</span>'
                )

            html_parts.append("</div></div>")

            html_parts.append("</div>")  # Close main div

            return format_html("".join(html_parts))

        get_detailed_usage_stats.short_description = _("Usage Statistics")

        def deactivate_cards(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Deactivate selected payment methods."""
            count = 0
            for payment_method in queryset:
                if payment_method.is_active:
                    payment_method.deactivate()
                    count += 1

            self.message_user(
                request,
                f"Deactivated {count} payment method(s).",
                level="success",
            )

        deactivate_cards.short_description = _("Deactivate selected payment methods")

        def set_as_default(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Set selected payment method as default (only one)."""
            if queryset.count() != 1:
                self.message_user(
                    request,
                    "Please select exactly one payment method to set as default.",
                    level="error",
                )
                return

            payment_method = queryset.first()

            if not payment_method.is_active:
                self.message_user(
                    request,
                    "Cannot set inactive payment method as default. Activate it first.",
                    level="error",
                )
                return

            if payment_method.is_expired():
                self.message_user(
                    request,
                    "Cannot set expired payment method as default.",
                    level="error",
                )
                return

            payment_method.is_default = True
            payment_method.save()

            self.message_user(
                request,
                f"Set payment method {payment_method.id} as default "
                f"for user {payment_method.user}.",
                level="success",
            )

        set_as_default.short_description = _("Set as default payment method")

        def delete_from_iyzico(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Delete cards from Iyzico and database."""
            from .client import IyzicoClient

            client = IyzicoClient()
            deleted_count = 0
            failed_count = 0

            for payment_method in queryset:
                try:
                    # Delete from Iyzico first
                    client.delete_card(
                        card_token=payment_method.card_token,
                        card_user_key=payment_method.card_user_key,
                    )

                    # Delete from database
                    payment_method_id = payment_method.id
                    payment_method.delete()

                    logger.info(
                        f"Deleted payment method {payment_method_id} from Iyzico and database"
                    )
                    deleted_count += 1

                except Exception as e:
                    logger.error(f"Failed to delete payment method {payment_method.id}: {e}")
                    self.message_user(
                        request,
                        f"Failed to delete payment method {payment_method.id}: {str(e)}",
                        level="error",
                    )
                    failed_count += 1

            if deleted_count > 0:
                self.message_user(
                    request,
                    f"Successfully deleted {deleted_count} payment method(s) "
                    "from Iyzico and database.",
                    level="success",
                )

            if failed_count > 0:
                self.message_user(
                    request,
                    f"Failed to delete {failed_count} payment method(s).",
                    level="warning",
                )

        delete_from_iyzico.short_description = _("Delete from Iyzico and database")

        def has_delete_permission(
            self, request: HttpRequest, obj: Optional[PaymentMethod] = None
        ) -> bool:
            """
            Prevent direct deletion - require using delete_from_iyzico action.

            This ensures cards are removed from both Iyzico and database.
            """
            # Allow superusers to delete
            if request.user.is_superuser:
                return True

            # For others, they should use the action
            return False

        def get_queryset(self, request: HttpRequest) -> QuerySet:
            """Optimize queryset."""
            qs = super().get_queryset(request)
            return qs.select_related("user")

    @admin.register(SubscriptionPlan)
    class SubscriptionPlanAdmin(admin.ModelAdmin):
        """
        Admin interface for subscription plans.

        Features:
        - List/create/edit subscription plans
        - View active subscriber counts
        - Toggle plan active status
        - Duplicate plans
        """

        list_display = [
            "name",
            "price_display",
            "billing_interval_display",
            "trial_period_days",
            "get_subscriber_count",
            "is_active",
            "sort_order",
        ]

        list_filter = [
            "is_active",
            "billing_interval",
            "currency",
        ]

        search_fields = [
            "name",
            "slug",
            "description",
        ]

        prepopulated_fields = {
            "slug": ("name",),
        }

        readonly_fields = [
            "created_at",
            "updated_at",
            "get_subscriber_count",
        ]

        fieldsets = [
            (
                _("Basic Information"),
                {
                    "fields": (
                        "name",
                        "slug",
                        "description",
                        "is_active",
                        "sort_order",
                    )
                },
            ),
            (
                _("Pricing"),
                {
                    "fields": (
                        "price",
                        "currency",
                        "billing_interval",
                        "billing_interval_count",
                    )
                },
            ),
            (
                _("Trial & Limits"),
                {
                    "fields": (
                        "trial_period_days",
                        "max_subscribers",
                        "get_subscriber_count",
                    )
                },
            ),
            (
                _("Features"),
                {
                    "fields": ("features",),
                    "classes": ("collapse",),
                },
            ),
            (
                _("Metadata"),
                {
                    "fields": (
                        "created_at",
                        "updated_at",
                    ),
                    "classes": ("collapse",),
                },
            ),
        ]

        ordering = ["sort_order", "price"]
        list_per_page = 25

        actions = ["duplicate_plan", "toggle_active"]

        def price_display(self, obj: SubscriptionPlan) -> str:
            """Display formatted price."""
            return f"{obj.price} {obj.currency}"

        price_display.short_description = _("Price")
        price_display.admin_order_field = "price"

        def billing_interval_display(self, obj: SubscriptionPlan) -> str:
            """Display billing interval with count."""
            if obj.billing_interval_count == 1:
                return obj.get_billing_interval_display()
            return f"Every {obj.billing_interval_count} {obj.get_billing_interval_display()}s"

        billing_interval_display.short_description = _("Billing Interval")
        billing_interval_display.admin_order_field = "billing_interval"

        def get_subscriber_count(self, obj: SubscriptionPlan) -> str:
            """Get active subscriber count."""
            count = obj.subscriptions.filter(
                status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
            ).count()

            if obj.max_subscribers:
                return format_html(
                    "<span>{} / {} subscribers</span>",
                    count,
                    obj.max_subscribers,
                )

            return f"{count} subscribers"

        get_subscriber_count.short_description = _("Subscribers")

        def duplicate_plan(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Duplicate selected plans."""
            for plan in queryset:
                plan.pk = None
                plan.name = f"{plan.name} (Copy)"
                plan.slug = f"{plan.slug}-copy"
                plan.is_active = False
                plan.save()

            self.message_user(
                request,
                f"Duplicated {queryset.count()} plan(s).",
                level="success",
            )

        duplicate_plan.short_description = _("Duplicate selected plans")

        def toggle_active(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Toggle active status of selected plans."""
            for plan in queryset:
                plan.is_active = not plan.is_active
                plan.save()

            self.message_user(
                request,
                f"Toggled active status for {queryset.count()} plan(s).",
                level="success",
            )

        toggle_active.short_description = _("Toggle active status")

    @admin.register(Subscription)
    class SubscriptionAdmin(admin.ModelAdmin):
        """
        Admin interface for subscriptions.

        Features:
        - View and filter subscriptions
        - Cancel subscriptions
        - Process billing manually
        - View payment history
        - Status badges
        """

        list_display = [
            "id",
            "user",
            "plan",
            "get_status_badge",
            "start_date",
            "next_billing_date",
            "get_payment_count",
            "failed_payment_count",
        ]

        list_filter = [
            "status",
            "plan",
            "cancel_at_period_end",
            "created_at",
        ]

        search_fields = [
            "user__email",
            "user__username",
            "plan__name",
        ]

        readonly_fields = [
            "created_at",
            "updated_at",
            "get_payment_history",
            "get_total_paid",
        ]

        fieldsets = [
            (
                _("Subscription Details"),
                {
                    "fields": (
                        "user",
                        "plan",
                        "status",
                    )
                },
            ),
            (
                _("Dates"),
                {
                    "fields": (
                        "start_date",
                        "trial_end_date",
                        "current_period_start",
                        "current_period_end",
                        "next_billing_date",
                    )
                },
            ),
            (
                _("Payment Tracking"),
                {
                    "fields": (
                        "failed_payment_count",
                        "last_payment_attempt",
                        "last_payment_error",
                        "get_payment_count",
                        "get_total_paid",
                        "get_payment_history",
                    )
                },
            ),
            (
                _("Cancellation"),
                {
                    "fields": (
                        "cancel_at_period_end",
                        "cancelled_at",
                        "cancellation_reason",
                        "ended_at",
                    )
                },
            ),
            (
                _("Metadata"),
                {
                    "fields": (
                        "metadata",
                        "created_at",
                        "updated_at",
                    ),
                    "classes": ("collapse",),
                },
            ),
        ]

        date_hierarchy = "created_at"
        ordering = ["-created_at"]
        list_per_page = 50

        actions = ["cancel_subscriptions", "process_billing_manually"]

        def get_status_badge(self, obj: Subscription) -> str:
            """Display colored status badge."""
            status_colors = {
                SubscriptionStatus.PENDING: "#ffc107",  # Yellow
                SubscriptionStatus.TRIALING: "#17a2b8",  # Blue
                SubscriptionStatus.ACTIVE: "#28a745",  # Green
                SubscriptionStatus.PAST_DUE: "#fd7e14",  # Orange
                SubscriptionStatus.PAUSED: "#6c757d",  # Gray
                SubscriptionStatus.CANCELLED: "#343a40",  # Dark gray
                SubscriptionStatus.EXPIRED: "#dc3545",  # Red
            }

            color = status_colors.get(obj.status, "#6c757d")
            status_display = obj.get_status_display()

            return format_html(
                '<span style="background-color: {}; color: white; '
                "padding: 3px 10px; border-radius: 3px; "
                'font-weight: bold; font-size: 11px;">{}</span>',
                color,
                status_display,
            )

        get_status_badge.short_description = _("Status")
        get_status_badge.admin_order_field = "status"

        def get_payment_count(self, obj: Subscription) -> int:
            """Get successful payment count."""
            return obj.payments.filter(status="success").count()

        get_payment_count.short_description = _("Successful Payments")

        def get_total_paid(self, obj: Subscription) -> str:
            """Get total amount paid."""
            total = obj.get_total_amount_paid()
            return f"{total} {obj.plan.currency}"

        get_total_paid.short_description = _("Total Paid")

        def get_payment_history(self, obj: Subscription) -> str:
            """Display payment history as table."""
            from django.utils.html import escape

            payments = obj.payments.order_by("-created_at")[:10]

            if not payments:
                return format_html("<p>No payments yet.</p>")

            html_parts = []
            html_parts.append('<table style="width: 100%; border-collapse: collapse;">')
            html_parts.append('<tr style="background: #f5f5f5;">')
            html_parts.append('<th style="padding: 8px; text-align: left;">Date</th>')
            html_parts.append('<th style="padding: 8px; text-align: left;">Amount</th>')
            html_parts.append('<th style="padding: 8px; text-align: left;">Status</th>')
            html_parts.append('<th style="padding: 8px; text-align: left;">Attempt</th>')
            html_parts.append("</tr>")

            for payment in payments:
                html_parts.append('<tr style="border-bottom: 1px solid #ddd;">')
                date_str = escape(payment.created_at.strftime("%Y-%m-%d %H:%M"))
                html_parts.append(f'<td style="padding: 8px;">{date_str}</td>')
                amount_str = f"{escape(str(payment.amount))} {escape(str(payment.currency))}"
                html_parts.append(f'<td style="padding: 8px;">{amount_str}</td>')
                html_parts.append(
                    f'<td style="padding: 8px;">{escape(payment.get_status_display())}</td>'
                )
                html_parts.append(
                    f'<td style="padding: 8px;">#{escape(str(payment.attempt_number))}</td>'
                )
                html_parts.append("</tr>")

            html_parts.append("</table>")

            if obj.payments.count() > 10:
                count = escape(str(obj.payments.count()))
                html_parts.append(
                    f'<p style="margin-top: 10px;"><em>Showing 10 of {count} payments</em></p>'
                )

            return format_html("".join(html_parts))

        get_payment_history.short_description = _("Recent Payments")

        def cancel_subscriptions(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Cancel selected subscriptions."""
            from .subscription_manager import SubscriptionManager

            manager = SubscriptionManager()
            cancelled_count = 0

            for subscription in queryset:
                if not subscription.is_cancelled():
                    manager.cancel_subscription(
                        subscription=subscription,
                        at_period_end=True,
                        reason="Cancelled by admin",
                    )
                    cancelled_count += 1

            self.message_user(
                request,
                f"Cancelled {cancelled_count} subscription(s).",
                level="success",
            )

        cancel_subscriptions.short_description = _("Cancel selected subscriptions")

        def process_billing_manually(self, request: HttpRequest, queryset: QuerySet) -> None:
            """Process billing for selected subscriptions manually."""
            self.message_user(
                request,
                "Manual billing requires stored payment methods. "
                "This feature will be available once payment method storage is implemented.",
                level="warning",
            )

        process_billing_manually.short_description = _("Process billing manually")

        def get_queryset(self, request: HttpRequest) -> QuerySet:
            """Optimize queryset."""
            qs = super().get_queryset(request)
            return qs.select_related("user", "plan").prefetch_related("payments")

    @admin.register(SubscriptionPayment)
    class SubscriptionPaymentAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
        """
        Admin interface for subscription payments.

        Extends IyzicoPaymentAdminMixin with subscription-specific features.
        """

        list_display = IyzicoPaymentAdminMixin.list_display + [
            "subscription",
            "get_period_display",
            "attempt_number",
            "is_retry",
        ]

        list_filter = IyzicoPaymentAdminMixin.list_filter + [
            "is_retry",
            "is_prorated",
        ]

        search_fields = IyzicoPaymentAdminMixin.search_fields + [
            "subscription__user__email",
            "subscription__user__username",
        ]

        readonly_fields = IyzicoPaymentAdminMixin.readonly_fields + [
            "subscription",
            "period_start",
            "period_end",
            "attempt_number",
            "is_retry",
            "is_prorated",
            "prorated_amount",
        ]

        fieldsets = IyzicoPaymentAdminMixin.fieldsets + [
            (
                _("Subscription Details"),
                {
                    "fields": (
                        "subscription",
                        "period_start",
                        "period_end",
                        "attempt_number",
                        "is_retry",
                        "is_prorated",
                        "prorated_amount",
                    )
                },
            ),
        ]

        def get_period_display(self, obj: SubscriptionPayment) -> str:
            """Display billing period."""
            return (
                f"{obj.period_start.strftime('%Y-%m-%d')} - {obj.period_end.strftime('%Y-%m-%d')}"
            )

        get_period_display.short_description = _("Billing Period")

        def get_queryset(self, request: HttpRequest) -> QuerySet:
            """Optimize queryset."""
            qs = super().get_queryset(request)
            return qs.select_related("subscription", "subscription__user", "subscription__plan")

except ImportError:
    # Subscription models not available (not installed or migrated yet)
    pass
