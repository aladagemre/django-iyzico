# Generated migration for subscription models

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create SubscriptionPlan model
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name for the plan", max_length=100, unique=True
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL-friendly identifier", max_length=100, unique=True
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, help_text="Detailed plan description"),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Price per billing interval",
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "currency",
                    models.CharField(
                        default="TRY", help_text="ISO 4217 currency code", max_length=3
                    ),
                ),
                (
                    "billing_interval",
                    models.CharField(
                        choices=[
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("monthly", "Monthly"),
                            ("quarterly", "Quarterly"),
                            ("yearly", "Yearly"),
                        ],
                        default="monthly",
                        help_text="How often to bill",
                        max_length=20,
                    ),
                ),
                (
                    "billing_interval_count",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Number of intervals between billings (e.g., 3 months)",
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "trial_period_days",
                    models.PositiveIntegerField(
                        default=0, help_text="Free trial period in days (0 = no trial)"
                    ),
                ),
                (
                    "features",
                    models.JSONField(
                        blank=True, default=dict, help_text="Plan features and limits as JSON"
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Whether this plan is available for new subscriptions",
                    ),
                ),
                (
                    "max_subscribers",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Maximum subscribers allowed (null = unlimited)",
                        null=True,
                    ),
                ),
                (
                    "sort_order",
                    models.IntegerField(
                        default=0, help_text="Display order (lower numbers appear first)"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Subscription Plan",
                "verbose_name_plural": "Subscription Plans",
                "db_table": "iyzico_subscription_plans",
                "ordering": ["sort_order", "price"],
            },
        ),
        # Create Subscription model
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("trialing", "Trialing"),
                            ("active", "Active"),
                            ("past_due", "Past Due"),
                            ("paused", "Paused"),
                            ("cancelled", "Cancelled"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Current subscription status",
                        max_length=20,
                    ),
                ),
                ("start_date", models.DateTimeField(help_text="When subscription started")),
                (
                    "trial_end_date",
                    models.DateTimeField(
                        blank=True, help_text="When trial period ends (if applicable)", null=True
                    ),
                ),
                (
                    "current_period_start",
                    models.DateTimeField(help_text="Start of current billing period"),
                ),
                (
                    "current_period_end",
                    models.DateTimeField(help_text="End of current billing period"),
                ),
                (
                    "cancelled_at",
                    models.DateTimeField(
                        blank=True, help_text="When subscription was cancelled", null=True
                    ),
                ),
                (
                    "ended_at",
                    models.DateTimeField(
                        blank=True, help_text="When subscription ended", null=True
                    ),
                ),
                (
                    "next_billing_date",
                    models.DateTimeField(db_index=True, help_text="Next scheduled billing date"),
                ),
                (
                    "failed_payment_count",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of consecutive failed payment attempts"
                    ),
                ),
                (
                    "last_payment_attempt",
                    models.DateTimeField(
                        blank=True, help_text="When last payment was attempted", null=True
                    ),
                ),
                (
                    "last_payment_error",
                    models.TextField(
                        blank=True, help_text="Error message from last failed payment", null=True
                    ),
                ),
                (
                    "cancel_at_period_end",
                    models.BooleanField(
                        default=False, help_text="Whether to cancel at end of current period"
                    ),
                ),
                (
                    "cancellation_reason",
                    models.TextField(blank=True, help_text="Reason for cancellation", null=True),
                ),
                (
                    "metadata",
                    models.JSONField(blank=True, default=dict, help_text="Additional metadata"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        help_text="Subscription plan",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="django_iyzico.subscriptionplan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        help_text="Subscriber user",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="iyzico_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription",
                "verbose_name_plural": "Subscriptions",
                "db_table": "iyzico_subscriptions",
                "ordering": ["-created_at"],
            },
        ),
        # Create SubscriptionPayment model (extends AbstractIyzicoPayment)
        migrations.CreateModel(
            name="SubscriptionPayment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                # AbstractIyzicoPayment fields
                (
                    "payment_id",
                    models.CharField(
                        blank=True,
                        help_text="Iyzico payment ID",
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "conversation_id",
                    models.CharField(
                        blank=True,
                        help_text="Conversation ID for tracking",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("refund_pending", "Refund Pending"),
                            ("refunded", "Refunded"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2, help_text="Payment amount", max_digits=10
                    ),
                ),
                (
                    "paid_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Amount paid after commissions",
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "currency",
                    models.CharField(default="TRY", help_text="Payment currency", max_length=3),
                ),
                ("locale", models.CharField(default="tr", max_length=5)),
                ("card_last_four_digits", models.CharField(blank=True, max_length=4, null=True)),
                ("card_type", models.CharField(blank=True, max_length=50, null=True)),
                ("card_association", models.CharField(blank=True, max_length=50, null=True)),
                ("card_family", models.CharField(blank=True, max_length=50, null=True)),
                ("card_bank_name", models.CharField(blank=True, max_length=100, null=True)),
                ("card_bank_code", models.CharField(blank=True, max_length=10, null=True)),
                ("installment", models.IntegerField(default=1)),
                ("buyer_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("buyer_name", models.CharField(blank=True, max_length=100, null=True)),
                ("buyer_surname", models.CharField(blank=True, max_length=100, null=True)),
                ("error_code", models.CharField(blank=True, max_length=50, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("error_group", models.CharField(blank=True, max_length=50, null=True)),
                ("raw_response", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                # Subscription-specific fields
                ("period_start", models.DateTimeField(help_text="Start of billing period")),
                ("period_end", models.DateTimeField(help_text="End of billing period")),
                (
                    "attempt_number",
                    models.PositiveIntegerField(
                        default=1, help_text="Payment attempt number (1 = first attempt)"
                    ),
                ),
                (
                    "is_retry",
                    models.BooleanField(
                        default=False, help_text="Whether this is a retry after failure"
                    ),
                ),
                (
                    "is_prorated",
                    models.BooleanField(
                        default=False, help_text="Whether this payment is prorated"
                    ),
                ),
                (
                    "prorated_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Prorated amount (if different from plan price)",
                        max_digits=10,
                        null=True,
                    ),
                ),
                (
                    "refund_reason",
                    models.CharField(
                        blank=True,
                        help_text="Reason for refund if applicable",
                        max_length=200,
                        null=True,
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        help_text="Associated subscription",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="django_iyzico.subscription",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "verbose_name": "Subscription Payment",
                "verbose_name_plural": "Subscription Payments",
                "db_table": "iyzico_subscription_payments",
                "ordering": ["-created_at"],
            },
        ),
        # Add indexes for SubscriptionPlan
        migrations.AddIndex(
            model_name="subscriptionplan",
            index=models.Index(
                fields=["is_active", "billing_interval"], name="iyzico_sub_is_acti_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionplan",
            index=models.Index(fields=["slug"], name="iyzico_sub_slug_idx"),
        ),
        # Add indexes for Subscription
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["user", "status"], name="iyzico_sub_user_st_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(
                fields=["status", "next_billing_date"], name="iyzico_sub_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["plan", "status"], name="iyzico_sub_plan_st_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(
                fields=["cancel_at_period_end", "current_period_end"], name="iyzico_sub_cancel_idx"
            ),
        ),
        # Add constraint for Subscription
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(
                check=models.Q(current_period_end__gte=models.F("current_period_start")),
                name="period_end_after_start",
            ),
        ),
        # Add indexes for SubscriptionPayment
        migrations.AddIndex(
            model_name="subscriptionpayment",
            index=models.Index(fields=["subscription", "status"], name="iyzico_subp_sub_sta_idx"),
        ),
        migrations.AddIndex(
            model_name="subscriptionpayment",
            index=models.Index(
                fields=["period_start", "period_end"], name="iyzico_subp_period_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionpayment",
            index=models.Index(
                fields=["attempt_number", "is_retry"], name="iyzico_subp_attempt_idx"
            ),
        ),
    ]
