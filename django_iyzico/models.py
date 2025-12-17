"""
Django models for django-iyzico.

Provides abstract base models that can be inherited by your Django models
to add Iyzico payment functionality.
"""

from typing import Dict, Any, Optional
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .utils import extract_card_info, mask_card_data


class PaymentStatus(models.TextChoices):
    """Payment status choices."""

    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    REFUND_PENDING = "refund_pending", _("Refund Pending")
    REFUNDED = "refunded", _("Refunded")
    CANCELLED = "cancelled", _("Cancelled")


class IyzicoPaymentQuerySet(models.QuerySet):
    """Custom QuerySet for Iyzico payments."""

    def successful(self):
        """Filter successful payments."""
        return self.filter(status=PaymentStatus.SUCCESS)

    def failed(self):
        """Filter failed payments."""
        return self.filter(status=PaymentStatus.FAILED)

    def pending(self):
        """Filter pending payments."""
        return self.filter(status=PaymentStatus.PENDING)

    def by_payment_id(self, payment_id: str):
        """Get payment by Iyzico payment ID."""
        return self.filter(payment_id=payment_id)

    def by_conversation_id(self, conversation_id: str):
        """Get payments by conversation ID."""
        return self.filter(conversation_id=conversation_id)


class IyzicoPaymentManager(models.Manager):
    """Custom manager for Iyzico payments."""

    def get_queryset(self):
        """Return custom QuerySet."""
        return IyzicoPaymentQuerySet(self.model, using=self._db)

    def get_by_payment_id(self, payment_id: str):
        """
        Get payment by Iyzico payment ID.

        Args:
            payment_id: Iyzico payment ID

        Returns:
            Payment instance

        Raises:
            DoesNotExist: If payment not found
        """
        return self.get(payment_id=payment_id)

    def get_by_conversation_id(self, conversation_id: str):
        """
        Get payment by conversation ID.

        Args:
            conversation_id: Conversation ID

        Returns:
            Payment instance (first match)

        Raises:
            DoesNotExist: If payment not found
        """
        return self.filter(conversation_id=conversation_id).first()

    def successful(self):
        """Get all successful payments."""
        return self.get_queryset().successful()

    def failed(self):
        """Get all failed payments."""
        return self.get_queryset().failed()

    def pending(self):
        """Get all pending payments."""
        return self.get_queryset().pending()


