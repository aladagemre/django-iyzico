"""
Subscription Payment Examples for django-iyzico.

Comprehensive examples showing how to use subscription features
including recurring billing, trials, upgrades, and cancellations.

Requirements:
    - Redis installed and running
    - Celery worker and beat started
    - User authentication configured
"""

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction

from django_iyzico.subscription_models import (
    BillingInterval,
    SubscriptionPlan,
    Subscription,
    SubscriptionStatus,
)
from django_iyzico.subscription_manager import SubscriptionManager
from django_iyzico.signals import (
    subscription_created,
    subscription_cancelled,
    subscription_payment_succeeded,
    subscription_payment_failed,
)

User = get_user_model()


# =============================================================================
# Example 1: Creating Subscription Plans
# =============================================================================

def create_subscription_plans():
    """
    Create different subscription tiers for a SaaS application.

    Returns a dictionary of created plans.
    """
    # Basic Plan - $9.99/month
    basic_plan = SubscriptionPlan.objects.create(
        name='Basic',
        slug='basic',
        description='Perfect for individuals and small projects',
        price=Decimal('9.99'),
        currency='USD',
        billing_interval=BillingInterval.MONTHLY,
        billing_interval_count=1,
        trial_period_days=7,  # 7-day trial
        features={
            'storage': '10GB',
            'projects': 5,
            'team_members': 1,
            'support': 'Email',
            'api_calls': 10000,
        },
        sort_order=1,
        is_active=True,
    )

    # Pro Plan - $29.99/month
    pro_plan = SubscriptionPlan.objects.create(
        name='Professional',
        slug='professional',
        description='For growing teams and businesses',
        price=Decimal('29.99'),
        currency='USD',
        billing_interval=BillingInterval.MONTHLY,
        billing_interval_count=1,
        trial_period_days=14,  # 14-day trial
        features={
            'storage': '100GB',
            'projects': 50,
            'team_members': 10,
            'support': 'Priority Email',
            'api_calls': 100000,
            'custom_domain': True,
        },
        sort_order=2,
        is_active=True,
    )

    # Enterprise Plan - $99.99/month
    enterprise_plan = SubscriptionPlan.objects.create(
        name='Enterprise',
        slug='enterprise',
        description='For large organizations with advanced needs',
        price=Decimal('99.99'),
        currency='USD',
        billing_interval=BillingInterval.MONTHLY,
        billing_interval_count=1,
        trial_period_days=30,  # 30-day trial
        features={
            'storage': 'Unlimited',
            'projects': 'Unlimited',
            'team_members': 'Unlimited',
            'support': '24/7 Phone & Email',
            'api_calls': 'Unlimited',
            'custom_domain': True,
            'dedicated_account_manager': True,
            'sla': '99.9%',
        },
        sort_order=3,
        is_active=True,
        max_subscribers=100,  # Limited enterprise slots
    )

    # Annual Plan (save 20%) - $95.88/year
    annual_plan = SubscriptionPlan.objects.create(
        name='Professional Annual',
        slug='professional-annual',
        description='Save 20% with annual billing',
        price=Decimal('287.88'),  # $29.99 * 12 * 0.8
        currency='USD',
        billing_interval=BillingInterval.YEARLY,
        billing_interval_count=1,
        trial_period_days=14,
        features={
            'storage': '100GB',
            'projects': 50,
            'team_members': 10,
            'support': 'Priority Email',
            'api_calls': 100000,
            'custom_domain': True,
            'billing_discount': '20%',
        },
        sort_order=4,
        is_active=True,
    )

    return {
        'basic': basic_plan,
        'pro': pro_plan,
        'enterprise': enterprise_plan,
        'annual': annual_plan,
    }


# =============================================================================
# Example 2: Creating a Subscription with Trial
# =============================================================================

