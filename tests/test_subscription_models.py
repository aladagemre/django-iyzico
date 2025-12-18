"""
Tests for subscription models.

Test coverage for SubscriptionPlan, Subscription, and SubscriptionPayment models.
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from django_iyzico.subscription_models import (
    BillingInterval,
    SubscriptionPlan,
    Subscription,
    SubscriptionPayment,
    SubscriptionStatus,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ===== SubscriptionPlan Tests =====


class TestSubscriptionPlan:
    """Tests for SubscriptionPlan model."""

    def test_create_subscription_plan(self):
        """Test creating a basic subscription plan."""
        plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            slug="basic",
            price=Decimal("99.99"),
            currency="TRY",
            billing_interval=BillingInterval.MONTHLY,
        )

        assert plan.name == "Basic Plan"
        assert plan.price == Decimal("99.99")
        assert plan.currency == "TRY"
        assert plan.billing_interval == BillingInterval.MONTHLY
        assert plan.billing_interval_count == 1
        assert plan.trial_period_days == 0
        assert plan.is_active is True

    def test_subscription_plan_str(self):
        """Test string representation."""
        plan = SubscriptionPlan.objects.create(
            name="Premium",
            slug="premium",
            price=Decimal("199.99"),
            currency="TRY",
            billing_interval=BillingInterval.MONTHLY,
        )

        assert str(plan) == "Premium (199.99 TRY/Monthly)"

    def test_subscription_plan_with_trial(self):
        """Test plan with trial period."""
        plan = SubscriptionPlan.objects.create(
            name="Trial Plan",
            slug="trial",
            price=Decimal("49.99"),
            trial_period_days=14,
        )

        assert plan.trial_period_days == 14
        assert plan.get_total_trial_days() == 14

    def test_quarterly_billing_interval(self):
        """Test quarterly billing interval."""
        plan = SubscriptionPlan.objects.create(
            name="Quarterly",
            slug="quarterly",
            price=Decimal("249.99"),
            billing_interval=BillingInterval.QUARTERLY,
        )

        assert plan.get_billing_interval_days() == 90

    def test_custom_billing_interval_count(self):
        """Test custom billing interval count (e.g., every 3 months)."""
        plan = SubscriptionPlan.objects.create(
            name="Every 3 Months",
            slug="three-months",
            price=Decimal("299.99"),
            billing_interval=BillingInterval.MONTHLY,
            billing_interval_count=3,
        )

        assert plan.billing_interval_count == 3
        assert plan.get_billing_interval_days() == 90  # 30 days * 3

    def test_plan_features_json(self):
        """Test storing features as JSON."""
        features = {
            "storage": "100GB",
            "users": 10,
            "support": "24/7",
        }

        plan = SubscriptionPlan.objects.create(
            name="Enterprise",
            slug="enterprise",
            price=Decimal("999.99"),
            features=features,
        )

        assert plan.features == features
        assert plan.features["storage"] == "100GB"
        assert plan.features["users"] == 10

    def test_max_subscribers_limit(self):
        """Test max subscribers limit."""
        plan = SubscriptionPlan.objects.create(
            name="Limited",
            slug="limited",
            price=Decimal("99.99"),
            max_subscribers=100,
        )

        assert plan.max_subscribers == 100
        assert plan.can_accept_subscribers() is True

    def test_inactive_plan_cannot_accept_subscribers(self):
        """Test inactive plan cannot accept subscribers."""
        plan = SubscriptionPlan.objects.create(
            name="Inactive",
            slug="inactive",
            price=Decimal("99.99"),
            is_active=False,
        )

        assert plan.can_accept_subscribers() is False

    def test_plan_at_capacity_cannot_accept_subscribers(self, user):
        """Test plan at capacity cannot accept subscribers."""
        plan = SubscriptionPlan.objects.create(
            name="Limited",
            slug="limited",
            price=Decimal("99.99"),
            max_subscribers=1,
        )

        # Create one active subscription
        Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        assert plan.can_accept_subscribers() is False

    def test_validation_negative_price(self):
        """Test validation for negative price."""
        with pytest.raises(ValidationError):
            plan = SubscriptionPlan(
                name="Invalid",
                slug="invalid",
                price=Decimal("-10.00"),
            )
            plan.full_clean()

    def test_validation_negative_trial_period(self):
        """Test validation for negative trial period."""
        plan = SubscriptionPlan(
            name="Invalid Trial",
            slug="invalid-trial",
            price=Decimal("99.99"),
            trial_period_days=-7,
        )

        with pytest.raises(ValidationError) as exc_info:
            plan.clean()

        assert "trial_period_days" in exc_info.value.message_dict

    def test_sort_order(self):
        """Test plans are ordered by sort_order and price."""
        plan1 = SubscriptionPlan.objects.create(
            name="Expensive",
            slug="expensive",
            price=Decimal("999.99"),
            sort_order=2,
        )

        plan2 = SubscriptionPlan.objects.create(
            name="Cheap",
            slug="cheap",
            price=Decimal("9.99"),
            sort_order=1,
        )

        plans = list(SubscriptionPlan.objects.all())
        assert plans[0] == plan2  # Lower sort_order first
        assert plans[1] == plan1


# ===== Subscription Tests =====


class TestSubscription:
    """Tests for Subscription model."""

    @pytest.fixture
    def plan(self):
        """Create a test plan."""
        return SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
            currency="TRY",
        )

    def test_create_subscription(self, user, plan):
        """Test creating a subscription."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        assert subscription.user == user
        assert subscription.plan == plan
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.failed_payment_count == 0
        assert subscription.cancel_at_period_end is False

    def test_subscription_str(self, user, plan):
        """Test string representation."""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        expected = f"{user} - Test Plan (Active)"
        assert str(subscription) == expected

    def test_subscription_is_active(self, user, plan):
        """Test is_active method."""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        assert subscription.is_active() is True

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.save()

        assert subscription.is_active() is False

    def test_subscription_is_trialing(self, user, plan):
        """Test is_trialing method."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.TRIALING,
            start_date=now,
            trial_end_date=now + timedelta(days=14),
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
            next_billing_date=now + timedelta(days=14),
        )

        assert subscription.is_trialing() is True

        # Trial ended
        subscription.trial_end_date = now - timedelta(days=1)
        subscription.save()

        assert subscription.is_trialing() is False

    def test_days_until_renewal(self, user, plan):
        """Test days_until_renewal calculation."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=7),
        )

        days = subscription.days_until_renewal()
        assert days >= 6 and days <= 7  # Account for time passing

    def test_is_past_due(self, user, plan):
        """Test is_past_due method."""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
            failed_payment_count=2,
        )

        assert subscription.is_past_due() is True

    def test_can_be_renewed(self, user, plan):
        """Test can_be_renewed method."""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30),
        )

        assert subscription.can_be_renewed() is True

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.save()

        assert subscription.can_be_renewed() is False

    def test_should_retry_payment(self, user, plan):
        """Test should_retry_payment logic."""
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now(),
            failed_payment_count=2,
        )

        assert subscription.should_retry_payment(max_retries=3) is True

        subscription.failed_payment_count = 3
        subscription.save()

        assert subscription.should_retry_payment(max_retries=3) is False

    def test_get_total_amount_paid(self, user, plan):
        """Test calculating total amount paid."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        # Create successful payments
        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now + timedelta(days=30),
            period_end=now + timedelta(days=60),
        )

        total = subscription.get_total_amount_paid()
        assert total == Decimal("199.98")

    def test_get_successful_payment_count(self, user, plan):
        """Test counting successful payments."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
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
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="failure",
            period_start=now + timedelta(days=30),
            period_end=now + timedelta(days=60),
        )

        count = subscription.get_successful_payment_count()
        assert count == 1

    def test_validation_period_end_after_start(self, user, plan):
        """Test validation for period dates."""
        now = timezone.now()

        subscription = Subscription(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now - timedelta(days=1),  # Invalid
            next_billing_date=now,
        )

        with pytest.raises(ValidationError) as exc_info:
            subscription.clean()

        assert "current_period_end" in exc_info.value.message_dict


