"""
Subscription management business logic for django-iyzico.

Handles subscription lifecycle, billing, upgrades/downgrades,
and payment processing.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .client import IyzicoClient
from .exceptions import IyzicoAPIException, IyzicoValidationException
from .subscription_models import (
    Subscription,
    SubscriptionPayment,
    SubscriptionPlan,
    SubscriptionStatus,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Business logic for subscription management.

    Handles the complete subscription lifecycle including creation,
    billing, cancellations, upgrades, downgrades, and payment processing.

    Example:
        >>> manager = SubscriptionManager()
        >>> subscription = manager.create_subscription(
        ...     user=user,
        ...     plan=plan,
        ...     payment_method={'card_number': '...', ...},
        ... )
    """

    def __init__(self, client: Optional[IyzicoClient] = None):
        """
        Initialize subscription manager.

        Args:
            client: Optional IyzicoClient instance. If not provided,
                   a new one will be created using settings.
        """
        self.client = client or IyzicoClient()

    @transaction.atomic
    def create_subscription(
        self,
        user: User,
        plan: SubscriptionPlan,
        payment_method: Dict[str, Any],
        start_date: Optional[timezone.datetime] = None,
        trial: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Subscription:
        """
        Create new subscription and process initial payment.

        Args:
            user: User to subscribe.
            plan: Subscription plan to subscribe to.
            payment_method: Payment method details (card info, etc.).
            start_date: Optional start date (default: now).
            trial: Whether to use trial period if available.
            metadata: Optional metadata to store with subscription.

        Returns:
            Created Subscription instance.

        Raises:
            IyzicoValidationException: If validation fails.
            IyzicoAPIException: If payment fails.

        Example:
            >>> subscription = manager.create_subscription(
            ...     user=user,
            ...     plan=premium_plan,
            ...     payment_method={
            ...         'card_holder_name': 'John Doe',
            ...         'card_number': '5528790000000008',
            ...         'expire_month': '12',
            ...         'expire_year': '2030',
            ...         'cvc': '123',
            ...     },
            ...     trial=True,
            ... )
        """
        # Validate plan can accept subscribers
        if not plan.can_accept_subscribers():
            raise IyzicoValidationException("Subscription plan is not available or at capacity")

        # Set start date
        if start_date is None:
            start_date = timezone.now()

        # Calculate trial period
        trial_end_date = None
        if trial and plan.trial_period_days > 0:
            trial_end_date = start_date + timedelta(days=plan.trial_period_days)

        # Calculate first billing period
        billing_interval_days = plan.get_billing_interval_days()
        if trial_end_date:
            # First billing after trial
            current_period_start = start_date
            current_period_end = trial_end_date
            next_billing_date = trial_end_date
            initial_status = SubscriptionStatus.TRIALING
            process_initial_payment = False
        else:
            # Bill immediately
            current_period_start = start_date
            current_period_end = start_date + timedelta(days=billing_interval_days)
            next_billing_date = current_period_end
            initial_status = SubscriptionStatus.PENDING
            process_initial_payment = True

        # Create subscription
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status=initial_status,
            start_date=start_date,
            trial_end_date=trial_end_date,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            next_billing_date=next_billing_date,
            metadata=metadata or {},
        )

        logger.info(f"Created subscription {subscription.id} for user {user.id}")

        # Process initial payment if not in trial
        if process_initial_payment:
            # Get buyer info for payment method storage
            buyer_info = self._get_buyer_info(user)

            payment = self._create_subscription_payment(
                subscription=subscription,
                payment_method=payment_method,
                attempt_number=1,
            )

            if payment.is_successful():
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.save(update_fields=["status"])
                logger.info(f"Subscription {subscription.id} activated after initial payment")

                # Register card with Iyzico and store payment method for recurring billing
                try:
                    self._store_payment_method(subscription, payment_method, buyer_info)
                except Exception as e:
                    logger.error(
                        f"Failed to store payment method for subscription {subscription.id}: {e}. "
                        f"Recurring billing may not work without stored payment method."
                    )
                    # Don't fail the subscription creation if payment method storage fails
                    # The subscription is already active and paid
            else:
                subscription.status = SubscriptionStatus.PAST_DUE
                subscription.failed_payment_count = 1
                subscription.last_payment_error = payment.error_message or "Payment failed"
                subscription.save(
                    update_fields=[
                        "status",
                        "failed_payment_count",
                        "last_payment_error",
                    ]
                )
                logger.warning(f"Subscription {subscription.id} initial payment failed")

        # Import and send signal
        from .signals import subscription_created

        subscription_created.send(
            sender=Subscription,
            subscription=subscription,
            user=user,
        )

        return subscription

    @transaction.atomic
    def process_billing(
        self,
        subscription: Subscription,
        payment_method: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionPayment:
        """
        Process recurring billing for a subscription with race condition protection.

        Uses database-level row locking (SELECT FOR UPDATE) to prevent double billing
        when concurrent billing tasks are processed.

        Args:
            subscription: Subscription to bill.
            payment_method: Optional payment method details. If not provided, uses
                           stored payment method (recommended for recurring billing).

        Returns:
            Created SubscriptionPayment instance.

        Raises:
            IyzicoValidationException: If subscription cannot be billed or no payment method found.
            IyzicoAPIException: If payment processing fails.

        Example:
            >>> # Automatic (uses stored payment method)
            >>> payment = manager.process_billing(subscription=subscription)

            >>> # Manual (provide payment method)
            >>> payment = manager.process_billing(
            ...     subscription=subscription,
            ...     payment_method={'cardToken': '...', 'cardUserKey': '...'},
            ... )

        Security Note:
            This method implements the following safeguards against double billing:
            1. Database row-level locking via SELECT FOR UPDATE
            2. Re-checking for recent successful payments after acquiring lock
            3. Database-level unique constraint on payment records
        """
        # Lock the subscription row to prevent concurrent billing
        # This blocks other transactions until this one completes
        locked_subscription = Subscription.objects.select_for_update(
            nowait=False  # Wait for lock if another transaction has it
        ).get(pk=subscription.pk)

        # Validate subscription can be billed (after acquiring lock)
        if not locked_subscription.can_be_renewed():
            raise IyzicoValidationException(
                f"Subscription {locked_subscription.id} cannot be billed "
                f"(status: {locked_subscription.status})"
            )

        # Get payment method (stored or provided)
        if payment_method is None:
            payment_method = self._get_stored_payment_method(locked_subscription)
            if not payment_method:
                raise IyzicoValidationException(
                    f"No payment method available for subscription {locked_subscription.id}. "
                    f"User must add a payment method before recurring billing can proceed.",
                    error_code="NO_PAYMENT_METHOD",
                )
            logger.info(f"Using stored payment method for subscription {locked_subscription.id}")
        else:
            logger.info(f"Using provided payment method for subscription {locked_subscription.id}")

        # Check if already billed recently AFTER acquiring lock
        # (critical for race condition prevention)
        # This is the second line of defense after the lock
        recent_payment = locked_subscription.payments.filter(
            created_at__gte=timezone.now() - timedelta(hours=1),
            status="success",
        ).first()

        if recent_payment:
            logger.warning(
                f"Subscription {locked_subscription.id} already billed recently "
                f"(payment {recent_payment.id}), skipping duplicate charge"
            )
            return recent_payment

        # Determine attempt number
        if locked_subscription.is_past_due():
            attempt_number = locked_subscription.failed_payment_count + 1
            is_retry = True
        else:
            attempt_number = 1
            is_retry = False

        # Create and process payment (uses locked_subscription for consistency)
        payment = self._create_subscription_payment(
            subscription=locked_subscription,
            payment_method=payment_method,
            attempt_number=attempt_number,
            is_retry=is_retry,
        )

        # Update subscription based on payment result
        if payment.is_successful():
            self._handle_successful_payment(locked_subscription)
        else:
            self._handle_failed_payment(locked_subscription, payment.error_message)

        return payment

    def _create_subscription_payment(
        self,
        subscription: Subscription,
        payment_method: Dict[str, Any],
        attempt_number: int = 1,
        is_retry: bool = False,
    ) -> SubscriptionPayment:
        """
        Create and process a subscription payment.

        This method validates payment data BEFORE creating database records
        to prevent orphaned payment records on validation failure.

        Args:
            subscription: Subscription to charge.
            payment_method: Payment method details.
            attempt_number: Payment attempt number.
            is_retry: Whether this is a retry.

        Returns:
            Created and processed SubscriptionPayment.

        Note:
            Database record is only created AFTER successful API call or
            confirmed API response (including failures). This prevents
            orphaned 'pending' records from validation errors.
        """
        from .exceptions import CardError, PaymentError

        # Prepare payment data BEFORE creating database record
        amount = subscription.plan.price
        currency = subscription.plan.currency

        # Generate a temporary basket ID (will be updated with payment ID)
        import uuid

        temp_basket_id = f"SUB-{subscription.id}-{uuid.uuid4().hex[:8]}"

        # Get buyer and address info (validates user profile)
        try:
            buyer_info = self._get_buyer_info(subscription.user)
            address_info = self._get_address_info(subscription.user)
        except IyzicoValidationException as e:
            # User profile incomplete - don't create a payment record for validation errors
            logger.error(
                f"Cannot process payment for subscription {subscription.id}: "
                f"User profile validation failed - {e}"
            )
            raise

        # Prepare payment basket
        basket_items = [
            {
                "id": str(subscription.plan.id),
                "name": subscription.plan.name,
                "category1": "Subscription",
                "itemType": "VIRTUAL",
                "price": str(amount),
            }
        ]

        # Prepare order data
        order_data = {
            "price": str(amount),
            "paidPrice": str(amount),
            "currency": currency,
            "basketId": temp_basket_id,
            "conversationId": temp_basket_id,
        }

        # Update subscription's last payment attempt timestamp
        subscription.last_payment_attempt = timezone.now()
        subscription.save(update_fields=["last_payment_attempt"])

        logger.info(
            f"Processing subscription payment for subscription {subscription.id} "
            f"(attempt {attempt_number}, retry={is_retry})"
        )

        # Process payment via Iyzico API FIRST
        payment_id = None
        status = "failure"
        error_code = None
        error_message = None

        try:
            # Detect if using stored payment method (token-based) or full card details
            is_token_payment = "cardToken" in payment_method and "cardUserKey" in payment_method

            if is_token_payment:
                # Use token-based payment API for recurring billing
                logger.debug(f"Using token-based payment for subscription {subscription.id}")
                response = self.client.create_payment_with_token(
                    order_data=order_data,
                    card_token=payment_method["cardToken"],
                    card_user_key=payment_method["cardUserKey"],
                    buyer=buyer_info,
                    billing_address=address_info,
                    shipping_address=address_info,
                    basket_items=basket_items,
                )
            else:
                # Use regular payment API with full card details
                logger.debug(f"Using full card payment for subscription {subscription.id}")
                response = self.client.create_payment(
                    order_data=order_data,
                    payment_card=payment_method,
                    buyer=buyer_info,
                    billing_address=address_info,
                    shipping_address=address_info,
                    basket_items=basket_items,
                )

            # Extract response data
            payment_id = response.payment_id
            status = "success" if response.status == "success" else "failure"
            error_code = response.error_code
            error_message = response.error_message

            if status == "success":
                logger.info(
                    f"Subscription payment successful for subscription {subscription.id}, "
                    f"Iyzico payment_id: {payment_id}"
                )
            else:
                logger.warning(
                    f"Subscription payment failed for subscription {subscription.id}: "
                    f"{error_message}"
                )

        except CardError as e:
            # Card-specific errors (declined, insufficient funds, etc.)
            error_code = e.error_code
            error_message = f"Card error: {str(e)}"
            logger.warning(f"Card error for subscription {subscription.id}: {e}")

        except PaymentError as e:
            # Payment processing errors
            error_code = e.error_code
            error_message = f"Payment error: {str(e)}"
            logger.warning(f"Payment error for subscription {subscription.id}: {e}")

        except IyzicoAPIException as e:
            # API errors (might be temporary)
            error_code = e.error_code
            error_message = f"API error: {str(e)}"
            logger.error(f"API error for subscription {subscription.id}: {e}")

        except Exception as e:
            # Unexpected errors - explicitly set error_code for clarity
            error_code = None
            error_message = f"Unexpected error: {str(e)}"
            logger.exception(f"Unexpected error processing subscription {subscription.id}")

        # NOW create the database record with the actual result
        # This prevents orphaned 'pending' records
        payment = SubscriptionPayment.objects.create(
            subscription=subscription,
            user=subscription.user,
            amount=amount,
            currency=currency,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            attempt_number=attempt_number,
            is_retry=is_retry,
            status=status,
            payment_id=payment_id,
            error_code=error_code,
            error_message=error_message,
        )

        logger.info(
            f"Created subscription payment record {payment.id} "
            f"(status={status}, attempt={attempt_number})"
        )

        return payment

    def _handle_successful_payment(self, subscription: Subscription) -> None:
        """Handle successful payment - update subscription status and dates."""
        # Move to next billing period
        billing_interval_days = subscription.plan.get_billing_interval_days()
        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = subscription.current_period_end + timedelta(
            days=billing_interval_days
        )
        subscription.next_billing_date = subscription.current_period_end

        # Update status
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.failed_payment_count = 0
        subscription.last_payment_error = None

        subscription.save()

        logger.info(f"Subscription {subscription.id} renewed successfully")

        # Send signal
        from .signals import subscription_payment_succeeded

        subscription_payment_succeeded.send(
            sender=Subscription,
            subscription=subscription,
        )

    def _handle_failed_payment(
        self,
        subscription: Subscription,
        error_message: Optional[str],
    ) -> None:
        """Handle failed payment - update subscription status."""
        subscription.failed_payment_count += 1
        subscription.last_payment_error = error_message
        subscription.status = SubscriptionStatus.PAST_DUE
        subscription.save()

        logger.warning(
            f"Subscription {subscription.id} payment failed "
            f"({subscription.failed_payment_count} attempts)"
        )

        # Send signal
        from .signals import subscription_payment_failed

        subscription_payment_failed.send(
            sender=Subscription,
            subscription=subscription,
            error_message=error_message,
        )

    @transaction.atomic
    def cancel_subscription(
        self,
        subscription: Subscription,
        at_period_end: bool = True,
        reason: Optional[str] = None,
    ) -> Subscription:
        """
        Cancel a subscription.

        Args:
            subscription: Subscription to cancel.
            at_period_end: If True, cancel at end of current period.
                          If False, cancel immediately.
            reason: Optional cancellation reason.

        Returns:
            Updated Subscription instance.

        Example:
            >>> manager.cancel_subscription(
            ...     subscription=subscription,
            ...     at_period_end=True,
            ...     reason="User requested cancellation",
            ... )
        """
        if subscription.is_cancelled():
            logger.warning(f"Subscription {subscription.id} already cancelled")
            return subscription

        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = reason

        if at_period_end:
            # Cancel at end of period
            subscription.cancel_at_period_end = True
            subscription.save()
            logger.info(f"Subscription {subscription.id} marked for cancellation at period end")
        else:
            # Cancel immediately
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.ended_at = timezone.now()
            subscription.save()
            logger.info(f"Subscription {subscription.id} cancelled immediately")

        # Send signal
        from .signals import subscription_cancelled

        subscription_cancelled.send(
            sender=Subscription,
            subscription=subscription,
            immediate=not at_period_end,
        )

        return subscription

    @transaction.atomic
    def pause_subscription(self, subscription: Subscription) -> Subscription:
        """
        Pause subscription (stop billing temporarily).

        Args:
            subscription: Subscription to pause.

        Returns:
            Updated Subscription instance.
        """
        if not subscription.is_active():
            raise IyzicoValidationException(
                f"Cannot pause subscription {subscription.id} - not active"
            )

        subscription.status = SubscriptionStatus.PAUSED
        subscription.save()

        logger.info(f"Subscription {subscription.id} paused")

        # Send signal
        from .signals import subscription_paused

        subscription_paused.send(
            sender=Subscription,
            subscription=subscription,
        )

        return subscription

    @transaction.atomic
    def resume_subscription(self, subscription: Subscription) -> Subscription:
        """
        Resume a paused subscription.

        Args:
            subscription: Subscription to resume.

        Returns:
            Updated Subscription instance.
        """
        if subscription.status != SubscriptionStatus.PAUSED:
            raise IyzicoValidationException(
                f"Cannot resume subscription {subscription.id} - not paused"
            )

        subscription.status = SubscriptionStatus.ACTIVE
        subscription.save()

        logger.info(f"Subscription {subscription.id} resumed")

        # Send signal
        from .signals import subscription_resumed

        subscription_resumed.send(
            sender=Subscription,
            subscription=subscription,
        )

        return subscription

    @transaction.atomic
    def upgrade_subscription(
        self,
        subscription: Subscription,
        new_plan: SubscriptionPlan,
        prorate: bool = True,
    ) -> Subscription:
        """
        Upgrade to a higher-tier plan.

        Args:
            subscription: Subscription to upgrade.
            new_plan: New (higher-tier) plan.
            prorate: Whether to charge prorated amount immediately.

        Returns:
            Updated Subscription instance.

        Example:
            >>> manager.upgrade_subscription(
            ...     subscription=basic_subscription,
            ...     new_plan=premium_plan,
            ...     prorate=True,
            ... )
        """
        if not subscription.is_active():
            raise IyzicoValidationException(
                f"Cannot upgrade subscription {subscription.id} - not active"
            )

        if new_plan.price <= subscription.plan.price:
            raise IyzicoValidationException(
                "New plan must be higher-tier (more expensive) for upgrade"
            )

        old_plan = subscription.plan
        subscription.plan = new_plan

        if prorate:
            # Calculate prorated charge
            days_remaining = (subscription.current_period_end - timezone.now()).days
            total_days = (subscription.current_period_end - subscription.current_period_start).days
            proration_factor = Decimal(str(days_remaining / max(total_days, 1)))
            price_difference = new_plan.price - old_plan.price
            prorated_charge = price_difference * proration_factor

            # TODO: Process prorated payment
            # This would require payment method storage or user input
            logger.info(
                f"Subscription {subscription.id} upgraded with prorated charge: "
                f"{prorated_charge} {new_plan.currency}"
            )

        subscription.save()

        logger.info(
            f"Subscription {subscription.id} upgraded from {old_plan.name} " f"to {new_plan.name}"
        )

        return subscription

    @transaction.atomic
    def downgrade_subscription(
        self,
        subscription: Subscription,
        new_plan: SubscriptionPlan,
        at_period_end: bool = True,
    ) -> Subscription:
        """
        Downgrade to a lower-tier plan.

        Args:
            subscription: Subscription to downgrade.
            new_plan: New (lower-tier) plan.
            at_period_end: If True, apply at end of current period.
                          If False, apply immediately (with refund).

        Returns:
            Updated Subscription instance.
        """
        if not subscription.is_active():
            raise IyzicoValidationException(
                f"Cannot downgrade subscription {subscription.id} - not active"
            )

        if new_plan.price >= subscription.plan.price:
            raise IyzicoValidationException(
                "New plan must be lower-tier (less expensive) for downgrade"
            )

        old_plan = subscription.plan

        if at_period_end:
            # Store downgrade in metadata to apply later
            subscription.metadata["pending_downgrade"] = {
                "new_plan_id": new_plan.id,
                "scheduled_at": timezone.now().isoformat(),
            }
            subscription.save()

            logger.info(
                f"Subscription {subscription.id} scheduled for downgrade to "
                f"{new_plan.name} at period end"
            )
        else:
            # Apply immediately
            subscription.plan = new_plan
            # TODO: Calculate and process refund for unused time
            subscription.save()

            logger.info(
                f"Subscription {subscription.id} downgraded immediately from "
                f"{old_plan.name} to {new_plan.name}"
            )

        return subscription

    def _get_buyer_info(self, user: User) -> Dict[str, str]:
        """
        Get buyer information for Iyzico API.

        Validates that required user profile information is present.
        Falls back to user model fields or raises validation error for
        truly missing required data.

        Args:
            user: User instance with profile data.

        Returns:
            Dictionary with buyer information for Iyzico.

        Raises:
            IyzicoValidationException: If required fields are missing.

        Required Fields for Iyzico API:
            - name (first_name)
            - surname (last_name)
            - email
            - identityNumber (Turkish ID - 11 digits)
            - registrationAddress
            - city
            - country

        Note:
            Users should configure IYZICO_USER_PROFILE_FIELDS in settings
            to specify which user model fields or related model fields
            contain the required data.
        """
        # Get profile data source - can be user model or related profile
        profile_attr = getattr(settings, "IYZICO_USER_PROFILE_ATTR", None)
        if profile_attr:
            profile = getattr(user, profile_attr, None)
            if not profile:
                raise IyzicoValidationException(
                    f"User {user.id} does not have required profile ({profile_attr})",
                    error_code="MISSING_USER_PROFILE",
                )
        else:
            profile = user  # Use user model directly

        # Helper to get field from profile or user
        def get_field(field_name: str, user_fallback: str = None, required: bool = False) -> str:
            # Try profile first, then user model
            value = getattr(profile, field_name, None)
            if not value and user_fallback:
                value = getattr(user, user_fallback, None)
            if not value and required:
                raise IyzicoValidationException(
                    f"Required field '{field_name}' missing for user {user.id}",
                    error_code="MISSING_REQUIRED_FIELD",
                )
            return str(value) if value else ""

        # Get required fields with validation
        first_name = get_field("first_name", required=True)
        last_name = get_field("last_name", required=True)
        email = get_field("email", required=True)

        # Identity number - required for Turkish transactions
        identity_number = get_field("identity_number")
        if not identity_number:
            identity_number = get_field("tc_kimlik_no")  # Alternative field name
        if not identity_number:
            identity_number = get_field("identityNumber")

        # Validate identity number format (Turkish TC Kimlik: 11 digits)
        if identity_number:
            identity_number = identity_number.strip()
            if len(identity_number) != 11 or not identity_number.isdigit():
                raise IyzicoValidationException(
                    f"Invalid identity number format for user {user.id}. "
                    f"Turkish TC Kimlik must be 11 digits.",
                    error_code="INVALID_IDENTITY_NUMBER",
                )
        else:
            raise IyzicoValidationException(
                f"Identity number (TC Kimlik) is required for user {user.id}",
                error_code="MISSING_IDENTITY_NUMBER",
            )

        # Address fields
        address = get_field("address") or get_field("registration_address")
        if not address:
            raise IyzicoValidationException(
                f"Registration address is required for user {user.id}",
                error_code="MISSING_ADDRESS",
            )

        city = get_field("city")
        if not city:
            raise IyzicoValidationException(
                f"City is required for user {user.id}",
                error_code="MISSING_CITY",
            )

        country = get_field("country") or "Turkey"

        # IP address - get from user's last login or metadata
        # In production, this should come from the request context
        ip_address = get_field("last_login_ip") or get_field("ip_address")
        if not ip_address:
            # Use iyzico_settings for IP validation configuration
            from .settings import iyzico_settings

            if iyzico_settings.strict_ip_validation:
                raise IyzicoValidationException(
                    f"IP address is required for user {user.id}. "
                    f"Configure IP tracking in your user model or set "
                    f"IYZICO_STRICT_IP_VALIDATION=False for development.",
                    error_code="MISSING_IP_ADDRESS",
                )
            # Default to configured IP in non-strict mode (dev only)
            ip_address = iyzico_settings.default_ip
            logger.warning(
                f"Using default IP address ({ip_address}) for user {user.id}. "
                f"This is NOT production-safe. Enable "
                f"IYZICO_STRICT_IP_VALIDATION=True and configure IP tracking."
            )

        # Phone number (optional but recommended)
        phone = get_field("phone") or get_field("gsm_number") or get_field("phone_number") or ""

        return {
            "id": str(user.id),
            "name": first_name,
            "surname": last_name,
            "email": email,
            "identityNumber": identity_number,
            "registrationAddress": address,
            "city": city,
            "country": country,
            "ip": ip_address,
            "gsmNumber": phone,
        }

    def _get_address_info(self, user: User) -> Dict[str, str]:
        """
        Get address information for Iyzico API.

        Retrieves billing/shipping address from user profile.

        Args:
            user: User instance with address data.

        Returns:
            Dictionary with address information for Iyzico.

        Raises:
            IyzicoValidationException: If required address fields are missing.
        """
        # Get profile data source
        profile_attr = getattr(settings, "IYZICO_USER_PROFILE_ATTR", None)
        if profile_attr:
            profile = getattr(user, profile_attr, None)
        else:
            profile = user

        # Helper to get field
        def get_field(field_name: str) -> str:
            value = getattr(profile, field_name, None) if profile else None
            if not value:
                value = getattr(user, field_name, None)
            return str(value) if value else ""

        # Get address fields
        address = get_field("address") or get_field("billing_address")
        city = get_field("city")
        country = get_field("country") or "Turkey"

        # Contact name
        first_name = get_field("first_name") or "User"
        last_name = get_field("last_name") or ""
        contact_name = f"{first_name} {last_name}".strip()

        if not address:
            raise IyzicoValidationException(
                f"Address is required for user {user.id}",
                error_code="MISSING_ADDRESS",
            )

        if not city:
            raise IyzicoValidationException(
                f"City is required for user {user.id}",
                error_code="MISSING_CITY",
            )

        return {
            "address": address,
            "contactName": contact_name,
            "city": city,
            "country": country,
        }

    def _store_payment_method(
        self,
        subscription: Subscription,
        payment_card: Dict[str, Any],
        buyer_info: Dict[str, str],
    ) -> None:
        """
        Register card with Iyzico and store payment method for recurring billing.

        Args:
            subscription: Subscription instance
            payment_card: Card information dict (from initial payment)
            buyer_info: Buyer information dict

        Note:
            This method registers the card with Iyzico to get secure tokens,
            then creates a PaymentMethod record. The card tokens enable recurring
            payments without storing actual card numbers (PCI DSS compliant).
        """
        from .subscription_models import CardBrand, PaymentMethod

        user = subscription.user

        try:
            # Register card with Iyzico to get tokens
            card_result = self.client.register_card(
                card_info={
                    "cardHolderName": payment_card.get("cardHolderName"),
                    "cardNumber": payment_card.get("cardNumber"),
                    "expireMonth": payment_card.get("expireMonth"),
                    "expireYear": payment_card.get("expireYear"),
                    "cvc": payment_card.get("cvc"),
                    "cardAlias": f"Card for {subscription.plan.name}",
                },
                buyer=buyer_info,
                external_id=str(user.id),
            )

            # Map card association to CardBrand enum
            card_association = card_result.get("card_association", "").upper()
            card_brand = CardBrand.OTHER
            if "VISA" in card_association:
                card_brand = CardBrand.VISA
            elif "MASTER" in card_association:
                card_brand = CardBrand.MASTERCARD
            elif "AMEX" in card_association or "AMERICAN" in card_association:
                card_brand = CardBrand.AMEX
            elif "TROY" in card_association:
                card_brand = CardBrand.TROY

            # Create or update payment method
            payment_method, created = PaymentMethod.objects.update_or_create(
                user=user,
                card_token=card_result["card_token"],
                defaults={
                    "card_user_key": card_result["card_user_key"],
                    "card_last_four": card_result["last_four_digits"],
                    "card_brand": card_brand,
                    "card_type": card_result.get("card_type"),
                    "card_family": card_result.get("card_family"),
                    "card_bank_name": card_result.get("card_bank_name"),
                    "card_holder_name": card_result.get("card_holder_name"),
                    "expiry_month": card_result["expiry_month"],
                    "expiry_year": card_result["expiry_year"],
                    "bin_number": card_result.get("bin_number"),
                    "is_default": True,  # First card is default
                    "is_active": True,
                    "is_verified": True,  # Verified by successful payment
                    "last_used_at": timezone.now(),
                    "metadata": {
                        "subscription_id": subscription.id,
                        "plan_name": subscription.plan.name,
                    },
                },
            )

            if created:
                logger.info(
                    f"Created payment method {payment_method.id} for user {user.id} "
                    f"(subscription {subscription.id})"
                )
            else:
                logger.info(f"Updated payment method {payment_method.id} for user {user.id}")

        except Exception as e:
            logger.error(
                f"Failed to store payment method for subscription {subscription.id}: {e}",
                exc_info=True,
            )
            raise

    def _get_stored_payment_method(
        self,
        subscription: Subscription,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored payment method for recurring billing.

        Args:
            subscription: Subscription instance

        Returns:
            Payment card dict with tokens, or None if no stored method

        Note:
            Returns a dict compatible with Iyzico's token payment API,
            containing only card tokens (not actual card numbers).
        """
        from .subscription_models import PaymentMethod

        # Get default payment method for user
        payment_method = PaymentMethod.get_default_for_user(subscription.user)

        if not payment_method:
            logger.warning(
                f"No stored payment method found for user {subscription.user.id} "
                f"(subscription {subscription.id})"
            )
            return None

        # Check if card is expired
        if payment_method.is_expired():
            logger.warning(
                f"Payment method {payment_method.id} for user {subscription.user.id} "
                f"has expired. Marking as inactive."
            )
            payment_method.deactivate()
            return None

        # Warn if card expires soon
        if payment_method.expires_soon(within_days=30):
            logger.warning(
                f"Payment method {payment_method.id} for user {subscription.user.id} "
                f"expires soon ({payment_method.expiry_month}/{payment_method.expiry_year})"
            )

        # Mark as used
        payment_method.mark_as_used()

        # Return token-based payment dict
        return payment_method.to_payment_dict()
