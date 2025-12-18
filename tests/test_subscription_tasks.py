"""
Tests for subscription Celery tasks.

Tests for automated billing, retries, and notifications.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, call

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone

from django_iyzico.subscription_models import (
    SubscriptionPlan,
    Subscription,
    SubscriptionPayment,
    SubscriptionStatus,
    BillingInterval,
)
from django_iyzico.tasks import (
    process_due_subscriptions,
    retry_failed_payments,
    expire_cancelled_subscriptions,
    check_trial_expiration,
    charge_subscription,
    send_payment_notification,
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
    """Create test plan."""
    return SubscriptionPlan.objects.create(
        name='Test Plan',
        slug='test',
        price=Decimal('99.99'),
        currency='TRY',
        billing_interval=BillingInterval.MONTHLY,
    )


class TestProcessDueSubscriptions:
    """Tests for process_due_subscriptions task."""

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_process_due_subscriptions_success(self, mock_manager_class, mock_get_payment, user, plan):
        """Test processing due subscriptions successfully."""
        now = timezone.now()

        # Create subscription due for billing
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now - timedelta(hours=1),  # Past due
        )

        # Mock payment method and successful payment
        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        # Run task
        with patch('django_iyzico.tasks.send_payment_notification') as mock_notify:
            result = process_due_subscriptions()

        assert result['processed'] == 1
        assert result['successful'] == 1
        assert result['failed'] == 0

        mock_manager.process_billing.assert_called_once()
        mock_notify.delay.assert_called_once()

    @patch('django_iyzico.tasks._get_stored_payment_method')
    def test_process_due_subscriptions_no_payment_method(self, mock_get_payment, user, plan):
        """Test handling subscription with no payment method."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now - timedelta(hours=1),
        )

        # No payment method available
        mock_get_payment.return_value = None

        result = process_due_subscriptions()

        assert result['processed'] == 0
        assert result['failed'] == 1

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_process_due_subscriptions_payment_failure(self, mock_manager_class, mock_get_payment, user, plan):
        """Test processing subscription with payment failure."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now - timedelta(hours=1),
        )

        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        # Mock failed payment
        mock_payment = Mock()
        mock_payment.is_successful.return_value = False

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        with patch('django_iyzico.tasks.send_payment_notification'):
            result = process_due_subscriptions()

        assert result['processed'] == 1
        assert result['successful'] == 0
        assert result['failed'] == 1

    def test_process_due_subscriptions_skips_future(self, user, plan):
        """Test that future subscriptions are not processed."""
        now = timezone.now()

        # Create subscription not yet due
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),  # Future
        )

        result = process_due_subscriptions()

        assert result['processed'] == 0


class TestRetryFailedPayments:
    """Tests for retry_failed_payments task."""

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_retry_failed_payments_success(self, mock_manager_class, mock_get_payment, user, plan):
        """Test successful payment retry."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now,
            failed_payment_count=1,
            last_payment_attempt=now - timedelta(days=1),  # 24 hours ago
        )

        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        # Mock successful retry
        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        with patch('django_iyzico.tasks.send_payment_notification'):
            result = retry_failed_payments()

        assert result['retried'] == 1
        assert result['successful'] == 1
        assert result['failed'] == 0

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_retry_failed_payments_max_retries_reached(self, mock_manager_class, mock_get_payment, user, plan):
        """Test subscription expired after max retries."""
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
            last_payment_attempt=now - timedelta(days=1),
        )

        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        # Mock failed retry
        mock_payment = Mock()
        mock_payment.is_successful.return_value = False

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        with patch('django_iyzico.tasks.send_payment_notification') as mock_notify:
            with patch('django_iyzico.tasks.getattr', return_value=3):  # Max retries = 3
                result = retry_failed_payments()

        subscription.refresh_from_db()
        assert subscription.status == SubscriptionStatus.EXPIRED
        assert subscription.ended_at is not None

    def test_retry_failed_payments_skips_recent_attempts(self, user, plan):
        """Test that recent failed attempts are not retried yet."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now,
            failed_payment_count=1,
            last_payment_attempt=now - timedelta(hours=1),  # Too recent
        )

        result = retry_failed_payments()

        assert result['retried'] == 0

    @patch('django_iyzico.tasks._get_stored_payment_method')
    def test_retry_no_payment_method_expires(self, mock_get_payment, user, plan):
        """Test subscription expires when no payment method after max retries."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now,
            next_billing_date=now,
            failed_payment_count=2,  # At max retries - 1
            last_payment_attempt=now - timedelta(days=1),
        )

        mock_get_payment.return_value = None

        with patch('django_iyzico.tasks.getattr', return_value=3):
            result = retry_failed_payments()

        subscription.refresh_from_db()
        assert subscription.status == SubscriptionStatus.EXPIRED


