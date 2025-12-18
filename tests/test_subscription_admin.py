"""
Tests for subscription admin interface.

Tests for Django admin classes and actions.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone

from django_iyzico.admin import (
    PaymentMethodAdmin,
    SubscriptionAdmin,
    SubscriptionPaymentAdmin,
    SubscriptionPlanAdmin,
)
from django_iyzico.subscription_models import (
    BillingInterval,
    CardBrand,
    PaymentMethod,
    Subscription,
    SubscriptionPayment,
    SubscriptionPlan,
    SubscriptionStatus,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    """Create admin user."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="admin123",
    )


@pytest.fixture
def regular_user():
    """Create regular user."""
    return User.objects.create_user(
        username="user",
        email="user@example.com",
        password="user123",
    )


@pytest.fixture
def request_factory():
    """Create request factory."""
    return RequestFactory()


@pytest.fixture
def admin_site():
    """Create admin site."""
    return AdminSite()


def add_messages_support(request):
    """Add messages framework support to a request object."""
    setattr(request, "session", "session")
    messages = FallbackStorage(request)
    setattr(request, "_messages", messages)
    return request


class TestSubscriptionPlanAdmin:
    """Tests for SubscriptionPlanAdmin."""

    @pytest.fixture
    def plan_admin(self, admin_site):
        """Create SubscriptionPlanAdmin instance."""
        return SubscriptionPlanAdmin(SubscriptionPlan, admin_site)

    def test_list_display(self, plan_admin):
        """Test list_display configuration."""
        assert "name" in plan_admin.list_display
        assert "price_display" in plan_admin.list_display
        assert "billing_interval_display" in plan_admin.list_display
        assert "get_subscriber_count" in plan_admin.list_display

    def test_price_display(self, plan_admin):
        """Test price_display method."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
            currency="TRY",
        )

        result = plan_admin.price_display(plan)
        assert result == "99.99 TRY"

    def test_billing_interval_display_single(self, plan_admin):
        """Test billing interval display for single interval."""
        plan = SubscriptionPlan.objects.create(
            name="Monthly",
            slug="monthly",
            price=Decimal("49.99"),
            billing_interval=BillingInterval.MONTHLY,
            billing_interval_count=1,
        )

        result = plan_admin.billing_interval_display(plan)
        assert result == "Monthly"

    def test_billing_interval_display_multiple(self, plan_admin):
        """Test billing interval display for multiple intervals."""
        plan = SubscriptionPlan.objects.create(
            name="Quarterly",
            slug="quarterly",
            price=Decimal("149.99"),
            billing_interval=BillingInterval.MONTHLY,
            billing_interval_count=3,
        )

        result = plan_admin.billing_interval_display(plan)
        assert result == "Every 3 Monthlys"

    def test_get_subscriber_count(self, plan_admin, regular_user):
        """Test get_subscriber_count method."""
        plan = SubscriptionPlan.objects.create(
            name="Premium",
            slug="premium",
            price=Decimal("99.99"),
        )

        # Create active subscription
        now = timezone.now()
        Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        result = plan_admin.get_subscriber_count(plan)
        assert "1 subscribers" in result

    def test_get_subscriber_count_with_limit(self, plan_admin, regular_user):
        """Test subscriber count with max limit."""
        plan = SubscriptionPlan.objects.create(
            name="Limited",
            slug="limited",
            price=Decimal("99.99"),
            max_subscribers=10,
        )

        now = timezone.now()
        Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        result = plan_admin.get_subscriber_count(plan)
        assert "1 / 10 subscribers" in result

    def test_duplicate_plan_action(self, plan_admin, request_factory, admin_user):
        """Test duplicate_plan admin action."""
        plan = SubscriptionPlan.objects.create(
            name="Original",
            slug="original",
            price=Decimal("99.99"),
        )

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = SubscriptionPlan.objects.filter(id=plan.id)
        plan_admin.duplicate_plan(request, queryset)

        # Should have 2 plans now
        assert SubscriptionPlan.objects.count() == 2

        # Find duplicated plan
        duplicated = SubscriptionPlan.objects.exclude(id=plan.id).first()
        assert duplicated.name == "Original (Copy)"
        assert duplicated.slug == "original-copy"
        assert duplicated.is_active is False

    def test_toggle_active_action(self, plan_admin, request_factory, admin_user):
        """Test toggle_active admin action."""
        plan = SubscriptionPlan.objects.create(
            name="Test",
            slug="test",
            price=Decimal("99.99"),
            is_active=True,
        )

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = SubscriptionPlan.objects.filter(id=plan.id)
        plan_admin.toggle_active(request, queryset)

        plan.refresh_from_db()
        assert plan.is_active is False

        # Toggle again
        plan_admin.toggle_active(request, queryset)

        plan.refresh_from_db()
        assert plan.is_active is True

    def test_prepopulated_fields(self, plan_admin):
        """Test prepopulated fields configuration."""
        assert "slug" in plan_admin.prepopulated_fields
        assert plan_admin.prepopulated_fields["slug"] == ("name",)


class TestSubscriptionAdmin:
    """Tests for SubscriptionAdmin."""

    @pytest.fixture
    def subscription_admin(self, admin_site):
        """Create SubscriptionAdmin instance."""
        return SubscriptionAdmin(Subscription, admin_site)

    @pytest.fixture
    def subscription(self, regular_user):
        """Create test subscription."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
        )

        now = timezone.now()
        return Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

    def test_list_display(self, subscription_admin):
        """Test list_display configuration."""
        assert "user" in subscription_admin.list_display
        assert "plan" in subscription_admin.list_display
        assert "get_status_badge" in subscription_admin.list_display
        assert "next_billing_date" in subscription_admin.list_display

    def test_get_status_badge(self, subscription_admin, subscription):
        """Test get_status_badge method."""
        result = subscription_admin.get_status_badge(subscription)

        assert "Active" in result
        assert "#28a745" in result  # Green color for active

    def test_get_status_badge_colors(self, subscription_admin, subscription):
        """Test different status badge colors."""
        statuses_and_colors = [
            (SubscriptionStatus.PENDING, "#ffc107"),
            (SubscriptionStatus.TRIALING, "#17a2b8"),
            (SubscriptionStatus.ACTIVE, "#28a745"),
            (SubscriptionStatus.PAST_DUE, "#fd7e14"),
            (SubscriptionStatus.PAUSED, "#6c757d"),
            (SubscriptionStatus.CANCELLED, "#343a40"),
            (SubscriptionStatus.EXPIRED, "#dc3545"),
        ]

        for status, color in statuses_and_colors:
            subscription.status = status
            subscription.save()

            result = subscription_admin.get_status_badge(subscription)
            assert color in result

    def test_get_payment_count(self, subscription_admin, subscription):
        """Test get_payment_count method."""
        now = timezone.now()

        # Create successful payments
        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="failure",
            period_start=now + timedelta(days=30),
            period_end=now + timedelta(days=60),
        )

        count = subscription_admin.get_payment_count(subscription)
        assert count == 1  # Only successful payments

    def test_get_total_paid(self, subscription_admin, subscription):
        """Test get_total_paid method."""
        now = timezone.now()

        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now + timedelta(days=30),
            period_end=now + timedelta(days=60),
        )

        result = subscription_admin.get_total_paid(subscription)
        assert "199.98" in result
        assert "TRY" in result

    def test_get_payment_history(self, subscription_admin, subscription):
        """Test get_payment_history method."""
        now = timezone.now()

        # Create payment
        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
            attempt_number=1,
        )

        result = subscription_admin.get_payment_history(subscription)

        assert "<table" in result
        assert "99.99" in result
        assert "TRY" in result
        assert "#1" in result

    def test_get_payment_history_no_payments(self, subscription_admin, subscription):
        """Test payment history with no payments."""
        result = subscription_admin.get_payment_history(subscription)

        assert "No payments yet" in result

    def test_cancel_subscriptions_action(
        self, subscription_admin, request_factory, admin_user, subscription
    ):
        """Test cancel_subscriptions admin action."""
        from unittest.mock import patch

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = Subscription.objects.filter(id=subscription.id)

        with patch(
            "django_iyzico.subscription_manager.SubscriptionManager"
        ) as mock_manager_class:
            mock_manager = mock_manager_class.return_value

            subscription_admin.cancel_subscriptions(request, queryset)

            mock_manager.cancel_subscription.assert_called_once()

    def test_get_queryset_optimization(self, subscription_admin, request_factory, admin_user):
        """Test queryset optimization with select_related."""
        request = request_factory.get("/")
        request.user = admin_user

        queryset = subscription_admin.get_queryset(request)

        # Check that select_related was called
        select_related = queryset.query.select_related
        # select_related can be True (all) or a dict with nested structure
        if select_related is True:
            pass  # All related fields selected
        else:
            assert "user" in select_related or select_related is True
            assert "plan" in select_related or select_related is True