def subscribe_user_with_trial(user, plan):
    """
    Subscribe a user to a plan with trial period.

    Args:
        user: Django user instance
        plan: SubscriptionPlan instance

    Returns:
        Subscription instance
    """
    manager = SubscriptionManager()

    # Payment method (test card)
    payment_method = {
        'cardHolderName': f"{user.first_name} {user.last_name}",
        'cardNumber': '5528790000000008',  # Test card
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
    }

    # Create subscription with trial
    subscription = manager.create_subscription(
        user=user,
        plan=plan,
        payment_method=payment_method,
        trial=True,  # Use trial period
        metadata={
            'source': 'website',
            'campaign': 'spring2025',
            'referral_code': 'FRIEND123',
        },
    )

    print(f"Subscription created: {subscription.id}")
    print(f"Status: {subscription.status}")  # TRIALING
    print(f"Trial ends: {subscription.trial_end_date}")
    print(f"First billing: {subscription.next_billing_date}")

    return subscription


# =============================================================================
# Example 3: Creating a Subscription without Trial (Immediate Billing)
# =============================================================================

def subscribe_user_immediate(user, plan):
    """
    Subscribe a user with immediate billing (no trial).

    Args:
        user: Django user instance
        plan: SubscriptionPlan instance

    Returns:
        Subscription instance
    """
    manager = SubscriptionManager()

    payment_method = {
        'cardHolderName': f"{user.first_name} {user.last_name}",
        'cardNumber': '5528790000000008',
        'expireMonth': '12',
        'expireYear': '2030',
        'cvc': '123',
    }

    # Create subscription without trial
    subscription = manager.create_subscription(
        user=user,
        plan=plan,
        payment_method=payment_method,
        trial=False,  # Skip trial, bill immediately
    )

    print(f"Subscription created: {subscription.id}")
    print(f"Status: {subscription.status}")  # ACTIVE or PAST_DUE
    print(f"Next billing: {subscription.next_billing_date}")

    # Check first payment
    first_payment = subscription.payments.first()
    if first_payment:
        print(f"First payment: {first_payment.status}")
        print(f"Amount: {first_payment.amount} {first_payment.currency}")

    return subscription


# =============================================================================
# Example 4: Upgrading a Subscription
# =============================================================================

def upgrade_subscription(subscription, new_plan):
    """
    Upgrade subscription to a higher tier with prorated charge.

    Args:
        subscription: Current Subscription instance
        new_plan: New (higher-tier) SubscriptionPlan

    Returns:
        Updated Subscription instance
    """
    manager = SubscriptionManager()

    # Upgrade with proration
    updated_subscription = manager.upgrade_subscription(
        subscription=subscription,
        new_plan=new_plan,
        prorate=True,  # Charge prorated amount immediately
    )

    print(f"Subscription upgraded from {subscription.plan.name} to {new_plan.name}")
    print(f"New price: {new_plan.price} {new_plan.currency}/{new_plan.get_billing_interval_display()}")

    return updated_subscription


# =============================================================================
# Example 5: Downgrading a Subscription
# =============================================================================

def downgrade_subscription(subscription, new_plan, at_period_end=True):
    """
    Downgrade subscription to a lower tier.

    Args:
        subscription: Current Subscription instance
        new_plan: New (lower-tier) SubscriptionPlan
        at_period_end: If True, apply at period end; if False, apply immediately

    Returns:
        Updated Subscription instance
    """
    manager = SubscriptionManager()

    updated_subscription = manager.downgrade_subscription(
        subscription=subscription,
        new_plan=new_plan,
        at_period_end=at_period_end,
    )

    if at_period_end:
        print(f"Downgrade scheduled for end of billing period")
        print(f"Will switch to {new_plan.name} on {subscription.current_period_end}")
    else:
        print(f"Downgraded immediately to {new_plan.name}")

    return updated_subscription


# =============================================================================
# Example 6: Cancelling a Subscription
# =============================================================================

def cancel_subscription(subscription, immediate=False, reason=None):
    """
    Cancel a subscription.

    Args:
        subscription: Subscription instance
        immediate: If True, cancel now; if False, cancel at period end
        reason: Optional cancellation reason

    Returns:
        Updated Subscription instance
    """
    manager = SubscriptionManager()

    updated_subscription = manager.cancel_subscription(
        subscription=subscription,
        at_period_end=not immediate,
        reason=reason or "User requested cancellation",
    )

    if immediate:
        print(f"Subscription cancelled immediately")
        print(f"Access ended: {subscription.ended_at}")
    else:
        print(f"Subscription will cancel at period end")
        print(f"Access until: {subscription.current_period_end}")
        print(f"No further charges will be made")

    return updated_subscription