# ===== SubscriptionPayment Tests =====


class TestSubscriptionPayment:
    """Tests for SubscriptionPayment model."""

    @pytest.fixture
    def subscription(self, user):
        """Create a test subscription."""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            price=Decimal("99.99"),
        )

        now = timezone.now()

        return Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

    def test_create_subscription_payment(self, user, subscription):
        """Test creating a subscription payment."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert payment.subscription == subscription
        assert payment.amount == Decimal("99.99")
        assert payment.attempt_number == 1
        assert payment.is_retry is False
        assert payment.is_prorated is False

    def test_subscription_payment_str(self, user, subscription):
        """Test string representation."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        expected = f"Payment for {subscription} - 99.99 TRY"
        assert str(payment) == expected

    def test_retry_payment(self, user, subscription):
        """Test retry payment tracking."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="failure",
            period_start=now,
            period_end=now + timedelta(days=30),
            attempt_number=2,
            is_retry=True,
        )

        assert payment.is_retry is True
        assert payment.attempt_number == 2
        assert str(payment).endswith("(Retry #2) - 99.99 TRY")

    def test_prorated_payment(self, user, subscription):
        """Test prorated payment."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=15),
            is_prorated=True,
            prorated_amount=Decimal("49.99"),
        )

        assert payment.is_prorated is True
        assert payment.get_effective_amount() == Decimal("49.99")

    def test_get_effective_amount_not_prorated(self, user, subscription):
        """Test effective amount for non-prorated payment."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert payment.get_effective_amount() == Decimal("99.99")

    def test_is_successful(self, user, subscription):
        """Test is_successful method."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert payment.is_successful() is True

    def test_is_failed(self, user, subscription):
        """Test is_failed method."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="failure",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert payment.is_failed() is True

    def test_get_period_duration_days(self, user, subscription):
        """Test calculating period duration."""
        now = timezone.now()

        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert payment.get_period_duration_days() == 30

    def test_validation_retry_with_first_attempt(self, user, subscription):
        """Test validation for retry flag with first attempt."""
        now = timezone.now()

        payment = SubscriptionPayment(
            subscription=subscription,
            user=user,
            amount=Decimal("99.99"),
            currency="TRY",
            status="success",
            period_start=now,
            period_end=now + timedelta(days=30),
            attempt_number=1,
            is_retry=True,  # Invalid - retry with attempt_number=1
        )

        with pytest.raises(ValidationError) as exc_info:
            payment.clean()

        assert "is_retry" in exc_info.value.message_dict


# ===== Fixtures =====


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
