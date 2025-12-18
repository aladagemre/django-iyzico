"""
Signal handlers for shop app.

Demonstrates how to handle payment and webhook events.
"""

from django.dispatch import receiver
from django_iyzico.signals import (
    payment_completed,
    payment_failed,
    threeds_completed,
    threeds_failed,
    webhook_received
)
from django_iyzico.subscription_signals import (
    subscription_activated,
    subscription_payment_failed
)
from .models import Order
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Payment Signals (Direct Payments)
# ============================================================================

@receiver(payment_completed)
def on_payment_completed(sender, instance, **kwargs):
    """Handle successful payment."""

    logger.info(f"Payment completed: {instance.payment_id}")

    # Send confirmation email
    # send_email(instance.buyer_email, "Payment Confirmed", ...)

    # Log for analytics
    # track_event('payment_success', amount=instance.amount, ...)

    # Update inventory, fulfill order, etc.
    # ...


@receiver(payment_failed)
def on_payment_failed(sender, instance, **kwargs):
    """Handle failed payment."""

    logger.warning(f"Payment failed: {instance.payment_id} - {instance.error_message}")

    # Send failure notification
    # send_email(instance.buyer_email, "Payment Failed", ...)

    # Log for analysis
    # track_event('payment_failed', reason=instance.error_message, ...)


@receiver(subscription_activated)
def on_subscription_activated(sender, subscription, **kwargs):
    """Handle subscription activation."""

    logger.info(f"Subscription activated: {subscription.id} for user {subscription.user.id}")

    # Grant premium access
    # subscription.user.grant_premium_access()

    # Send welcome email
    # send_email(subscription.user.email, "Welcome to Premium!", ...)


@receiver(subscription_payment_failed)
def on_subscription_payment_failed(sender, subscription, payment, **kwargs):
    """Handle failed subscription payment."""

    logger.warning(f"Subscription payment failed: {subscription.id}")

    # Notify user to update payment method
    # send_email(subscription.user.email, "Payment Failed - Update Card", ...)

    # Track for retry
    # ...


# ============================================================================
# 3D Secure Signals
# ============================================================================

@receiver(threeds_completed)
def on_threeds_completed(sender, payment_id, conversation_id, response, request, **kwargs):
    """
    Handle successful 3D Secure payment completion.

    This is triggered when user completes 3DS authentication and payment succeeds.
    Called AFTER Iyzico redirects back to callback URL.

    Args:
        payment_id: Iyzico payment ID
        conversation_id: Your conversation ID
        response: Full payment response dict
        request: HTTP request from callback
    """

    logger.info(f"3DS payment completed: payment_id={payment_id}, conversation_id={conversation_id}")

    # Find order by conversation_id and update it
    try:
        order = Order.objects.get(conversation_id=conversation_id)
        order.payment_id = payment_id
        order.payment_status = 'SUCCESS'
        order.order_status = 'PAID'

        # Extract payment details from response
        if 'price' in response:
            order.paid_amount = response['price']
        if 'cardAssociation' in response:
            order.card_association = response['cardAssociation']
        if 'cardFamily' in response:
            order.card_family = response['cardFamily']
        # ... extract other fields as needed

        order.save()

        logger.info(f"Order {order.id} updated after 3DS completion")

        # Reduce stock
        for item in order.items.all():
            item.product.stock -= item.quantity
            item.product.save()

        # Send confirmation email
        # send_email(order.buyer_email, "Payment Confirmed", ...)

    except Order.DoesNotExist:
        logger.error(f"Order not found for conversation_id: {conversation_id}")


@receiver(threeds_failed)
def on_threeds_failed(sender, conversation_id, error_code, error_message, request, **kwargs):
    """
    Handle failed 3D Secure payment.

    This is triggered when 3DS authentication or payment fails.

    Args:
        conversation_id: Your conversation ID (may be None)
        error_code: Error code from Iyzico
        error_message: Error message
        request: HTTP request from callback
    """

    logger.warning(f"3DS payment failed: conversation_id={conversation_id}, error={error_message}")

    # Find order and update status
    if conversation_id:
        try:
            order = Order.objects.get(conversation_id=conversation_id)
            order.payment_status = 'FAILED'
            order.error_message = error_message
            order.error_code = error_code
            order.save()

            logger.info(f"Order {order.id} marked as failed")

            # Send failure notification
            # send_email(order.buyer_email, "Payment Failed", ...)

        except Order.DoesNotExist:
            logger.error(f"Order not found for conversation_id: {conversation_id}")


# ============================================================================
# Webhook Signal
# ============================================================================

@receiver(webhook_received)
def on_webhook_received(sender, event_type, payment_id, conversation_id, data, request, **kwargs):
    """
    Handle webhook notifications from Iyzico.

    This is triggered when Iyzico sends webhook notifications.
    Webhooks are sent asynchronously and may arrive AFTER the user has already
    been redirected (for 3DS flow).

    Use this for:
    - Final status confirmation
    - Delayed notifications (chargebacks, refunds, etc.)
    - Reconciliation

    Args:
        event_type: Type of event (e.g., 'PAYMENT_AUTH', 'REFUND', etc.)
        payment_id: Iyzico payment ID
        conversation_id: Your conversation ID
        data: Full webhook data dict
        request: HTTP request from webhook
    """

    logger.info(f"Webhook received: event_type={event_type}, payment_id={payment_id}")

    # Example: Update order based on webhook
    if conversation_id:
        try:
            order = Order.objects.get(conversation_id=conversation_id)

            # Different event types may require different handling
            if event_type == 'PAYMENT_AUTH':
                # Payment authorized
                order.payment_status = 'SUCCESS'
                order.order_status = 'PAID'
                logger.info(f"Order {order.id} confirmed via webhook")

            elif event_type == 'REFUND_SUCCESS':
                # Refund processed
                order.payment_status = 'REFUNDED'
                order.order_status = 'REFUNDED'
                logger.info(f"Order {order.id} refund confirmed via webhook")

            elif event_type == 'CHARGEBACK':
                # Chargeback received
                order.payment_status = 'CHARGEBACK'
                order.notes += f"\nChargeback received: {data.get('reason', 'No reason')}"
                logger.warning(f"Order {order.id} chargeback via webhook")

            # Add other event type handling as needed

            order.save()

        except Order.DoesNotExist:
            logger.error(f"Order not found for webhook: conversation_id={conversation_id}")

    # Always return success (webhook handler does this automatically)
    # This is handled by the built-in webhook view
