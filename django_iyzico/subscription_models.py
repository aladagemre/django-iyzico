"""
Subscription models for django-iyzico.

Provides recurring payment and subscription management functionality.
Requires Celery for automatic billing.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import django
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import AbstractIyzicoPayment

# Django 5.1+ renamed CheckConstraint's 'check' parameter to 'condition'
CHECKCONSTRAINT_PARAM = "condition" if django.VERSION >= (5, 1) else "check"

logger = logging.getLogger(__name__)


class CardBrand(models.TextChoices):
    """Card brand/association choices."""

    VISA = "VISA", _("Visa")
    MASTERCARD = "MASTER_CARD", _("Mastercard")
    AMEX = "AMERICAN_EXPRESS", _("American Express")
    TROY = "TROY", _("Troy")
    OTHER = "OTHER", _("Other")


class PaymentMethod(models.Model):
    """
    Secure storage for payment method tokens.

    SECURITY WARNING: This model stores ONLY tokenized card data from Iyzico.
    NEVER store full card numbers, CVV, or other sensitive card data.

    The card_token is a reference token provided by Iyzico that allows
    recurring payments without storing actual card details. This ensures
    PCI DSS compliance.

    Example:
        >>> payment_method = PaymentMethod.objects.create(
        ...     user=user,
        ...     card_token='iyzico_card_token_xyz123',
        ...     card_last_four='1234',
        ...     card_brand=CardBrand.VISA,
        ...     expiry_month='12',
        ...     expiry_year='2030',
        ...     card_holder_name='John Doe',
        ... )

    Usage for recurring billing:
        >>> payment_method = user.iyzico_payment_methods.get_default()
        >>> payment_data = payment_method.to_payment_dict()
        >>> manager.process_billing(subscription, payment_data)
    """

    # User relation
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="iyzico_payment_methods",
        help_text=_("User who owns this payment method"),
    )

    # Iyzico token - NEVER store actual card numbers
    card_token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Iyzico card token for recurring payments. NEVER store full card numbers."),
    )
    card_user_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Iyzico user key for card storage"),
    )

    # Card display info (non-sensitive)
    card_last_four = models.CharField(
        max_length=4,
        help_text=_("Last 4 digits of card number"),
    )
    card_brand = models.CharField(
        max_length=50,
        choices=CardBrand.choices,
        default=CardBrand.OTHER,
        help_text=_("Card brand/association (Visa, Mastercard, etc.)"),
    )
    card_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text=_("Card type (CREDIT_CARD, DEBIT_CARD, etc.)"),
    )
    card_family = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Card program/family (Bonus, Axess, Maximum, etc.)"),
    )
    card_bank_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("Issuing bank name"),
    )
    card_holder_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Cardholder name (as on card)"),
    )

    # Expiry information (for display/warning purposes)
    expiry_month = models.CharField(
        max_length=2,
        help_text=_("Expiry month (MM format)"),
    )
    expiry_year = models.CharField(
        max_length=4,
        help_text=_("Expiry year (YYYY format)"),
    )

    # BIN for installment queries
    bin_number = models.CharField(
        max_length=6,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("First 6 digits of card (BIN) for installment queries"),
    )

    # Status flags
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Whether this is the default payment method"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this payment method is active"),
    )
    is_verified = models.BooleanField(
        default=False,
        help_text=_("Whether this card has been verified via a successful transaction"),
    )

    # Metadata
    nickname = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text=_("User-defined nickname for the card"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional metadata (no sensitive data)"),
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this payment method was last used"),
    )

    class Meta:
        db_table = "iyzico_payment_methods"
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active", "is_default"]),
            models.Index(fields=["card_token"]),
            models.Index(fields=["expiry_year", "expiry_month"]),
        ]
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        constraints = [
            # Ensure only one default per user
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True, is_active=True),
                name="unique_default_payment_method_per_user",
            ),
        ]

    def __str__(self) -> str:
        brand = self.get_card_brand_display()
        return f"{brand} ****{self.card_last_four} ({self.user})"

    def save(self, *args, **kwargs):
        """Override save to handle default payment method logic."""
        if self.is_default and self.is_active:
            # Remove default from other payment methods for this user
            PaymentMethod.objects.filter(
                user=self.user,
                is_default=True,
                is_active=True,
            ).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        # Validate expiry month
        if self.expiry_month:
            try:
                month = int(self.expiry_month)
                if not (1 <= month <= 12):
                    raise ValidationError(
                        {
                            "expiry_month": _("Must be between 01 and 12"),
                        }
                    )
            except ValueError:
                raise ValidationError(
                    {
                        "expiry_month": _("Must be a valid month number"),
                    }
                )

        # Validate expiry year
        if self.expiry_year:
            try:
                year = int(self.expiry_year)
                current_year = timezone.now().year
                if not (current_year <= year <= current_year + 20):
                    raise ValidationError(
                        {
                            "expiry_year": _("Must be a valid future year"),
                        }
                    )
            except ValueError:
                raise ValidationError(
                    {
                        "expiry_year": _("Must be a valid year"),
                    }
                )

        # Validate last four digits
        if self.card_last_four:
            if len(self.card_last_four) != 4 or not self.card_last_four.isdigit():
                raise ValidationError(
                    {
                        "card_last_four": _("Must be exactly 4 digits"),
                    }
                )

        # Validate BIN if provided
        if self.bin_number:
            if len(self.bin_number) != 6 or not self.bin_number.isdigit():
                raise ValidationError(
                    {
                        "bin_number": _("Must be exactly 6 digits"),
                    }
                )

    def is_expired(self) -> bool:
        """
        Check if the card has expired.

        Returns:
            True if the card is expired.
        """
        try:
            now = timezone.now()
            year = int(self.expiry_year)
            month = int(self.expiry_month)

            # Card expires at the end of the expiry month
            if year < now.year:
                return True
            if year == now.year and month < now.month:
                return True
            return False
        except (ValueError, TypeError):
            # If we can't parse the dates, assume not expired
            logger.warning(f"Could not parse expiry date for payment method {self.pk}")
            return False

    def expires_soon(self, within_days: int = 30) -> bool:
        """
        Check if the card expires within a specified number of days.

        Args:
            within_days: Number of days to check.

        Returns:
            True if the card expires within the specified days.
        """
        try:
            from datetime import timedelta

            now = timezone.now()
            year = int(self.expiry_year)
            month = int(self.expiry_month)

            # Card expires at the end of the expiry month
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            expiry_date = timezone.datetime(year, month, last_day, 23, 59, 59, tzinfo=now.tzinfo)

            return expiry_date <= now + timedelta(days=within_days)
        except (ValueError, TypeError):
            return False

    def get_display_name(self) -> str:
        """
        Get a human-readable display name for the payment method.

        Returns:
            Display name like "Visa ****1234" or nickname if set.
        """
        if self.nickname:
            return self.nickname
        brand = self.get_card_brand_display()
        return f"{brand} ****{self.card_last_four}"

    def to_payment_dict(self) -> Dict[str, Any]:
        """
        Convert to payment dictionary for Iyzico API calls.

        This returns only the token-based card data needed for
        recurring payments, NOT actual card details.

        Returns:
            Dictionary with card token and user key for Iyzico API.

        Example:
            >>> payment_dict = payment_method.to_payment_dict()
            >>> # Use for subscription billing
            >>> response = client.create_payment_with_token(payment_dict)
        """
        return {
            "cardToken": self.card_token,
            "cardUserKey": self.card_user_key,
        }

    def mark_as_used(self) -> None:
        """Update last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at", "updated_at"])

    def deactivate(self) -> None:
        """Deactivate this payment method."""
        self.is_active = False
        self.is_default = False
        self.save(update_fields=["is_active", "is_default", "updated_at"])

    @classmethod
    def get_default_for_user(cls, user) -> Optional["PaymentMethod"]:
        """
        Get the default active payment method for a user.

        Args:
            user: User instance.

        Returns:
            Default PaymentMethod or None if no default exists.
        """
        return cls.objects.filter(
            user=user,
            is_active=True,
            is_default=True,
        ).first()

    @classmethod
    def get_active_for_user(cls, user) -> models.QuerySet:
        """
        Get all active payment methods for a user.

        Args:
            user: User instance.

        Returns:
            QuerySet of active PaymentMethod objects.
        """
        return cls.objects.filter(
            user=user,
            is_active=True,
        ).order_by("-is_default", "-created_at")


