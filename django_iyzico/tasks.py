"""
Celery tasks for django-iyzico subscription management.

Handles automated billing, payment retries, and subscription lifecycle management.
"""

import logging
from datetime import timedelta
from typing import Dict, Optional

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="django_iyzico.process_due_subscriptions")
def process_due_subscriptions() -> Dict[str, int]:
    """
    Process subscriptions due for billing.

    Runs daily via Celery Beat to charge subscriptions whose
    next_billing_date has arrived.

    Returns:
        Dictionary with counts of processed, successful, and failed subscriptions.

    Example:
        >>> result = process_due_subscriptions()
        >>> print(result)
        {'processed': 50, 'successful': 48, 'failed': 2}
    """
    from .subscription_manager import SubscriptionManager
    from .subscription_models import Subscription, SubscriptionStatus

    manager = SubscriptionManager()
    now = timezone.now()

    # Get subscriptions due for billing
    due_subscriptions = Subscription.objects.filter(
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING],
        next_billing_date__lte=now,
    ).select_related("plan", "user")

    processed = 0
    successful = 0
    failed = 0

    logger.info(f"Processing {due_subscriptions.count()} subscriptions due for billing")

    for subscription in due_subscriptions:
        try:
            # TODO: Retrieve stored payment method
            # For now, this is a placeholder - payment method storage
            # needs to be implemented
            payment_method = _get_stored_payment_method(subscription)

            if not payment_method:
                logger.warning(
                    f"No payment method found for subscription {subscription.id}, skipping"
                )
                failed += 1
                continue

            # Process billing
            payment = manager.process_billing(
                subscription=subscription,
                payment_method=payment_method,
            )

            processed += 1

            if payment.is_successful():
                successful += 1
                logger.info(f"Successfully billed subscription {subscription.id}")

                # Send success notification
                send_payment_notification.delay(
                    subscription_id=subscription.id,
                    event_type="payment_success",
                )
            else:
                failed += 1
                logger.warning(f"Failed to bill subscription {subscription.id}")

                # Send failure notification
                send_payment_notification.delay(
                    subscription_id=subscription.id,
                    event_type="payment_failed",
                )

        except Exception as e:
            failed += 1
            logger.exception(f"Error processing subscription {subscription.id}: {e}")

    result = {
        "processed": processed,
        "successful": successful,
        "failed": failed,
    }

    logger.info(f"Billing complete: {result}")
    return result


@shared_task(name="django_iyzico.retry_failed_payments")
def retry_failed_payments() -> Dict[str, int]:
    """
    Retry failed subscription payments.

    Runs every 6 hours via Celery Beat to retry subscriptions
    in PAST_DUE status with failed payment count < max retries.

    Returns:
        Dictionary with counts of retried, successful, and failed attempts.
    """
    from .subscription_manager import SubscriptionManager
    from .subscription_models import Subscription, SubscriptionStatus

    manager = SubscriptionManager()
    max_retries = getattr(settings, "IYZICO_SUBSCRIPTION_RETRY_ATTEMPTS", 3)
    retry_delay_hours = getattr(settings, "IYZICO_SUBSCRIPTION_RETRY_DELAY", 86400) / 3600

    # Get subscriptions that need retry
    retry_cutoff = timezone.now() - timedelta(hours=retry_delay_hours)

    subscriptions_to_retry = Subscription.objects.filter(
        status=SubscriptionStatus.PAST_DUE,
        failed_payment_count__lt=max_retries,
        last_payment_attempt__lte=retry_cutoff,
    ).select_related("plan", "user")

    retried = 0
    successful = 0
    failed = 0

    logger.info(f"Retrying {subscriptions_to_retry.count()} failed subscription payments")

    for subscription in subscriptions_to_retry:
        try:
            # TODO: Retrieve stored payment method
            payment_method = _get_stored_payment_method(subscription)

            if not payment_method:
                logger.warning(
                    f"No payment method for subscription {subscription.id}, "
                    f"marking for expiration"
                )
                failed += 1

                # If max retries reached, expire subscription
                if subscription.failed_payment_count >= max_retries - 1:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.ended_at = timezone.now()
                    subscription.save()
                continue

            # Retry payment
            payment = manager.process_billing(
                subscription=subscription,
                payment_method=payment_method,
            )

            retried += 1

            if payment.is_successful():
                successful += 1
                logger.info(f"Retry successful for subscription {subscription.id}")

                # Send success notification
                send_payment_notification.delay(
                    subscription_id=subscription.id,
                    event_type="payment_retry_success",
                )
            else:
                failed += 1
                logger.warning(
                    f"Retry failed for subscription {subscription.id} "
                    f"(attempt {subscription.failed_payment_count})"
                )

                # If max retries reached, expire subscription
                if subscription.failed_payment_count >= max_retries:
                    subscription.status = SubscriptionStatus.EXPIRED
                    subscription.ended_at = timezone.now()
                    subscription.save()

                    logger.info(
                        f"Subscription {subscription.id} expired after {max_retries} "
                        f"failed attempts"
                    )

                    # Send expiration notification
                    send_payment_notification.delay(
                        subscription_id=subscription.id,
                        event_type="subscription_expired",
                    )

        except Exception as e:
            failed += 1
            logger.exception(f"Error retrying subscription {subscription.id}: {e}")

    result = {
        "retried": retried,
        "successful": successful,
        "failed": failed,
    }

    logger.info(f"Retry complete: {result}")
    return result