# =============================================================================
# Example 7: Pausing and Resuming a Subscription
# =============================================================================

def pause_subscription(subscription):
    """
    Pause a subscription temporarily (stop billing).

    Args:
        subscription: Subscription instance

    Returns:
        Updated Subscription instance
    """
    manager = SubscriptionManager()

    updated_subscription = manager.pause_subscription(subscription)

    print(f"Subscription paused")
    print(f"Billing stopped - will not be charged on next billing date")
    print(f"Status: {updated_subscription.status}")  # PAUSED

    return updated_subscription


def resume_subscription(subscription):
    """
    Resume a paused subscription.

    Args:
        subscription: Paused Subscription instance

    Returns:
        Updated Subscription instance
    """
    manager = SubscriptionManager()

    updated_subscription = manager.resume_subscription(subscription)

    print(f"Subscription resumed")
    print(f"Billing will continue on schedule")
    print(f"Status: {updated_subscription.status}")  # ACTIVE

    return updated_subscription


# =============================================================================
# Example 8: Handling Subscription Signals
# =============================================================================

def setup_subscription_signals():
    """
    Set up signal handlers for subscription lifecycle events.

    This allows you to integrate subscription events with your
    application logic (send emails, update user permissions, etc.).
    """
    from django.dispatch import receiver

    @receiver(subscription_created)
    def on_subscription_created(sender, subscription, user, **kwargs):
        """Handle new subscription creation."""
        print(f"New subscription created for {user.email}")
        print(f"Plan: {subscription.plan.name}")

        # Send welcome email
        # Update user permissions
        # Track analytics event
        # etc.

    @receiver(subscription_payment_succeeded)
    def on_payment_success(sender, subscription, **kwargs):
        """Handle successful payment."""
        print(f"Payment successful for subscription {subscription.id}")

        # Extend user access
        # Send receipt email
        # Update billing metrics

    @receiver(subscription_payment_failed)
    def on_payment_failed(sender, subscription, error_message, **kwargs):
        """Handle failed payment."""
        print(f"Payment failed for subscription {subscription.id}")
        print(f"Error: {error_message}")

        # Send payment failure email
        # Notify user to update payment method
        # Start dunning process

    @receiver(subscription_cancelled)
    def on_subscription_cancelled(sender, subscription, immediate, **kwargs):
        """Handle subscription cancellation."""
        print(f"Subscription cancelled: {subscription.id}")

        if immediate:
            # Revoke access immediately
            # Send cancellation confirmation
            pass
        else:
            # Schedule access revocation
            # Send cancellation confirmation with end date
            pass


# =============================================================================
# Example 9: Checking Subscription Status
# =============================================================================

def check_subscription_status(user):
    """
    Check user's subscription status and permissions.

    Args:
        user: Django user instance

    Returns:
        dict with subscription information
    """
    # Get user's active subscription
    subscription = user.iyzico_subscriptions.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    ).first()

    if not subscription:
        return {
            'has_subscription': False,
            'plan': None,
            'features': {},
        }

    return {
        'has_subscription': True,
        'plan': subscription.plan.name,
        'status': subscription.get_status_display(),
        'is_trialing': subscription.is_trialing(),
        'trial_ends': subscription.trial_end_date,
        'next_billing_date': subscription.next_billing_date,
        'days_until_renewal': subscription.days_until_renewal(),
        'features': subscription.plan.features,
        'total_paid': subscription.get_total_amount_paid(),
        'payment_count': subscription.get_successful_payment_count(),
    }


# =============================================================================
# Example 10: Admin - Manually Process Billing
# =============================================================================

def manually_process_subscription_billing(subscription_id):
    """
    Manually trigger billing for a specific subscription (admin use).

    Args:
        subscription_id: ID of subscription to bill

    Returns:
        bool indicating success
    """
    from django_iyzico.tasks import charge_subscription

    # Queue the charge task
    result = charge_subscription.delay(subscription_id)

    print(f"Billing task queued for subscription {subscription_id}")
    print(f"Task ID: {result.id}")

    return True