class BillingInterval(models.TextChoices):
    """Billing interval choices for subscription plans."""

    DAILY = "daily", _("Daily")
    WEEKLY = "weekly", _("Weekly")
    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    YEARLY = "yearly", _("Yearly")


class SubscriptionPlan(models.Model):
    """
    Subscription plan/tier definition.

    Defines pricing, billing intervals, trial periods, and features
    for subscription-based services (SaaS, memberships, etc.).

    Example:
        >>> plan = SubscriptionPlan.objects.create(
        ...     name='Premium',
        ...     slug='premium',
        ...     price=Decimal('99.99'),
        ...     billing_interval=BillingInterval.MONTHLY,
        ...     trial_period_days=14,
        ...     features={'storage': '100GB', 'users': 10},
        ... )
    """

    # Basic Info
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Display name for the plan"),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text=_("URL-friendly identifier"),
    )
    description = models.TextField(
        blank=True,
        help_text=_("Detailed plan description"),
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=_("Price per billing interval"),
    )
    currency = models.CharField(
        max_length=3,
        default="TRY",
        help_text=_("ISO 4217 currency code"),
    )
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY,
        help_text=_("How often to bill"),
    )
    billing_interval_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("Number of intervals between billings (e.g., 3 months)"),
    )

    # Trial
    trial_period_days = models.PositiveIntegerField(
        default=0,
        help_text=_("Free trial period in days (0 = no trial)"),
    )

    # Features (JSON field for flexibility)
    features = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Plan features and limits as JSON"),
    )

    # Settings
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Whether this plan is available for new subscriptions"),
    )
    max_subscribers = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Maximum subscribers allowed (null = unlimited)"),
    )

    # Display order
    sort_order = models.IntegerField(
        default=0,
        help_text=_("Display order (lower numbers appear first)"),
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iyzico_subscription_plans"
        ordering = ["sort_order", "price"]
        indexes = [
            models.Index(fields=["is_active", "billing_interval"]),
            models.Index(fields=["slug"]),
        ]
        verbose_name = _("Subscription Plan")
        verbose_name_plural = _("Subscription Plans")

    def __str__(self) -> str:
        return f"{self.name} ({self.price} {self.currency}/{self.get_billing_interval_display()})"

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        # Validate billing interval count
        if self.billing_interval_count < 1:
            raise ValidationError(
                {
                    "billing_interval_count": _("Must be at least 1"),
                }
            )

        # Validate trial period
        if self.trial_period_days < 0:
            raise ValidationError(
                {
                    "trial_period_days": _("Cannot be negative"),
                }
            )

        # Validate max subscribers
        if self.max_subscribers is not None and self.max_subscribers < 0:
            raise ValidationError(
                {
                    "max_subscribers": _("Cannot be negative"),
                }
            )

    def get_total_trial_days(self) -> int:
        """Get total trial period in days."""
        return self.trial_period_days

    def get_billing_interval_days(self) -> int:
        """
        Calculate billing interval in days.

        Returns:
            Number of days in one billing cycle.
        """
        base_days = {
            BillingInterval.DAILY: 1,
            BillingInterval.WEEKLY: 7,
            BillingInterval.MONTHLY: 30,  # Approximate
            BillingInterval.QUARTERLY: 90,  # Approximate
            BillingInterval.YEARLY: 365,  # Approximate
        }
        return base_days.get(self.billing_interval, 30) * self.billing_interval_count

    def can_accept_subscribers(self) -> bool:
        """
        Check if plan can accept new subscribers.

        Returns:
            True if plan is active and under subscriber limit.
        """
        if not self.is_active:
            return False

        if self.max_subscribers is None:
            return True

        current_count = self.subscriptions.filter(
            status__in=["active", "trialing", "past_due"],
        ).count()

        return current_count < self.max_subscribers


class SubscriptionStatus(models.TextChoices):
    """Status choices for subscriptions."""

    PENDING = "pending", _("Pending")  # Created but not yet paid
    TRIALING = "trialing", _("Trialing")  # In trial period
    ACTIVE = "active", _("Active")  # Active and paid
    PAST_DUE = "past_due", _("Past Due")  # Payment failed
    PAUSED = "paused", _("Paused")  # Temporarily suspended
    CANCELLED = "cancelled", _("Cancelled")  # Cancelled but not expired
    EXPIRED = "expired", _("Expired")  # Ended


class Subscription(models.Model):
    """
    User subscription to a plan.

    Manages the subscription lifecycle including billing, payments,
    cancellations, and status transitions.

    Example:
        >>> subscription = Subscription.objects.create(
        ...     user=user,
        ...     plan=plan,
        ...     start_date=timezone.now(),
        ...     current_period_start=timezone.now(),
        ...     current_period_end=timezone.now() + timedelta(days=30),
        ...     next_billing_date=timezone.now() + timedelta(days=30),
        ... )
    """

    # Relations
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="iyzico_subscriptions",
        help_text=_("Subscriber user"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        help_text=_("Subscription plan"),
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
        db_index=True,
        help_text=_("Current subscription status"),
    )

    # Dates
    start_date = models.DateTimeField(
        help_text=_("When subscription started"),
    )
    trial_end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When trial period ends (if applicable)"),
    )
    current_period_start = models.DateTimeField(
        help_text=_("Start of current billing period"),
    )
    current_period_end = models.DateTimeField(
        help_text=_("End of current billing period"),
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When subscription was cancelled"),
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When subscription ended"),
    )

    # Billing
    next_billing_date = models.DateTimeField(
        db_index=True,
        help_text=_("Next scheduled billing date"),
    )

    # Payment tracking
    failed_payment_count = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of consecutive failed payment attempts"),
    )
    last_payment_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When last payment was attempted"),
    )
    last_payment_error = models.TextField(
        null=True,
        blank=True,
        help_text=_("Error message from last failed payment"),
    )

    # Cancellation
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text=_("Whether to cancel at end of current period"),
    )
    cancellation_reason = models.TextField(
        null=True,
        blank=True,
        help_text=_("Reason for cancellation"),
    )

    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional metadata"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iyzico_subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "next_billing_date"]),
            models.Index(fields=["plan", "status"]),
            models.Index(fields=["cancel_at_period_end", "current_period_end"]),
        ]
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        constraints = [
            models.CheckConstraint(
                **{
                    CHECKCONSTRAINT_PARAM: models.Q(
                        current_period_end__gte=models.F("current_period_start")
                    )
                },
                name="period_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.plan.name} ({self.get_status_display()})"

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        # Validate period dates
        if self.current_period_end <= self.current_period_start:
            raise ValidationError(
                {
                    "current_period_end": _("Must be after current_period_start"),
                }
            )

        # Validate trial dates
        if self.trial_end_date and self.trial_end_date < self.start_date:
            raise ValidationError(
                {
                    "trial_end_date": _("Must be after start_date"),
                }
            )

    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    def is_trialing(self) -> bool:
        """
        Check if in trial period.

        Returns:
            True if currently in trial period.
        """
        if not self.trial_end_date:
            return False
        return timezone.now() < self.trial_end_date and self.status == SubscriptionStatus.TRIALING

    def days_until_renewal(self) -> Optional[int]:
        """
        Get days until next billing.

        Returns:
            Number of days until renewal, or None if no billing date.
        """
        if not self.next_billing_date:
            return None
        delta = self.next_billing_date - timezone.now()
        return max(0, delta.days)

    def is_past_due(self) -> bool:
        """Check if subscription is past due."""
        return self.status == SubscriptionStatus.PAST_DUE

    def is_cancelled(self) -> bool:
        """Check if subscription is cancelled."""
        return self.status in [SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED]

    def can_be_renewed(self) -> bool:
        """
        Check if subscription can be renewed.

        Returns:
            True if subscription can process renewal payment.
        """
        return self.status in [
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        ]

    def get_total_amount_paid(self) -> Decimal:
        """
        Calculate total amount paid for this subscription.

        Returns:
            Total of all successful payments.
        """
        return self.payments.filter(
            status="success",
        ).aggregate(
            total=models.Sum("amount"),
        )[
            "total"
        ] or Decimal("0.00")

    def get_successful_payment_count(self) -> int:
        """Get count of successful payments."""
        return self.payments.filter(status="success").count()

    def should_retry_payment(self, max_retries: int = 3) -> bool:
        """
        Check if failed payment should be retried.

        Args:
            max_retries: Maximum number of retry attempts.

        Returns:
            True if payment should be retried.
        """
        return (
            self.status == SubscriptionStatus.PAST_DUE and self.failed_payment_count < max_retries
        )


class SubscriptionPayment(AbstractIyzicoPayment):
    """
    Payment for a subscription billing cycle.

    Extends AbstractIyzicoPayment with subscription-specific fields
    for tracking recurring payments, retries, and prorated charges.

    Example:
        >>> payment = SubscriptionPayment.objects.create(
        ...     subscription=subscription,
        ...     user=user,
        ...     amount=Decimal('99.99'),
        ...     currency='TRY',
        ...     period_start=timezone.now(),
        ...     period_end=timezone.now() + timedelta(days=30),
        ... )
    """

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="payments",
        help_text=_("Associated subscription"),
    )

    # User relation (denormalized for easier querying)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="iyzico_subscription_payments",
        help_text=_("User who made the payment"),
    )

    # Billing period this payment covers
    period_start = models.DateTimeField(
        help_text=_("Start of billing period"),
    )
    period_end = models.DateTimeField(
        help_text=_("End of billing period"),
    )

    # Attempt tracking
    attempt_number = models.PositiveIntegerField(
        default=1,
        help_text=_("Payment attempt number (1 = first attempt)"),
    )
    is_retry = models.BooleanField(
        default=False,
        help_text=_("Whether this is a retry after failure"),
    )

    # Prorating
    is_prorated = models.BooleanField(
        default=False,
        help_text=_("Whether this payment is prorated"),
    )
    prorated_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Prorated amount (if different from plan price)"),
    )

    # Refund tracking specific to subscriptions
    refund_reason = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text=_("Reason for refund if applicable"),
    )

    class Meta:
        db_table = "iyzico_subscription_payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription", "status"]),
            models.Index(fields=["period_start", "period_end"]),
            models.Index(fields=["attempt_number", "is_retry"]),
        ]
        verbose_name = _("Subscription Payment")
        verbose_name_plural = _("Subscription Payments")
        constraints = [
            # Prevent double billing for the same subscription period
            # This ensures only one successful payment per billing period attempt
            models.UniqueConstraint(
                fields=["subscription", "period_start", "period_end", "attempt_number"],
                name="unique_subscription_payment_period",
            ),
        ]

    def __str__(self) -> str:
        retry_text = f" (Retry #{self.attempt_number})" if self.is_retry else ""
        return f"Payment for {self.subscription}{retry_text} - {self.amount} {self.currency}"

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        # Validate period dates
        if self.period_end <= self.period_start:
            raise ValidationError(
                {
                    "period_end": _("Must be after period_start"),
                }
            )

        # Validate attempt number
        if self.attempt_number < 1:
            raise ValidationError(
                {
                    "attempt_number": _("Must be at least 1"),
                }
            )

        # If retry, attempt number should be > 1
        if self.is_retry and self.attempt_number == 1:
            raise ValidationError(
                {
                    "is_retry": _("Retry payments must have attempt_number > 1"),
                }
            )

    def get_effective_amount(self) -> Decimal:
        """
        Get the effective payment amount.

        Returns:
            Prorated amount if prorated, otherwise regular amount.
        """
        if self.is_prorated and self.prorated_amount:
            return self.prorated_amount
        return self.amount

    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == "success"

    def is_failed(self) -> bool:
        """Check if payment failed."""
        return self.status == "failure"

    def get_period_duration_days(self) -> int:
        """
        Calculate billing period duration in days.

        Returns:
            Number of days in billing period.
        """
        delta = self.period_end - self.period_start
        return delta.days
