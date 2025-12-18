"""
Tests for SubscriptionManager.

Comprehensive tests for subscription business logic.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.contrib.auth import get_user_model
from django.utils import timezone

from django_iyzico.client import IyzicoClient
from django_iyzico.exceptions import IyzicoAPIException, IyzicoValidationException
from django_iyzico.subscription_manager import SubscriptionManager
from django_iyzico.subscription_models import (
    BillingInterval,
    SubscriptionPlan,
    Subscription,
    SubscriptionPayment,
    SubscriptionStatus,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User',
    )


@pytest.fixture
def plan():
    """Create test subscription plan."""
    return SubscriptionPlan.objects.create(
        name='Premium Plan',
        slug='premium',
        price=Decimal('99.99'),
        currency='TRY',
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=14,
    )


@pytest.fixture
def plan_without_trial():
    """Create plan without trial."""
    return SubscriptionPlan.objects.create(
        name='Basic Plan',
        slug='basic',
        price=Decimal('49.99'),
        currency='TRY',
        billing_interval=BillingInterval.MONTHLY,
        trial_period_days=0,
    )


@pytest.fixture
def payment_method():
    """Mock payment method data."""
    return {
        'cardHolderName': 'Test User',
        'cardNumber': '5528790000000008',
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
    }


@pytest.fixture
def mock_client():
    """Mock Iyzico client."""
    with patch('django_iyzico.subscription_manager.IyzicoClient') as mock:
        client = Mock(spec=IyzicoClient)
        mock.return_value = client
        yield client


class TestSubscriptionManagerCreate:
    """Tests for create_subscription method."""

    def test_create_subscription_with_trial(self, user, plan, payment_method):
        """Test creating subscription with trial period."""
        manager = SubscriptionManager()

        with patch.object(manager, '_create_subscription_payment'):
            subscription = manager.create_subscription(
                user=user,
                plan=plan,
                payment_method=payment_method,
                trial=True,
            )

        assert subscription.user == user
        assert subscription.plan == plan
        assert subscription.status == SubscriptionStatus.TRIALING
        assert subscription.trial_end_date is not None
        assert subscription.trial_end_date > subscription.start_date

        # Should not process initial payment during trial
        manager._create_subscription_payment.assert_not_called()

    def test_create_subscription_without_trial(self, user, plan_without_trial, payment_method):
        """Test creating subscription without trial (immediate billing)."""
        manager = SubscriptionManager()

        # Mock successful payment
        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        with patch.object(manager, '_create_subscription_payment', return_value=mock_payment):
            subscription = manager.create_subscription(
                user=user,
                plan=plan_without_trial,
                payment_method=payment_method,
                trial=False,
            )

        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.trial_end_date is None
        manager._create_subscription_payment.assert_called_once()

    def test_create_subscription_with_failed_initial_payment(self, user, plan_without_trial, payment_method):
        """Test subscription creation when initial payment fails."""
        manager = SubscriptionManager()

        # Mock failed payment
        mock_payment = Mock()
        mock_payment.is_successful.return_value = False
        mock_payment.error_message = 'Card declined'

        with patch.object(manager, '_create_subscription_payment', return_value=mock_payment):
            subscription = manager.create_subscription(
                user=user,
                plan=plan_without_trial,
                payment_method=payment_method,
            )

        assert subscription.status == SubscriptionStatus.PAST_DUE
        assert subscription.failed_payment_count == 1
        assert subscription.last_payment_error == 'Card declined'

    def test_create_subscription_with_custom_start_date(self, user, plan, payment_method):
        """Test creating subscription with custom start date."""
        manager = SubscriptionManager()
        custom_start = timezone.now() + timedelta(days=7)

        with patch.object(manager, '_create_subscription_payment'):
            subscription = manager.create_subscription(
                user=user,
                plan=plan,
                payment_method=payment_method,
                start_date=custom_start,
                trial=False,
            )

        assert subscription.start_date.date() == custom_start.date()

    def test_create_subscription_with_metadata(self, user, plan, payment_method):
        """Test creating subscription with metadata."""
        manager = SubscriptionManager()
        metadata = {'source': 'web', 'campaign': 'summer2025'}

        with patch.object(manager, '_create_subscription_payment'):
            subscription = manager.create_subscription(
                user=user,
                plan=plan,
                payment_method=payment_method,
                metadata=metadata,
            )

        assert subscription.metadata == metadata

    def test_create_subscription_inactive_plan_raises_error(self, user, payment_method):
        """Test creating subscription with inactive plan raises error."""
        inactive_plan = SubscriptionPlan.objects.create(
            name='Inactive',
            slug='inactive',
            price=Decimal('99.99'),
            is_active=False,
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException) as exc_info:
            manager.create_subscription(
                user=user,
                plan=inactive_plan,
                payment_method=payment_method,
            )

        assert 'not available' in str(exc_info.value)

    def test_create_subscription_plan_at_capacity_raises_error(self, user, payment_method):
        """Test creating subscription when plan is at capacity."""
        limited_plan = SubscriptionPlan.objects.create(
            name='Limited',
            slug='limited',
            price=Decimal('99.99'),
            max_subscribers=1,
        )

        # Create first subscription
        now = timezone.now()
        Subscription.objects.create(
            user=user,
            plan=limited_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        # Try to create second subscription
        user2 = User.objects.create_user(username='user2', email='user2@example.com')
        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException) as exc_info:
            manager.create_subscription(
                user=user2,
                plan=limited_plan,
                payment_method=payment_method,
            )

        assert 'capacity' in str(exc_info.value)

    def test_create_subscription_signal_sent(self, user, plan, payment_method):
        """Test that subscription_created signal is sent."""
        manager = SubscriptionManager()

        with patch('django_iyzico.subscription_manager.subscription_created') as mock_signal:
            with patch.object(manager, '_create_subscription_payment'):
                subscription = manager.create_subscription(
                    user=user,
                    plan=plan,
                    payment_method=payment_method,
                )

            mock_signal.send.assert_called_once()


class TestSubscriptionManagerBilling:
    """Tests for process_billing method."""

    @pytest.fixture
    def active_subscription(self, user, plan):
        """Create active subscription."""
        now = timezone.now()
        return Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now,
        )

    def test_process_billing_success(self, active_subscription, payment_method):
        """Test successful billing processing."""
        manager = SubscriptionManager()

        # Mock successful payment
        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        with patch.object(manager, '_create_subscription_payment', return_value=mock_payment):
            payment = manager.process_billing(
                subscription=active_subscription,
                payment_method=payment_method,
            )

        assert payment.is_successful()
        active_subscription.refresh_from_db()
        assert active_subscription.status == SubscriptionStatus.ACTIVE
        assert active_subscription.failed_payment_count == 0

    def test_process_billing_failure(self, active_subscription, payment_method):
        """Test failed billing processing."""
        manager = SubscriptionManager()

        # Mock failed payment
        mock_payment = Mock()
        mock_payment.is_successful.return_value = False
        mock_payment.error_message = 'Insufficient funds'

        with patch.object(manager, '_create_subscription_payment', return_value=mock_payment):
            payment = manager.process_billing(
                subscription=active_subscription,
                payment_method=payment_method,
            )

        assert not payment.is_successful()
        active_subscription.refresh_from_db()
        assert active_subscription.status == SubscriptionStatus.PAST_DUE
        assert active_subscription.failed_payment_count == 1

    def test_process_billing_retry(self, user, plan, payment_method):
        """Test billing retry for past due subscription."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now,
            failed_payment_count=2,
        )

        manager = SubscriptionManager()

        # Mock successful retry
        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        with patch.object(manager, '_create_subscription_payment', return_value=mock_payment) as mock_create:
            manager.process_billing(
                subscription=subscription,
                payment_method=payment_method,
            )

            # Should be marked as retry with attempt #3
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs['is_retry'] is True
            assert call_kwargs['attempt_number'] == 3

    def test_process_billing_prevents_duplicate(self, active_subscription, payment_method):
        """Test prevention of duplicate billing within 1 hour."""
        manager = SubscriptionManager()

        # Create recent successful payment
        SubscriptionPayment.objects.create(
            subscription=active_subscription,
            user=active_subscription.user,
            amount=Decimal('99.99'),
            currency='TRY',
            status='success',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30),
        )

        with patch.object(manager, '_create_subscription_payment') as mock_create:
            payment = manager.process_billing(
                subscription=active_subscription,
                payment_method=payment_method,
            )

        # Should return existing payment, not create new one
        mock_create.assert_not_called()
        assert payment.status == 'success'

    def test_process_billing_invalid_subscription_raises_error(self, user, plan, payment_method):
        """Test billing cancelled subscription raises error."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.CANCELLED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException) as exc_info:
            manager.process_billing(
                subscription=subscription,
                payment_method=payment_method,
            )

        assert 'cannot be billed' in str(exc_info.value)


class TestSubscriptionManagerCancel:
    """Tests for cancel_subscription method."""

    @pytest.fixture
    def active_subscription(self, user, plan):
        """Create active subscription."""
        now = timezone.now()
        return Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=15),
            current_period_start=now - timedelta(days=15),
            current_period_end=now + timedelta(days=15),
            next_billing_date=now + timedelta(days=15),
        )

    def test_cancel_at_period_end(self, active_subscription):
        """Test cancelling subscription at period end."""
        manager = SubscriptionManager()

        subscription = manager.cancel_subscription(
            subscription=active_subscription,
            at_period_end=True,
            reason='User requested',
        )

        assert subscription.cancel_at_period_end is True
        assert subscription.cancelled_at is not None
        assert subscription.cancellation_reason == 'User requested'
        assert subscription.status == SubscriptionStatus.ACTIVE  # Still active until period end
        assert subscription.ended_at is None

    def test_cancel_immediately(self, active_subscription):
        """Test immediate cancellation."""
        manager = SubscriptionManager()

        subscription = manager.cancel_subscription(
            subscription=active_subscription,
            at_period_end=False,
            reason='Fraud detected',
        )

        assert subscription.status == SubscriptionStatus.CANCELLED
        assert subscription.ended_at is not None
        assert subscription.cancellation_reason == 'Fraud detected'

    def test_cancel_already_cancelled_subscription(self, user, plan):
        """Test cancelling already cancelled subscription."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.CANCELLED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
            cancelled_at=now,
        )

        manager = SubscriptionManager()

        # Should not raise error, just return
        result = manager.cancel_subscription(subscription=subscription)
        assert result == subscription

    def test_cancel_signal_sent(self, active_subscription):
        """Test that subscription_cancelled signal is sent."""
        manager = SubscriptionManager()

        with patch('django_iyzico.subscription_manager.subscription_cancelled') as mock_signal:
            manager.cancel_subscription(
                subscription=active_subscription,
                at_period_end=True,
            )

            mock_signal.send.assert_called_once()