class TestSubscriptionPaymentAdmin:
    """Tests for SubscriptionPaymentAdmin."""

    @pytest.fixture
    def payment_admin(self, admin_site):
        """Create SubscriptionPaymentAdmin instance."""
        return SubscriptionPaymentAdmin(SubscriptionPayment, admin_site)

    @pytest.fixture
    def payment(self, regular_user):
        """Create test subscription payment."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
        )

        now = timezone.now()
        subscription = Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        return SubscriptionPayment.objects.create(
            subscription=subscription,
            user=regular_user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

    def test_list_display(self, payment_admin):
        """Test list_display includes subscription fields."""
        assert "subscription" in payment_admin.list_display
        assert "get_period_display" in payment_admin.list_display
        assert "attempt_number" in payment_admin.list_display
        assert "is_retry" in payment_admin.list_display

    def test_list_filter(self, payment_admin):
        """Test list_filter includes subscription fields."""
        assert "is_retry" in payment_admin.list_filter
        assert "is_prorated" in payment_admin.list_filter

    def test_get_period_display(self, payment_admin, payment):
        """Test get_period_display method."""
        result = payment_admin.get_period_display(payment)

        assert "-" in result  # Date range separator
        # Should contain formatted dates

    def test_readonly_fields_include_subscription(self, payment_admin):
        """Test readonly fields include subscription details."""
        assert "subscription" in payment_admin.readonly_fields
        assert "period_start" in payment_admin.readonly_fields
        assert "period_end" in payment_admin.readonly_fields
        assert "attempt_number" in payment_admin.readonly_fields

    def test_search_fields_include_subscription_user(self, payment_admin):
        """Test search fields include subscription user."""
        assert "subscription__user__email" in payment_admin.search_fields
        assert "subscription__user__username" in payment_admin.search_fields

    def test_get_queryset_optimization(self, payment_admin, request_factory, admin_user):
        """Test queryset optimization."""
        request = request_factory.get("/")
        request.user = admin_user

        queryset = payment_admin.get_queryset(request)

        # Check that select_related was called
        select_related = queryset.query.select_related
        # select_related can be True (all) or a dict with nested structure
        if select_related is True:
            pass  # All related fields selected
        else:
            assert "subscription" in select_related
            # Nested relations are in subscription dict
            subscription_related = select_related.get("subscription", {})
            assert "user" in subscription_related
            assert "plan" in subscription_related


class TestAdminFieldsets:
    """Tests for admin fieldset configuration."""

    def test_subscription_plan_fieldsets(self, admin_site):
        """Test SubscriptionPlan fieldsets."""
        admin = SubscriptionPlanAdmin(SubscriptionPlan, admin_site)

        fieldsets = admin.fieldsets
        assert len(fieldsets) == 5

        # Check sections exist
        section_names = [fs[0] for fs in fieldsets]
        assert "Basic Information" in section_names
        assert "Pricing" in section_names
        assert "Trial & Limits" in section_names
        assert "Features" in section_names
        assert "Metadata" in section_names

    def test_subscription_fieldsets(self, admin_site):
        """Test Subscription fieldsets."""
        admin = SubscriptionAdmin(Subscription, admin_site)

        fieldsets = admin.fieldsets
        assert len(fieldsets) == 5

        section_names = [fs[0] for fs in fieldsets]
        assert "Subscription Details" in section_names
        assert "Dates" in section_names
        assert "Payment Tracking" in section_names
        assert "Cancellation" in section_names
        assert "Metadata" in section_names

    def test_subscription_payment_fieldsets(self, admin_site):
        """Test SubscriptionPayment fieldsets include subscription section."""
        admin = SubscriptionPaymentAdmin(SubscriptionPayment, admin_site)

        fieldsets = admin.fieldsets

        # Should have inherited fieldsets plus subscription details
        section_names = [fs[0] for fs in fieldsets]
        assert "Subscription Details" in section_names


class TestPaymentMethodAdmin:
    """Tests for PaymentMethodAdmin."""

    @pytest.fixture
    def payment_method_admin(self, admin_site):
        """Create PaymentMethodAdmin instance."""
        return PaymentMethodAdmin(PaymentMethod, admin_site)

    @pytest.fixture
    def payment_method(self, regular_user):
        """Create test payment method."""
        return PaymentMethod.objects.create(
            user=regular_user,
            card_token="test_card_token_123",
            card_user_key="test_user_key_456",
            card_last_four="1234",
            card_brand=CardBrand.VISA,
            card_type="CREDIT_CARD",
            card_bank_name="Test Bank",
            card_holder_name="Test User",
            expiry_month=12,
            expiry_year=2030,
            is_default=True,
            is_active=True,
        )

    def test_list_display(self, payment_method_admin):
        """Test list_display configuration."""
        assert "user" in payment_method_admin.list_display
        assert "get_display_name" in payment_method_admin.list_display
        assert "get_card_brand_badge" in payment_method_admin.list_display
        assert "get_expiry_display" in payment_method_admin.list_display
        assert "is_default" in payment_method_admin.list_display
        assert "is_active" in payment_method_admin.list_display

    def test_get_card_brand_badge_visa(self, payment_method_admin, payment_method):
        """Test card brand badge for VISA."""
        result = payment_method_admin.get_card_brand_badge(payment_method)

        assert "Visa" in result
        assert "#1A1F71" in result  # Visa blue

    def test_get_card_brand_badge_mastercard(self, payment_method_admin, payment_method):
        """Test card brand badge for Mastercard."""
        payment_method.card_brand = CardBrand.MASTERCARD
        result = payment_method_admin.get_card_brand_badge(payment_method)

        assert "Mastercard" in result
        assert "#EB001B" in result  # Mastercard red

    def test_get_card_brand_badge_amex(self, payment_method_admin, payment_method):
        """Test card brand badge for Amex."""
        payment_method.card_brand = CardBrand.AMEX
        result = payment_method_admin.get_card_brand_badge(payment_method)

        assert "American Express" in result
        assert "#006FCF" in result  # Amex blue

    def test_get_card_brand_badge_troy(self, payment_method_admin, payment_method):
        """Test card brand badge for Troy."""
        payment_method.card_brand = CardBrand.TROY
        result = payment_method_admin.get_card_brand_badge(payment_method)

        assert "Troy" in result
        assert "#00A3E0" in result  # Troy blue

    def test_get_card_brand_badge_other(self, payment_method_admin, payment_method):
        """Test card brand badge for Other."""
        payment_method.card_brand = CardBrand.OTHER
        result = payment_method_admin.get_card_brand_badge(payment_method)

        assert "#6c757d" in result  # Gray

    def test_get_expiry_display_valid(self, payment_method_admin, payment_method):
        """Test expiry display for valid card."""
        result = payment_method_admin.get_expiry_display(payment_method)

        assert "12/2030" in result
        assert "EXPIRED" not in result
        assert "Expires Soon" not in result

    def test_get_expiry_display_expired(self, payment_method_admin, payment_method):
        """Test expiry display for expired card."""
        payment_method.expiry_month = 1
        payment_method.expiry_year = 2020
        result = payment_method_admin.get_expiry_display(payment_method)

        assert "1/2020" in result
        assert "EXPIRED" in result

    def test_get_expiry_display_expires_soon(self, payment_method_admin, payment_method):
        """Test expiry display for card expiring soon."""
        now = timezone.now()
        # Set to expire at end of current month (within 30 days)
        payment_method.expiry_month = now.month
        payment_method.expiry_year = now.year
        result = payment_method_admin.get_expiry_display(payment_method)

        assert "Expires Soon" in result

    def test_get_usage_stats_no_usage(self, payment_method_admin, payment_method):
        """Test usage stats when no usage."""
        result = payment_method_admin.get_usage_stats(payment_method)

        assert "No usage" in result

    def test_get_usage_stats_with_usage(self, payment_method_admin, payment_method, regular_user):
        """Test usage stats with payment history."""
        # Create subscription and payments
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
            currency="TRY",
        )

        now = timezone.now()
        subscription = Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        # Create successful payment
        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=regular_user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        result = payment_method_admin.get_usage_stats(payment_method)

        assert "payment(s)" in result
        assert "99.99" in result

    def test_get_detailed_usage_stats(self, payment_method_admin, payment_method, regular_user):
        """Test detailed usage stats display."""
        # Create subscription and payments
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test-detail",
            price=Decimal("99.99"),
            currency="USD",
        )

        now = timezone.now()
        subscription = Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        # Create payments
        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=regular_user,
            amount=Decimal("99.99"),
            currency="USD",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        # Update last_used_at
        payment_method.last_used_at = now
        payment_method.save()

        result = payment_method_admin.get_detailed_usage_stats(payment_method)

        assert "Payment Method Usage Analytics" in result
        assert "Active Subscriptions" in result
        assert "Successful Payments" in result
        assert "Total Amount Billed" in result
        assert "1234" in result  # Last four digits

    def test_get_detailed_usage_stats_never_used(self, payment_method_admin, payment_method):
        """Test detailed usage stats when never used."""
        payment_method.last_used_at = None
        result = payment_method_admin.get_detailed_usage_stats(payment_method)

        assert "Never used for payments" in result

    def test_deactivate_cards_action(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test deactivate_cards admin action."""
        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        payment_method_admin.deactivate_cards(request, queryset)

        payment_method.refresh_from_db()
        assert payment_method.is_active is False

    def test_deactivate_cards_action_already_inactive(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test deactivate_cards action on already inactive card."""
        payment_method.is_active = False
        payment_method.save()

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        payment_method_admin.deactivate_cards(request, queryset)

        # Should not change anything
        payment_method.refresh_from_db()
        assert payment_method.is_active is False

    def test_set_as_default_action(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test set_as_default admin action."""
        payment_method.is_default = False
        payment_method.save()

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        payment_method_admin.set_as_default(request, queryset)

        payment_method.refresh_from_db()
        assert payment_method.is_default is True

    def test_set_as_default_action_multiple_selected(
        self, payment_method_admin, request_factory, admin_user, payment_method, regular_user
    ):
        """Test set_as_default action with multiple cards selected."""
        # Create second payment method
        second_pm = PaymentMethod.objects.create(
            user=regular_user,
            card_token="token2",
            card_user_key="key2",
            card_last_four="5678",
            card_brand=CardBrand.MASTERCARD,
            expiry_month=12,
            expiry_year=2030,
            is_active=True,
        )

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id__in=[payment_method.id, second_pm.id])
        payment_method_admin.set_as_default(request, queryset)

        # Should not set default (error message shown instead)

    def test_set_as_default_action_inactive_card(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test set_as_default action on inactive card."""
        payment_method.is_active = False
        payment_method.is_default = False
        payment_method.save()

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        payment_method_admin.set_as_default(request, queryset)

        payment_method.refresh_from_db()
        # Should remain non-default due to inactive status
        assert payment_method.is_default is False

    def test_set_as_default_action_expired_card(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test set_as_default action on expired card."""
        payment_method.expiry_month = 1
        payment_method.expiry_year = 2020
        payment_method.is_default = False
        payment_method.save()

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        payment_method_admin.set_as_default(request, queryset)

        payment_method.refresh_from_db()
        # Should remain non-default due to expired status
        assert payment_method.is_default is False

    def test_delete_from_iyzico_action(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test delete_from_iyzico admin action."""
        from unittest.mock import patch

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)
        pm_id = payment_method.id
        card_token = payment_method.card_token
        card_user_key = payment_method.card_user_key

        with patch("django_iyzico.client.IyzicoClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.delete_card.return_value = None

            payment_method_admin.delete_from_iyzico(request, queryset)

            mock_client.delete_card.assert_called_once_with(
                card_token=card_token,
                card_user_key=card_user_key,
            )

            # Payment method should be deleted
            assert not PaymentMethod.objects.filter(id=pm_id).exists()

    def test_delete_from_iyzico_action_error(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test delete_from_iyzico action with error."""
        from unittest.mock import patch

        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = PaymentMethod.objects.filter(id=payment_method.id)

        with patch("django_iyzico.client.IyzicoClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.delete_card.side_effect = Exception("API Error")

            payment_method_admin.delete_from_iyzico(request, queryset)

            # Payment method should still exist
            assert PaymentMethod.objects.filter(id=payment_method.id).exists()

    def test_has_delete_permission_superuser(
        self, payment_method_admin, request_factory, admin_user, payment_method
    ):
        """Test delete permission for superuser."""
        request = request_factory.get("/")
        request.user = admin_user

        can_delete = payment_method_admin.has_delete_permission(request, payment_method)
        assert can_delete is True

    def test_has_delete_permission_regular_user(
        self, payment_method_admin, request_factory, regular_user, payment_method
    ):
        """Test delete permission for regular user."""
        request = request_factory.get("/")
        request.user = regular_user

        can_delete = payment_method_admin.has_delete_permission(request, payment_method)
        assert can_delete is False

    def test_get_queryset_optimization(
        self, payment_method_admin, request_factory, admin_user
    ):
        """Test queryset optimization with select_related."""
        request = request_factory.get("/")
        request.user = admin_user

        queryset = payment_method_admin.get_queryset(request)

        # Check that select_related was called
        select_related = queryset.query.select_related
        if select_related is True:
            pass
        else:
            assert "user" in select_related

    def test_fieldsets_configuration(self, payment_method_admin):
        """Test fieldsets are configured correctly."""
        fieldsets = payment_method_admin.fieldsets

        section_names = [fs[0] for fs in fieldsets]
        assert "User & Status" in section_names
        assert "Card Information" in section_names
        assert "Expiry" in section_names
        assert "Security Tokens (PCI DSS Compliant)" in section_names
        assert "Usage Analytics" in section_names
        assert "Metadata" in section_names

    def test_actions_configuration(self, payment_method_admin):
        """Test admin actions are configured."""
        assert "deactivate_cards" in payment_method_admin.actions
        assert "set_as_default" in payment_method_admin.actions
        assert "delete_from_iyzico" in payment_method_admin.actions


class TestSubscriptionAdminProcessBilling:
    """Test process_billing_manually action."""

    @pytest.fixture
    def subscription_admin(self, admin_site):
        """Create SubscriptionAdmin instance."""
        return SubscriptionAdmin(Subscription, admin_site)

    @pytest.fixture
    def subscription(self, regular_user):
        """Create test subscription."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test-billing",
            price=Decimal("99.99"),
        )

        now = timezone.now()
        return Subscription.objects.create(
            user=regular_user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

    def test_process_billing_manually_action(
        self, subscription_admin, request_factory, admin_user, subscription
    ):
        """Test process_billing_manually admin action shows warning."""
        request = request_factory.post("/")
        request.user = admin_user
        add_messages_support(request)

        queryset = Subscription.objects.filter(id=subscription.id)
        subscription_admin.process_billing_manually(request, queryset)

        # Should not raise - just shows warning message