# =============================================================================
# Example 11: Admin - Generate Subscription Report
# =============================================================================

def generate_subscription_report(start_date, end_date):
    """
    Generate subscription metrics report for a date range.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        dict with subscription metrics
    """
    from django.db.models import Count, Sum, Avg

    # Active subscriptions
    active_subs = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    ).count()

    # New subscriptions in period
    new_subs = Subscription.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
    ).count()

    # Cancelled subscriptions in period
    cancelled_subs = Subscription.objects.filter(
        cancelled_at__gte=start_date,
        cancelled_at__lte=end_date,
    ).count()

    # Revenue metrics
    from django_iyzico.subscription_models import SubscriptionPayment

    revenue = SubscriptionPayment.objects.filter(
        status='success',
        created_at__gte=start_date,
        created_at__lte=end_date,
    ).aggregate(
        total_revenue=Sum('amount'),
        payment_count=Count('id'),
        avg_payment=Avg('amount'),
    )

    # Calculate MRR (Monthly Recurring Revenue)
    monthly_subs = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
        plan__billing_interval=BillingInterval.MONTHLY,
    ).select_related('plan')

    mrr = sum(sub.plan.price for sub in monthly_subs)

    # Calculate churn rate
    start_active = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
        created_at__lt=start_date,
    ).count()

    churn_rate = (cancelled_subs / start_active * 100) if start_active > 0 else 0

    return {
        'period': {
            'start': start_date,
            'end': end_date,
        },
        'subscriptions': {
            'active': active_subs,
            'new': new_subs,
            'cancelled': cancelled_subs,
            'churn_rate': f"{churn_rate:.2f}%",
        },
        'revenue': {
            'total': revenue['total_revenue'] or Decimal('0.00'),
            'payment_count': revenue['payment_count'],
            'average_payment': revenue['avg_payment'] or Decimal('0.00'),
        },
        'metrics': {
            'mrr': mrr,
            'arr': mrr * 12,  # Annual Recurring Revenue
        },
    }


# =============================================================================
# Example 12: Full SaaS Subscription Flow
# =============================================================================

@transaction.atomic
def complete_saas_subscription_flow():
    """
    Complete example of SaaS subscription flow from signup to upgrade.

    This demonstrates a real-world subscription lifecycle.
    """
    # 1. Create subscription plans
    plans = create_subscription_plans()

    # 2. User signs up
    user = User.objects.create_user(
        username='newuser',
        email='newuser@example.com',
        password='password123',
        first_name='New',
        last_name='User',
    )

    print("\n=== Step 1: User Signup ===")
    print(f"User created: {user.email}")

    # 3. Subscribe to Basic plan with trial
    print("\n=== Step 2: Subscribe to Basic Plan ===")
    subscription = subscribe_user_with_trial(user, plans['basic'])

    # 4. User uses service during trial
    print("\n=== Step 3: During Trial Period ===")
    status = check_subscription_status(user)
    print(f"Trial status: {status}")

    # 5. Trial ends, first payment processed automatically by Celery
    # (This happens in background via process_due_subscriptions task)

    # 6. After 2 months, user upgrades to Pro
    print("\n=== Step 4: Upgrade to Professional ===")
    subscription.refresh_from_db()
    upgrade_subscription(subscription, plans['pro'])

    # 7. After 6 months, user downgrades to Basic
    print("\n=== Step 5: Downgrade to Basic ===")
    subscription.refresh_from_db()
    downgrade_subscription(subscription, plans['basic'], at_period_end=True)

    # 8. User cancels subscription
    print("\n=== Step 6: Cancel Subscription ===")
    subscription.refresh_from_db()
    cancel_subscription(
        subscription,
        immediate=False,
        reason="Found alternative solution",
    )

    print("\n=== Subscription Lifecycle Complete ===")

    return subscription


if __name__ == '__main__':
    # Run the complete flow
    complete_saas_subscription_flow()