class TestExpireCancelledSubscriptions:
    """Tests for expire_cancelled_subscriptions task."""

    def test_expire_cancelled_subscriptions(self, user, plan):
        """Test expiring subscriptions marked for cancellation."""
        now = timezone.now()

        # Create subscription marked for cancellation
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now - timedelta(days=30),
            current_period_start=now - timedelta(days=30),
            current_period_end=now - timedelta(hours=1),  # Period ended
            next_billing_date=now - timedelta(hours=1),
            cancel_at_period_end=True,
            cancelled_at=now - timedelta(days=5),
        )

        with patch('django_iyzico.tasks.send_payment_notification'):
            count = expire_cancelled_subscriptions()

        assert count == 1
        subscription.refresh_from_db()
        assert subscription.status == SubscriptionStatus.EXPIRED
        assert subscription.ended_at is not None

    def test_expire_cancelled_subscriptions_skips_future(self, user, plan):
        """Test that subscriptions with future period end are not expired."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=15),  # Future
            next_billing_date=now + timedelta(days=15),
            cancel_at_period_end=True,
        )

        count = expire_cancelled_subscriptions()

        assert count == 0
        subscription.refresh_from_db()
        assert subscription.status == SubscriptionStatus.ACTIVE


class TestCheckTrialExpiration:
    """Tests for check_trial_expiration task."""

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_expired_trial_with_successful_payment(self, mock_manager_class, mock_get_payment, user, plan):
        """Test trial expiration with successful first payment."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.TRIALING,
            start_date=now - timedelta(days=14),
            trial_end_date=now - timedelta(hours=1),  # Trial ended
            current_period_start=now - timedelta(days=14),
            current_period_end=now - timedelta(hours=1),
            next_billing_date=now - timedelta(hours=1),
        )

        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        result = check_trial_expiration()

        assert result['expired'] == 1

    @patch('django_iyzico.tasks._get_stored_payment_method')
    def test_expired_trial_no_payment_method(self, mock_get_payment, user, plan):
        """Test trial expiration with no payment method."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.TRIALING,
            start_date=now - timedelta(days=14),
            trial_end_date=now - timedelta(hours=1),
            current_period_start=now - timedelta(days=14),
            current_period_end=now - timedelta(hours=1),
            next_billing_date=now - timedelta(hours=1),
        )

        mock_get_payment.return_value = None

        result = check_trial_expiration()

        subscription.refresh_from_db()
        assert subscription.status == SubscriptionStatus.EXPIRED

    def test_trial_ending_soon_notification(self, user, plan):
        """Test notification for trials ending in 7 days."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.TRIALING,
            start_date=now - timedelta(days=7),
            trial_end_date=now + timedelta(days=7),  # Ends in 7 days
            current_period_start=now - timedelta(days=7),
            current_period_end=now + timedelta(days=7),
            next_billing_date=now + timedelta(days=7),
        )

        with patch('django_iyzico.tasks.send_payment_notification') as mock_notify:
            result = check_trial_expiration()

        assert result['notified'] == 1
        mock_notify.delay.assert_called_with(
            subscription_id=subscription.id,
            event_type='trial_ending_soon',
        )