class AbstractIyzicoPayment(models.Model):
    """
    Abstract base model for Iyzico payments.

    Inherit from this in your Django models to add Iyzico payment functionality:

    Example:
        class Order(AbstractIyzicoPayment):
            user = models.ForeignKey(User, on_delete=models.CASCADE)
            product = models.ForeignKey(Product, on_delete=models.CASCADE)
            quantity = models.IntegerField()

            class Meta:
                db_table = 'orders'

    This provides all Iyzico payment fields and functionality while letting you
    add your own business-specific fields.
    """

    # Iyzico IDs
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Payment ID"),
        help_text=_("Iyzico payment ID (unique identifier from Iyzico)"),
    )
    conversation_id = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name=_("Conversation ID"),
        help_text=_("Unique conversation ID for tracking this payment"),
    )

    # Payment details
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("Current payment status"),
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Payment amount (before installments)"),
    )
    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Paid Amount"),
        help_text=_("Actual amount paid (may differ with installments)"),
    )
    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name=_("Currency"),
        help_text=_("Currency code (e.g., TRY, USD, EUR)"),
    )
    locale = models.CharField(
        max_length=5,
        default="tr",
        verbose_name=_("Locale"),
        help_text=_("Locale for the payment (e.g., tr, en)"),
    )

    # Card information (non-sensitive only - PCI DSS compliant)
    card_last_four_digits = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        verbose_name=_("Card Last 4 Digits"),
        help_text=_("Last 4 digits of card number"),
    )
    card_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Type"),
        help_text=_("Card type (e.g., CREDIT_CARD, DEBIT_CARD)"),
    )
    card_association = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Association"),
        help_text=_("Card association (e.g., VISA, MASTER_CARD, AMEX)"),
    )
    card_family = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Family"),
        help_text=_("Card family/program (e.g., Bonus, Axess, Maximum)"),
    )
    card_bank_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Card Bank Name"),
        help_text=_("Issuing bank name"),
    )
    card_bank_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Card Bank Code"),
        help_text=_("Issuing bank code"),
    )
    installment = models.IntegerField(
        default=1,
        verbose_name=_("Installment"),
        help_text=_("Number of installments (1 for single payment)"),
    )

    # Buyer information
    buyer_email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Buyer Email"),
        help_text=_("Buyer's email address"),
    )
    buyer_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Buyer Name"),
        help_text=_("Buyer's first name"),
    )
    buyer_surname = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Buyer Surname"),
        help_text=_("Buyer's last name"),
    )

    # Error handling
    error_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Error Code"),
        help_text=_("Iyzico error code (if payment failed)"),
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Error Message"),
        help_text=_("Iyzico error message (if payment failed)"),
    )
    error_group = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_("Error Group"),
        help_text=_("Iyzico error group (if payment failed)"),
    )

    # Audit trail
    raw_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Raw Response"),
        help_text=_("Complete response from Iyzico API (for debugging and audit)"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("When this payment record was created"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("When this payment record was last updated"),
    )

    # Custom manager
    objects = IyzicoPaymentManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]
        verbose_name = _("Iyzico Payment")
        verbose_name_plural = _("Iyzico Payments")
        indexes = [
            models.Index(fields=["payment_id"]),
            models.Index(fields=["conversation_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["buyer_email"]),
        ]

    def __str__(self) -> str:
        """String representation."""
        return f"Payment {self.payment_id or 'pending'} - {self.get_status_display()}"

    def is_successful(self) -> bool:
        """
        Check if payment is successful.

        Returns:
            True if payment status is SUCCESS
        """
        return self.status == PaymentStatus.SUCCESS

    def is_failed(self) -> bool:
        """
        Check if payment failed.

        Returns:
            True if payment status is FAILED
        """
        return self.status == PaymentStatus.FAILED

    def is_pending(self) -> bool:
        """
        Check if payment is pending.

        Returns:
            True if payment status is PENDING or PROCESSING
        """
        return self.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]

    def can_be_refunded(self) -> bool:
        """
        Check if payment can be refunded.

        Returns:
            True if payment is successful and not already refunded
        """
        return self.status == PaymentStatus.SUCCESS

    def process_refund(
        self,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
    ):
        """
        Process refund for this payment.

        Args:
            amount: Amount to refund (None for full refund)
            reason: Optional refund reason

        Returns:
            RefundResponse object

        Raises:
            ValidationError: If payment cannot be refunded
            PaymentError: If refund fails

        Example:
            >>> payment = Order.objects.get(id=1)
            >>> # Full refund
            >>> response = payment.process_refund()
            >>> # Partial refund
            >>> response = payment.process_refund(amount=Decimal("50.00"), reason="Customer request")
        """
        from .client import IyzicoClient
        from .signals import payment_refunded

        if not self.can_be_refunded():
            raise ValidationError("Payment cannot be refunded")

        if not self.payment_id:
            raise ValidationError("Payment ID is missing")

        client = IyzicoClient()
        response = client.refund_payment(self.payment_id, amount, reason)

        if response.is_successful():
            # Update payment status
            if amount is None or amount >= self.amount:
                self.status = PaymentStatus.REFUNDED
            else:
                self.status = PaymentStatus.REFUND_PENDING

            self.save()

            # Send signal
            payment_refunded.send(
                sender=self.__class__,
                instance=self,
                response=response.to_dict(),
                amount=amount,
                reason=reason,
            )

        return response

    def update_from_response(self, response, save: bool = True) -> None:
        """
        Update payment fields from Iyzico API response.

        Args:
            response: PaymentResponse or dict from Iyzico
            save: Whether to save the model after updating

        Example:
            >>> payment = Order.objects.get(id=1)
            >>> response = client.create_payment(...)
            >>> payment.update_from_response(response)
        """
        # Handle both PaymentResponse objects and dicts
        if hasattr(response, "to_dict"):
            response_dict = response.to_dict()
        else:
            response_dict = response

        # Update Iyzico IDs
        if response_dict.get("paymentId"):
            self.payment_id = response_dict["paymentId"]

        if response_dict.get("conversationId"):
            self.conversation_id = response_dict["conversationId"]

        # Update status
        if response_dict.get("status") == "success":
            self.status = PaymentStatus.SUCCESS
        elif response_dict.get("status") == "failure":
            self.status = PaymentStatus.FAILED
        else:
            # Keep existing status or set to processing
            if self.status == PaymentStatus.PENDING:
                self.status = PaymentStatus.PROCESSING

        # Update amounts (convert to Decimal)
        if response_dict.get("price"):
            self.amount = Decimal(str(response_dict["price"]))

        if response_dict.get("paidPrice"):
            self.paid_amount = Decimal(str(response_dict["paidPrice"]))

        if response_dict.get("currency"):
            self.currency = response_dict["currency"]

        if response_dict.get("installment"):
            self.installment = int(response_dict["installment"])

        # Update card info (safe metadata only)
        card_info = extract_card_info(response_dict)
        if card_info.get("cardType"):
            self.card_type = card_info["cardType"]
        if card_info.get("cardAssociation"):
            self.card_association = card_info["cardAssociation"]
        if card_info.get("cardFamily"):
            self.card_family = card_info["cardFamily"]
        if card_info.get("cardBankName"):
            self.card_bank_name = card_info["cardBankName"]
        if card_info.get("cardBankCode"):
            self.card_bank_code = card_info["cardBankCode"]

        # Extract last 4 digits from binNumber if available
        if response_dict.get("binNumber"):
            # binNumber is first 6 digits, not last 4
            # We need to get it from the original card data if available
            pass

        # Update buyer info
        if response_dict.get("buyerEmail"):
            self.buyer_email = response_dict["buyerEmail"]
        if response_dict.get("buyerName"):
            self.buyer_name = response_dict["buyerName"]
        if response_dict.get("buyerSurname"):
            self.buyer_surname = response_dict["buyerSurname"]

        # Update error info (if failed)
        if response_dict.get("errorCode"):
            self.error_code = response_dict["errorCode"]
        if response_dict.get("errorMessage"):
            self.error_message = response_dict["errorMessage"]
        if response_dict.get("errorGroup"):
            self.error_group = response_dict["errorGroup"]

        # Store raw response for audit
        self.raw_response = response_dict

        if save:
            self.save()

    def mask_and_store_card_data(
        self, payment_details: Dict[str, Any], save: bool = True
    ) -> None:
        """
        Mask and store card data (last 4 digits only).

        This is for storing data from the original payment request
        before sending to Iyzico. Use this to capture card last 4 digits.

        Args:
            payment_details: Original payment details with card info
            save: Whether to save the model after updating

        Example:
            >>> payment = Order(...)
            >>> payment.mask_and_store_card_data({'card': {'cardNumber': '5528790000000008'}})
            >>> print(payment.card_last_four_digits)
            '0008'
        """
        masked = mask_card_data(payment_details)

        # Extract last 4 digits if available
        if "card" in masked and isinstance(masked["card"], dict):
            last_four = masked["card"].get("lastFourDigits", "")
            if last_four:
                self.card_last_four_digits = last_four

        if save:
            self.save()

    def get_buyer_full_name(self) -> str:
        """
        Get buyer's full name.

        Returns:
            Full name (first + last) or empty string
        """
        if self.buyer_name and self.buyer_surname:
            return f"{self.buyer_name} {self.buyer_surname}"
        return self.buyer_name or self.buyer_surname or ""

    def get_masked_card_number(self) -> str:
        """
        Get masked card number for display.

        Returns:
            Masked card number (e.g., "**** **** **** 1234")
        """
        if self.card_last_four_digits:
            return f"**** **** **** {self.card_last_four_digits}"
        return "****"

    def get_card_display(self) -> str:
        """
        Get card display string.

        Returns:
            Card display string (e.g., "VISA **** 1234")
        """
        parts = []

        if self.card_association:
            parts.append(self.card_association)

        if self.card_last_four_digits:
            parts.append(f"**** {self.card_last_four_digits}")

        return " ".join(parts) if parts else "****"

    def get_amount_display(self) -> str:
        """
        Get formatted amount for display.

        Returns:
            Formatted amount with currency (e.g., "100.00 TRY")
        """
        return f"{self.amount} {self.currency}"

    def get_paid_amount_display(self) -> str:
        """
        Get formatted paid amount for display.

        Returns:
            Formatted paid amount with currency
        """
        amount = self.paid_amount if self.paid_amount else self.amount
        return f"{amount} {self.currency}"