@shared_task(name="django_iyzico.expire_cancelled_subscriptions")
def expire_cancelled_subscriptions() -> int:
    """
    Expire subscriptions marked for cancellation at period end.

    Runs daily via Celery Beat to find subscriptions with
    cancel_at_period_end=True whose current_period_end has passed.

    Returns:
        Number of subscriptions expired.
    """
    from .subscription_models import Subscription, SubscriptionStatus

    now = timezone.now()

    # Find subscriptions to expire
    subscriptions_to_expire = Subscription.objects.filter(
        cancel_at_period_end=True,
        current_period_end__lte=now,
        status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED],
    )

    expired_count = 0

    for subscription in subscriptions_to_expire:
        subscription.status = SubscriptionStatus.EXPIRED
        subscription.ended_at = now
        subscription.save()

        expired_count += 1

        logger.info(f"Expired subscription {subscription.id} at period end")

        # Send signal
        from .signals import subscription_expired

        subscription_expired.send(
            sender=Subscription,
            subscription=subscription,
        )

        # Send notification
        send_payment_notification.delay(
            subscription_id=subscription.id,
            event_type="subscription_expired",
        )

    logger.info(f"Expired {expired_count} cancelled subscriptions")
    return expired_count


@shared_task(name="django_iyzico.check_trial_expiration")
def check_trial_expiration() -> Dict[str, int]:
    """
    Check for expiring trials and send notifications.

    Runs daily to:
    1. Convert expired trials to active (with billing)
    2. Send notifications for trials expiring soon (7 days)

    Returns:
        Dictionary with counts of expired and notified subscriptions.
    """
    from .subscription_manager import SubscriptionManager
    from .subscription_models import Subscription, SubscriptionStatus

    manager = SubscriptionManager()
    now = timezone.now()

    # Find expired trials
    expired_trials = Subscription.objects.filter(
        status=SubscriptionStatus.TRIALING,
        trial_end_date__lte=now,
    ).select_related("plan", "user")

    expired_count = 0

    for subscription in expired_trials:
        try:
            # TODO: Process first payment
            payment_method = _get_stored_payment_method(subscription)

            if payment_method:
                payment = manager.process_billing(
                    subscription=subscription,
                    payment_method=payment_method,
                )

                if payment.is_successful():
                    logger.info(
                        f"Trial ended for subscription {subscription.id}, "
                        f"first payment successful"
                    )
                    expired_count += 1
                else:
                    logger.warning(
                        f"Trial ended for subscription {subscription.id}, " f"first payment failed"
                    )
            else:
                # No payment method - mark as expired
                subscription.status = SubscriptionStatus.EXPIRED
                subscription.ended_at = now
                subscription.save()

                logger.warning(
                    f"Trial ended for subscription {subscription.id}, " f"no payment method found"
                )

        except Exception as e:
            logger.exception(
                f"Error processing trial expiration for subscription " f"{subscription.id}: {e}"
            )

    # Find trials expiring soon (7 days)
    notification_date = now + timedelta(days=7)
    expiring_soon = Subscription.objects.filter(
        status=SubscriptionStatus.TRIALING,
        trial_end_date__date=notification_date.date(),
    )

    notified_count = 0

    for subscription in expiring_soon:
        send_payment_notification.delay(
            subscription_id=subscription.id,
            event_type="trial_ending_soon",
        )
        notified_count += 1

    result = {
        "expired": expired_count,
        "notified": notified_count,
    }

    logger.info(f"Trial expiration check complete: {result}")
    return result


