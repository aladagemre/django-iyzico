# Generated migration for PaymentMethod model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("django_iyzico", "0001_add_subscription_models"),
    ]

    operations = [
        # Create PaymentMethod model
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "card_token",
                    models.CharField(
                        db_index=True,
                        help_text=(
                            "Iyzico card token for recurring payments. "
                            "NEVER store full card numbers."
                        ),
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "card_user_key",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Iyzico user key for card storage",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "card_last_four",
                    models.CharField(help_text="Last 4 digits of card number", max_length=4),
                ),
                (
                    "card_brand",
                    models.CharField(
                        choices=[
                            ("VISA", "Visa"),
                            ("MASTER_CARD", "Mastercard"),
                            ("AMERICAN_EXPRESS", "American Express"),
                            ("TROY", "Troy"),
                            ("OTHER", "Other"),
                        ],
                        default="OTHER",
                        help_text="Card brand/association (Visa, Mastercard, etc.)",
                        max_length=50,
                    ),
                ),
                (
                    "card_type",
                    models.CharField(
                        blank=True,
                        help_text="Card type (CREDIT_CARD, DEBIT_CARD, etc.)",
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    "card_family",
                    models.CharField(
                        blank=True,
                        help_text="Card program/family (Bonus, Axess, Maximum, etc.)",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "card_bank_name",
                    models.CharField(
                        blank=True, help_text="Issuing bank name", max_length=100, null=True
                    ),
                ),
                (
                    "card_holder_name",
                    models.CharField(
                        blank=True,
                        help_text="Cardholder name (as on card)",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "expiry_month",
                    models.CharField(help_text="Expiry month (MM format)", max_length=2),
                ),
                (
                    "expiry_year",
                    models.CharField(help_text="Expiry year (YYYY format)", max_length=4),
                ),
                (
                    "bin_number",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="First 6 digits of card (BIN) for installment queries",
                        max_length=6,
                        null=True,
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="Whether this is the default payment method",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Whether this payment method is active",
                    ),
                ),
                (
                    "is_verified",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Whether this card has been verified " "via a successful transaction"
                        ),
                    ),
                ),
                (
                    "nickname",
                    models.CharField(
                        blank=True,
                        help_text="User-defined nickname for the card",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional metadata (no sensitive data)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "last_used_at",
                    models.DateTimeField(
                        blank=True, help_text="When this payment method was last used", null=True
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="User who owns this payment method",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="iyzico_payment_methods",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Payment Method",
                "verbose_name_plural": "Payment Methods",
                "db_table": "iyzico_payment_methods",
                "ordering": ["-is_default", "-created_at"],
            },
        ),
        # Add indexes for PaymentMethod
        migrations.AddIndex(
            model_name="paymentmethod",
            index=models.Index(
                fields=["user", "is_active", "is_default"], name="iyzico_pm_user_act_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="paymentmethod",
            index=models.Index(fields=["card_token"], name="iyzico_pm_token_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentmethod",
            index=models.Index(fields=["expiry_year", "expiry_month"], name="iyzico_pm_expiry_idx"),
        ),
        # Add constraint for PaymentMethod - only one default per user
        migrations.AddConstraint(
            model_name="paymentmethod",
            constraint=models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True, is_active=True),
                name="unique_default_payment_method_per_user",
            ),
        ),
        # Add constraint for SubscriptionPayment - prevent double billing
        migrations.AddConstraint(
            model_name="subscriptionpayment",
            constraint=models.UniqueConstraint(
                fields=["subscription", "period_start", "period_end", "attempt_number"],
                name="unique_subscription_payment_period",
            ),
        ),
    ]