class TestSubscriptionManagerPauseResume:
    """Tests for pause and resume methods."""

    @pytest.fixture
    def active_subscription(self, user, plan):
        """Create active subscription."""
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

    def test_pause_subscription(self, active_subscription):
        """Test pausing active subscription."""
        manager = SubscriptionManager()

        subscription = manager.pause_subscription(active_subscription)

        assert subscription.status == SubscriptionStatus.PAUSED

    def test_pause_non_active_subscription_raises_error(self, user, plan):
        """Test pausing non-active subscription raises error."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.CANCELLED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException):
            manager.pause_subscription(subscription)

    def test_resume_subscription(self, user, plan):
        """Test resuming paused subscription."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAUSED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        subscription = manager.resume_subscription(subscription)

        assert subscription.status == SubscriptionStatus.ACTIVE

    def test_resume_non_paused_subscription_raises_error(self, active_subscription):
        """Test resuming non-paused subscription raises error."""
        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException):
            manager.resume_subscription(active_subscription)

    def test_pause_signal_sent(self, active_subscription):
        """Test that subscription_paused signal is sent."""
        manager = SubscriptionManager()

        with patch('django_iyzico.subscription_manager.subscription_paused') as mock_signal:
            manager.pause_subscription(active_subscription)

            mock_signal.send.assert_called_once()

    def test_resume_signal_sent(self, user, plan):
        """Test that subscription_resumed signal is sent."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAUSED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with patch('django_iyzico.subscription_manager.subscription_resumed') as mock_signal:
            manager.resume_subscription(subscription)

            mock_signal.send.assert_called_once()


class TestSubscriptionManagerUpgrade:
    """Tests for upgrade_subscription method."""

    @pytest.fixture
    def basic_plan(self):
        """Create basic plan."""
        return SubscriptionPlan.objects.create(
            name='Basic',
            slug='basic',
            price=Decimal('49.99'),
            currency='TRY',
        )

    @pytest.fixture
    def premium_plan(self):
        """Create premium plan."""
        return SubscriptionPlan.objects.create(
            name='Premium',
            slug='premium',
            price=Decimal('99.99'),
            currency='TRY',
        )

    @pytest.fixture
    def basic_subscription(self, user, basic_plan):
        """Create subscription on basic plan."""
        now = timezone.now()
        return Subscription.objects.create(
            user=user,
            plan=basic_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=15),
            current_period_start=now - timedelta(days=15),
            current_period_end=now + timedelta(days=15),
            next_billing_date=now + timedelta(days=15),
        )

    def test_upgrade_subscription(self, basic_subscription, premium_plan):
        """Test upgrading subscription to higher tier."""
        manager = SubscriptionManager()

        subscription = manager.upgrade_subscription(
            subscription=basic_subscription,
            new_plan=premium_plan,
            prorate=False,
        )

        assert subscription.plan == premium_plan

    def test_upgrade_with_lower_price_raises_error(self, user, premium_plan, basic_plan):
        """Test upgrading to lower-priced plan raises error."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=premium_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException) as exc_info:
            manager.upgrade_subscription(
                subscription=subscription,
                new_plan=basic_plan,
            )

        assert 'higher-tier' in str(exc_info.value)

    def test_upgrade_non_active_subscription_raises_error(self, user, basic_plan, premium_plan):
        """Test upgrading non-active subscription raises error."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=basic_plan,
            status=SubscriptionStatus.CANCELLED,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException):
            manager.upgrade_subscription(
                subscription=subscription,
                new_plan=premium_plan,
            )


class TestSubscriptionManagerDowngrade:
    """Tests for downgrade_subscription method."""

    @pytest.fixture
    def basic_plan(self):
        """Create basic plan."""
        return SubscriptionPlan.objects.create(
            name='Basic',
            slug='basic',
            price=Decimal('49.99'),
            currency='TRY',
        )

    @pytest.fixture
    def premium_plan(self):
        """Create premium plan."""
        return SubscriptionPlan.objects.create(
            name='Premium',
            slug='premium',
            price=Decimal('99.99'),
            currency='TRY',
        )

    @pytest.fixture
    def premium_subscription(self, user, premium_plan):
        """Create subscription on premium plan."""
        now = timezone.now()
        return Subscription.objects.create(
            user=user,
            plan=premium_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=15),
            current_period_start=now - timedelta(days=15),
            current_period_end=now + timedelta(days=15),
            next_billing_date=now + timedelta(days=15),
        )

    def test_downgrade_at_period_end(self, premium_subscription, basic_plan):
        """Test downgrading subscription at period end."""
        manager = SubscriptionManager()

        subscription = manager.downgrade_subscription(
            subscription=premium_subscription,
            new_plan=basic_plan,
            at_period_end=True,
        )

        assert subscription.plan != basic_plan  # Not changed yet
        assert 'pending_downgrade' in subscription.metadata
        assert subscription.metadata['pending_downgrade']['new_plan_id'] == basic_plan.id

    def test_downgrade_immediately(self, premium_subscription, basic_plan):
        """Test immediate downgrade."""
        manager = SubscriptionManager()

        subscription = manager.downgrade_subscription(
            subscription=premium_subscription,
            new_plan=basic_plan,
            at_period_end=False,
        )

        assert subscription.plan == basic_plan

    def test_downgrade_with_higher_price_raises_error(self, user, basic_plan, premium_plan):
        """Test downgrading to higher-priced plan raises error."""
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=user,
            plan=basic_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        manager = SubscriptionManager()

        with pytest.raises(IyzicoValidationException) as exc_info:
            manager.downgrade_subscription(
                subscription=subscription,
                new_plan=premium_plan,
            )

        assert 'lower-tier' in str(exc_info.value)


class TestSubscriptionManagerPaymentCreation:
    """Tests for _create_subscription_payment method."""

    @pytest.fixture
    def subscription(self, user, plan):
        """Create test subscription."""
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

    @patch('django_iyzico.subscription_manager.IyzicoClient')
    def test_create_subscription_payment_success(self, mock_client_class, subscription, payment_method):
        """Test successful payment creation."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 'success'
        mock_response.payment_id = 'PAY123'
        mock_response.error_code = None
        mock_response.error_message = None

        mock_client = Mock()
        mock_client.create_payment.return_value = mock_response
        mock_client_class.return_value = mock_client

        manager = SubscriptionManager()
        payment = manager._create_subscription_payment(
            subscription=subscription,
            payment_method=payment_method,
        )

        assert payment.status == 'success'
        assert payment.payment_id == 'PAY123'
        assert payment.subscription == subscription
        assert payment.attempt_number == 1
        assert payment.is_retry is False

    @patch('django_iyzico.subscription_manager.IyzicoClient')
    def test_create_subscription_payment_failure(self, mock_client_class, subscription, payment_method):
        """Test failed payment creation."""
        # Mock failed response
        mock_response = Mock()
        mock_response.status = 'failure'
        mock_response.payment_id = None
        mock_response.error_code = 'CARD_DECLINED'
        mock_response.error_message = 'Card was declined'

        mock_client = Mock()
        mock_client.create_payment.return_value = mock_response
        mock_client_class.return_value = mock_client

        manager = SubscriptionManager()
        payment = manager._create_subscription_payment(
            subscription=subscription,
            payment_method=payment_method,
        )

        assert payment.status == 'failure'
        assert payment.error_message == 'Card was declined'

    @patch('django_iyzico.subscription_manager.IyzicoClient')
    def test_create_subscription_payment_api_exception(self, mock_client_class, subscription, payment_method):
        """Test payment creation with API exception."""
        mock_client = Mock()
        mock_client.create_payment.side_effect = IyzicoAPIException('API Error')
        mock_client_class.return_value = mock_client

        manager = SubscriptionManager()
        payment = manager._create_subscription_payment(
            subscription=subscription,
            payment_method=payment_method,
        )

        assert payment.status == 'failure'
        assert 'API Error' in payment.error_message

    def test_create_subscription_payment_updates_last_attempt(self, subscription, payment_method):
        """Test that last_payment_attempt is updated."""
        manager = SubscriptionManager()

        with patch.object(manager.client, 'create_payment'):
            manager._create_subscription_payment(
                subscription=subscription,
                payment_method=payment_method,
            )

        subscription.refresh_from_db()
        assert subscription.last_payment_attempt is not None