@shared_task(name="django_iyzico.charge_subscription", bind=True, max_retries=3)
def charge_subscription(
    self,
    subscription_id: int,
    payment_method: Optional[Dict] = None,
) -> bool:
    """
    Process payment for a specific subscription.

    Args:
        subscription_id: ID of subscription to charge.
        payment_method: Optional payment method details.

    Returns:
        True if payment successful, False otherwise.

    Raises:
        Retries task up to 3 times on failure.
    """
    from .subscription_manager import SubscriptionManager
    from .subscription_models import Subscription

    try:
        subscription = Subscription.objects.select_related("plan", "user").get(id=subscription_id)
    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return False

    try:
        manager = SubscriptionManager()

        # Get payment method
        if not payment_method:
            payment_method = _get_stored_payment_method(subscription)

        if not payment_method:
            logger.error(f"No payment method available for subscription {subscription_id}")
            return False

        # Process payment
        payment = manager.process_billing(
            subscription=subscription,
            payment_method=payment_method,
        )

        return payment.is_successful()

    except Exception as e:
        logger.exception(f"Error charging subscription {subscription_id}: {e}")

        # Retry task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(name="django_iyzico.send_payment_notification")
def send_payment_notification(
    subscription_id: int,
    event_type: str,
) -> bool:
    """
    Send email notification for subscription events.

    Args:
        subscription_id: ID of subscription.
        event_type: Type of event (payment_success, payment_failed, etc.).

    Returns:
        True if notification sent successfully.

    Example:
        >>> send_payment_notification.delay(
        ...     subscription_id=123,
        ...     event_type='payment_success',
        ... )
    """
    from django.core.mail import send_mail

    from .subscription_models import Subscription

    try:
        subscription = Subscription.objects.select_related("plan", "user").get(id=subscription_id)
    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found for notification")
        return False

    user = subscription.user
    plan = subscription.plan

    # Email templates
    templates = {
        "payment_success": {
            "subject": f"Payment Successful - {plan.name}",
            "message": (
                f"Hi {user.first_name},\n\n"
                f"Your subscription payment of {plan.price} {plan.currency} "
                f"has been processed successfully.\n\n"
                f'Next billing date: {subscription.next_billing_date.strftime("%Y-%m-%d")}\n\n'
                f"Thank you for your continued support!"
            ),
        },
        "payment_failed": {
            "subject": f"Payment Failed - {plan.name}",
            "message": (
                f"Hi {user.first_name},\n\n"
                f"We were unable to process your subscription payment of "
                f"{plan.price} {plan.currency}.\n\n"
                f"Please update your payment method to continue your subscription.\n\n"
                f"If you have any questions, please contact support."
            ),
        },
        "payment_retry_success": {
            "subject": f"Payment Retry Successful - {plan.name}",
            "message": (
                f"Hi {user.first_name},\n\n"
                f"Your subscription payment has been processed successfully "
                f"after a previous failure.\n\n"
                f"Your subscription is now active.\n\n"
                f"Thank you!"
            ),
        },
        "subscription_expired": {
            "subject": f"Subscription Expired - {plan.name}",
            "message": (
                f"Hi {user.first_name},\n\n"
                f"Your subscription to {plan.name} has expired.\n\n"
                f"To reactivate, please visit our website and subscribe again.\n\n"
                f"We hope to see you again soon!"
            ),
        },
        "trial_ending_soon": {
            "subject": f"Trial Ending Soon - {plan.name}",
            "message": (
                f"Hi {user.first_name},\n\n"
                f"Your trial period for {plan.name} will end in 7 days.\n\n"
                f"Your first payment of {plan.price} {plan.currency} will be "
                f'charged on {subscription.trial_end_date.strftime("%Y-%m-%d")}.\n\n'
                f"If you wish to cancel, please do so before the trial ends."
            ),
        },
    }

    template = templates.get(event_type)

    if not template:
        logger.error(f"Unknown event type: {event_type}")
        return False

    try:
        # Send email
        send_mail(
            subject=template["subject"],
            message=template["message"],
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(
            f"Sent {event_type} notification to {user.email} for " f"subscription {subscription_id}"
        )

        return True

    except Exception as e:
        logger.exception(
            f"Error sending {event_type} notification for " f"subscription {subscription_id}: {e}"
        )
        return False


@shared_task(name="django_iyzico.check_expiring_payment_methods")
def check_expiring_payment_methods() -> Dict[str, int]:
    """
    Check for expiring payment methods and send notifications to users.

    Runs daily via Celery Beat to:
    1. Find payment methods expiring within 30 days
    2. Send email notifications to users
    3. Deactivate already expired payment methods

    Returns:
        Dictionary with counts of expired, expiring, and notified users.

    Example:
        >>> result = check_expiring_payment_methods()
        >>> print(result)
        {'expired': 5, 'expiring': 12, 'notified': 12}

    Security Note:
        Only sends notifications, never exposes actual card numbers.
        Users are directed to update their payment method in the application.
    """
    from django.core.mail import send_mail

    from .subscription_models import PaymentMethod

    now = timezone.now()
    expired_count = 0
    expiring_count = 0
    notified_count = 0

    # Find and deactivate expired payment methods
    expired_methods = PaymentMethod.objects.filter(
        is_active=True,
    ).select_related("user")

    for payment_method in expired_methods:
        if payment_method.is_expired():
            # Deactivate expired card
            payment_method.deactivate()
            expired_count += 1

            logger.info(
                f"Deactivated expired payment method {payment_method.id} "
                f"for user {payment_method.user_id}"
            )

            # Check if user has active subscriptions
            active_subscriptions = payment_method.user.iyzico_subscriptions.filter(
                status__in=["active", "trialing", "past_due"]
            ).count()

            if active_subscriptions > 0:
                # Send notification about expired card
                try:
                    user_name = payment_method.user.first_name or payment_method.user.username
                    expiry = f"{payment_method.expiry_month}/" f"{payment_method.expiry_year}"
                    send_mail(
                        subject="Payment Method Expired - Action Required",
                        message=(
                            f"Hi {user_name},\n\n"
                            f"Your payment method ending in "
                            f"{payment_method.card_last_four} "
                            f"has expired ({expiry}).\n\n"
                            f"You have {active_subscriptions} "
                            f"active subscription(s) that require "
                            f"a valid payment method.\n\n"
                            f"Please log in to your account and "
                            f"update your payment method "
                            f"to avoid service interruption.\n\n"
                            f"Thank you!"
                        ),
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                        recipient_list=[payment_method.user.email],
                        fail_silently=False,
                    )

                    notified_count += 1

                    logger.info(
                        f"Sent expired card notification to {payment_method.user.email} "
                        f"for payment method {payment_method.id}"
                    )

                except Exception as e:
                    logger.exception(
                        f"Error sending expired card notification for "
                        f"payment method {payment_method.id}: {e}"
                    )

    # Find payment methods expiring within 30 days
    expiring_methods = PaymentMethod.objects.filter(
        is_active=True,
        is_default=True,  # Only notify for default payment methods
    ).select_related("user")

    for payment_method in expiring_methods:
        # Check if expires soon but not yet expired
        if payment_method.expires_soon(within_days=30) and not payment_method.is_expired():
            expiring_count += 1

            # Check if user has active subscriptions
            active_subscriptions = payment_method.user.iyzico_subscriptions.filter(
                status__in=["active", "trialing"]
            ).count()

            if active_subscriptions > 0:
                # Calculate days until expiry
                try:
                    import calendar
                    from datetime import datetime

                    expiry_year = int(payment_method.expiry_year)
                    expiry_month = int(payment_method.expiry_month)
                    last_day = calendar.monthrange(expiry_year, expiry_month)[1]

                    expiry_date = datetime(expiry_year, expiry_month, last_day)
                    days_until_expiry = (expiry_date.date() - now.date()).days

                    # Only send notification if expiring within 30 days
                    if 0 < days_until_expiry <= 30:
                        user_name = payment_method.user.first_name or payment_method.user.username
                        card_info = (
                            f"{payment_method.get_card_brand_display()} "
                            f"ending in {payment_method.card_last_four}"
                        )
                        expiry = f"{payment_method.expiry_month}/" f"{payment_method.expiry_year}"
                        send_mail(
                            subject="Payment Method Expiring Soon",
                            message=(
                                f"Hi {user_name},\n\n"
                                f"Your payment method ({card_info}) "
                                f"will expire in {days_until_expiry} "
                                f"day(s) ({expiry}).\n\n"
                                f"You have {active_subscriptions} "
                                f"active subscription(s) "
                                f"that use this payment method.\n\n"
                                f"To avoid any interruption to your service, "
                                f"please log in to your account and "
                                f"update your payment method before it expires.\n\n"
                                f"Thank you!"
                            ),
                            from_email=getattr(
                                settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"
                            ),
                            recipient_list=[payment_method.user.email],
                            fail_silently=False,
                        )

                        notified_count += 1

                        logger.info(
                            f"Sent expiring card notification to {payment_method.user.email} "
                            f"for payment method {payment_method.id} "
                            f"(expires in {days_until_expiry} days)"
                        )

                except Exception as e:
                    logger.exception(
                        f"Error sending expiring card notification for "
                        f"payment method {payment_method.id}: {e}"
                    )

    result = {
        "expired": expired_count,
        "expiring": expiring_count,
        "notified": notified_count,
    }

    logger.info(f"Payment method expiry check complete: {result}")
    return result


def _get_stored_payment_method(subscription) -> Optional[Dict]:
    """
    Retrieve stored payment method for a subscription.

    Fetches the user's default active payment method from the PaymentMethod model.
    Only returns tokenized card data (never full card numbers) in PCI DSS compliant format.

    Args:
        subscription: Subscription instance with user relation.

    Returns:
        Payment method dictionary with card token for Iyzico API, or None.

    Security Note:
        This function returns only tokenized references, never actual card data.
        The card_token is a secure reference provided by Iyzico for recurring payments.
    """
    from .subscription_models import PaymentMethod

    try:
        user = subscription.user

        # First, try to get payment method from subscription metadata (if stored)
        # This allows subscription-specific payment methods
        stored_method_id = subscription.metadata.get("payment_method_id")
        if stored_method_id:
            try:
                payment_method = PaymentMethod.objects.get(
                    pk=stored_method_id,
                    user=user,
                    is_active=True,
                )
            except PaymentMethod.DoesNotExist:
                logger.warning(
                    f"Stored payment method {stored_method_id} not found for "
                    f"subscription {subscription.id}, falling back to default"
                )
                payment_method = None
        else:
            payment_method = None

        # Fall back to user's default payment method
        if not payment_method:
            payment_method = PaymentMethod.get_default_for_user(user)

        if not payment_method:
            logger.warning(
                f"No active payment method found for user {user.id} "
                f"(subscription {subscription.id})"
            )
            return None

        # Check if card is expired
        if payment_method.is_expired():
            logger.warning(
                f"Payment method {payment_method.id} for user {user.id} is expired "
                f"({payment_method.expiry_month}/{payment_method.expiry_year})"
            )
            return None

        # Return tokenized payment data for Iyzico API
        payment_data = payment_method.to_payment_dict()

        logger.debug(
            f"Retrieved payment method {payment_method.id} "
            f"({payment_method.get_display_name()}) for subscription {subscription.id}"
        )

        # Mark the payment method as used
        payment_method.mark_as_used()

        return payment_data

    except Exception as e:
        logger.exception(f"Error retrieving payment method for subscription {subscription.id}: {e}")
        return None