class TestChargeSubscription:
    """Tests for charge_subscription task."""

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_charge_subscription_success(self, mock_manager_class, mock_get_payment, user, plan):
        """Test successful subscription charge."""
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

        mock_get_payment.return_value = {'cardNumber': '5528790000000008'}

        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        result = charge_subscription(subscription.id)

        assert result is True
        mock_manager.process_billing.assert_called_once()

    def test_charge_subscription_not_found(self):
        """Test charging non-existent subscription."""
        result = charge_subscription(99999)

        assert result is False

    @patch('django_iyzico.tasks._get_stored_payment_method')
    @patch('django_iyzico.tasks.SubscriptionManager')
    def test_charge_subscription_with_payment_method(self, mock_manager_class, mock_get_payment, user, plan):
        """Test charging subscription with provided payment method."""
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

        payment_method = {'cardNumber': '5528790000000008'}

        mock_payment = Mock()
        mock_payment.is_successful.return_value = True

        mock_manager = Mock()
        mock_manager.process_billing.return_value = mock_payment
        mock_manager_class.return_value = mock_manager

        result = charge_subscription(subscription.id, payment_method=payment_method)

        assert result is True
        # Should use provided payment method, not call _get_stored_payment_method
        mock_get_payment.assert_not_called()


class TestSendPaymentNotification:
    """Tests for send_payment_notification task."""

    def test_send_payment_success_notification(self, user, plan):
        """Test sending payment success notification."""
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

        result = send_payment_notification(
            subscription_id=subscription.id,
            event_type='payment_success',
        )

        assert result is True
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert 'Payment Successful' in mail.outbox[0].subject

    def test_send_payment_failed_notification(self, user, plan):
        """Test sending payment failed notification."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.PAST_DUE,
            start_date=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        result = send_payment_notification(
            subscription_id=subscription.id,
            event_type='payment_failed',
        )

        assert result is True
        assert len(mail.outbox) == 1
        assert 'Payment Failed' in mail.outbox[0].subject

    def test_send_trial_ending_notification(self, user, plan):
        """Test sending trial ending soon notification."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.TRIALING,
            start_date=now - timedelta(days=7),
            trial_end_date=now + timedelta(days=7),
            current_period_start=now - timedelta(days=7),
            current_period_end=now + timedelta(days=7),
            next_billing_date=now + timedelta(days=7),
        )

        result = send_payment_notification(
            subscription_id=subscription.id,
            event_type='trial_ending_soon',
        )

        assert result is True
        assert len(mail.outbox) == 1
        assert 'Trial Ending Soon' in mail.outbox[0].subject

    def test_send_notification_invalid_subscription(self):
        """Test sending notification for non-existent subscription."""
        result = send_payment_notification(
            subscription_id=99999,
            event_type='payment_success',
        )

        assert result is False
        assert len(mail.outbox) == 0

    def test_send_notification_invalid_event_type(self, user, plan):
        """Test sending notification with invalid event type."""
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

        result = send_payment_notification(
            subscription_id=subscription.id,
            event_type='invalid_event',
        )

        assert result is False
        assert len(mail.outbox) == 0

    def test_all_notification_templates(self, user, plan):
        """Test all notification email templates."""
        now = timezone.now()

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            trial_end_date=now + timedelta(days=7),
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            next_billing_date=now + timedelta(days=30),
        )

        event_types = [
            'payment_success',
            'payment_failed',
            'payment_retry_success',
            'subscription_expired',
            'trial_ending_soon',
        ]

        for event_type in event_types:
            mail.outbox = []  # Clear mailbox

            result = send_payment_notification(
                subscription_id=subscription.id,
                event_type=event_type,
            )

            assert result is True, f"Failed for event_type: {event_type}"
            assert len(mail.outbox) == 1, f"No email sent for event_type: {event_type}"
