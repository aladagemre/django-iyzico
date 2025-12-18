"""
Django views for django-iyzico.

Handles webhooks, 3D Secure callbacks, and payment processing views.
"""

import json
import logging
from typing import Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .client import IyzicoClient
from .exceptions import IyzicoError, ThreeDSecureError, WebhookError
from .settings import iyzico_settings
from .signals import (
    threeds_completed,
    threeds_failed,
    webhook_received,
)
from .utils import verify_webhook_signature, is_ip_allowed

logger = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address from request.

    Checks X-Forwarded-For header first (for proxies/load balancers),
    then falls back to REMOTE_ADDR.

    Args:
        request: HTTP request

    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')

    return ip


@csrf_exempt
@require_http_methods(["GET", "POST"])
def threeds_callback_view(request: HttpRequest) -> HttpResponse:
    """
    Handle 3D Secure callback from Iyzico.

    This view is called by Iyzico after the user completes 3D Secure authentication.
    The callback can be either GET or POST depending on Iyzico's configuration.

    URL: /iyzico/callback/

    Query Parameters (GET):
        token: Payment token from Iyzico

    Form Data (POST):
        paymentId: Payment token from Iyzico (alternative to token)

    Returns:
        Redirect to success or error page

    Note:
        This view is CSRF exempt because it's called by an external service (Iyzico).
        Users should implement their own success/failure redirect URLs.
    """
    # Get token from either GET or POST
    token = request.GET.get("token") or request.POST.get("paymentId")

    if not token:
        logger.error("3DS callback received without token")
        return _handle_3ds_error(
            request,
            "Missing payment token",
            error_code="MISSING_TOKEN",
        )

    logger.info(f"3DS callback received - token={token[:10]}...")

    try:
        # Complete 3D Secure payment
        client = IyzicoClient()
        response = client.complete_3ds_payment(token)

        if response.is_successful():
            logger.info(
                f"3DS payment completed successfully - "
                f"payment_id={response.payment_id}, "
                f"conversation_id={response.conversation_id}"
            )

            # Trigger signal for successful payment
            threeds_completed.send(
                sender=None,
                payment_id=response.payment_id,
                conversation_id=response.conversation_id,
                response=response.to_dict(),
                request=request,
            )

            # Redirect to success page
            return _handle_3ds_success(request, response)

        else:
            logger.warning(
                f"3DS payment failed - "
                f"error_code={response.error_code}, "
                f"error_message={response.error_message}, "
                f"conversation_id={response.conversation_id}"
            )

            # Trigger signal for failed payment
            threeds_failed.send(
                sender=None,
                conversation_id=response.conversation_id,
                error_code=response.error_code,
                error_message=response.error_message,
                request=request,
            )

            # Redirect to error page
            return _handle_3ds_error(
                request,
                response.error_message,
                error_code=response.error_code,
                conversation_id=response.conversation_id,
            )

    except ThreeDSecureError as e:
        logger.error(f"3DS completion error: {str(e)}", exc_info=True)

        # Trigger signal for failed payment
        threeds_failed.send(
            sender=None,
            conversation_id=None,
            error_code=e.error_code,
            error_message=str(e),
            request=request,
        )

        return _handle_3ds_error(
            request,
            str(e),
            error_code=e.error_code,
        )

    except Exception as e:
        logger.error(f"Unexpected error in 3DS callback: {str(e)}", exc_info=True)

        # Trigger signal for failed payment
        threeds_failed.send(
            sender=None,
            conversation_id=None,
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
            request=request,
        )

        return _handle_3ds_error(
            request,
            "An unexpected error occurred",
            error_code="UNEXPECTED_ERROR",
        )


@csrf_exempt
@require_POST
def webhook_view(request: HttpRequest) -> JsonResponse:
    """
    Handle webhook notifications from Iyzico.

    This view receives POST requests from Iyzico for various payment events.
    Supports optional signature validation and IP whitelisting.

    URL: /iyzico/webhook/

    Request Headers:
        X-Iyzico-Signature: HMAC-SHA256 signature (if signature validation enabled)

    Request Body (JSON):
        {
            "iyziEventType": "event_type",
            "paymentId": "payment_id",
            "conversationId": "conversation_id",
            ...
        }

    Returns:
        JSON response with status 200 (always, to prevent retry spam)

    Note:
        - This view is CSRF exempt (external webhook)
        - Always returns 200 OK to prevent webhook retry spam
        - Actual processing should be done asynchronously via signals
        - Users should connect to the webhook_received signal to handle events

    Security:
        - Optional signature validation via IYZICO_WEBHOOK_SECRET setting
        - Optional IP whitelisting via IYZICO_WEBHOOK_ALLOWED_IPS setting
    """
    logger.info("Webhook received")

    # Get client IP
    client_ip = get_client_ip(request)
    logger.debug(f"Webhook from IP: {client_ip}")

    # Verify IP whitelist
    allowed_ips = iyzico_settings.webhook_allowed_ips

    # SECURITY: In production, require IP whitelist to be configured
    if not allowed_ips:
        from django.conf import settings as django_settings
        if not getattr(django_settings, 'DEBUG', False):
            logger.error(
                "SECURITY WARNING: Webhook IP whitelist not configured in production! "
                "Set IYZICO_WEBHOOK_ALLOWED_IPS in your settings. "
                "Rejecting webhook to prevent unauthorized access."
            )
            return JsonResponse(
                {"status": "error", "message": "Webhook security not configured"},
                status=403,
            )
        else:
            logger.warning(
                "Webhook IP whitelist not configured. Allowing all IPs in DEBUG mode. "
                "Configure IYZICO_WEBHOOK_ALLOWED_IPS for production."
            )

    if allowed_ips and not is_ip_allowed(client_ip, allowed_ips):
        logger.warning(f"Webhook rejected - IP {client_ip} not in whitelist")
        return JsonResponse(
            {"status": "error", "message": "IP not allowed"},
            status=403,
        )

    # Verify webhook signature (if configured)
    webhook_secret = iyzico_settings.webhook_secret
    if webhook_secret:
        signature = request.META.get('HTTP_X_IYZICO_SIGNATURE', '')
        payload = request.body

        if not verify_webhook_signature(payload, signature, webhook_secret):
            logger.warning("Webhook rejected - invalid signature")
            return JsonResponse(
                {"status": "error", "message": "Invalid signature"},
                status=403,
            )

    try:
        # Parse webhook data
        try:
            webhook_data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid webhook JSON: {str(e)}")
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON"},
                status=200,  # Still return 200 to avoid retry
            )

        # Extract event information
        event_type = webhook_data.get("iyziEventType")
        payment_id = webhook_data.get("paymentId")
        conversation_id = webhook_data.get("conversationId")

        logger.info(
            f"Webhook event - type={event_type}, "
            f"payment_id={payment_id}, "
            f"conversation_id={conversation_id}"
        )

        # Log full webhook data (for debugging)
        logger.debug(f"Webhook data: {webhook_data}")

        # Trigger signal for webhook processing
        # Users should connect to this signal to handle webhooks
        webhook_received.send(
            sender=None,
            event_type=event_type,
            payment_id=payment_id,
            conversation_id=conversation_id,
            data=webhook_data,
            request=request,
        )

        # Return success immediately
        # Actual processing should be done asynchronously via signal handlers
        return JsonResponse(
            {"status": "success", "message": "Webhook received"},
            status=200,
        )

    except Exception as e:
        # Log error but still return 200 to avoid webhook retry spam
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)

        return JsonResponse(
            {"status": "error", "message": "Internal error"},
            status=200,  # Still 200 to avoid retry
        )


def _handle_3ds_success(request: HttpRequest, response) -> HttpResponse:
    """
    Handle successful 3DS payment redirect.

    Users can customize this behavior by:
    1. Setting IYZICO_SUCCESS_URL in Django settings
    2. Passing success_url in session
    3. Overriding this function

    Args:
        request: HTTP request
        response: Payment response from Iyzico

    Returns:
        HttpResponse (redirect or rendered page)
    """
    from django.conf import settings

    # Try to get success URL from various sources
    success_url = (
        request.session.get("iyzico_success_url")
        or getattr(settings, "IYZICO_SUCCESS_URL", None)
        or "/payment/success/"
    )

    # Clean up session
    if "iyzico_success_url" in request.session:
        del request.session["iyzico_success_url"]
    if "iyzico_error_url" in request.session:
        del request.session["iyzico_error_url"]

    # Add payment info to session for success page
    request.session["last_payment_id"] = response.payment_id
    request.session["last_payment_status"] = "success"

    logger.debug(f"Redirecting to success URL: {success_url}")
    return redirect(success_url)


def _handle_3ds_error(
    request: HttpRequest,
    error_message: str,
    error_code: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> HttpResponse:
    """
    Handle failed 3DS payment redirect.

    Users can customize this behavior by:
    1. Setting IYZICO_ERROR_URL in Django settings
    2. Passing error_url in session
    3. Overriding this function

    Args:
        request: HTTP request
        error_message: Error message
        error_code: Error code (optional)
        conversation_id: Conversation ID (optional)

    Returns:
        HttpResponse (redirect or rendered page)
    """
    from django.conf import settings

    # Try to get error URL from various sources
    error_url = (
        request.session.get("iyzico_error_url")
        or getattr(settings, "IYZICO_ERROR_URL", None)
        or "/payment/error/"
    )

    # Clean up session
    if "iyzico_success_url" in request.session:
        del request.session["iyzico_success_url"]
    if "iyzico_error_url" in request.session:
        del request.session["iyzico_error_url"]

    # Add error info to session for error page
    request.session["last_payment_status"] = "failed"
    request.session["last_payment_error"] = error_message
    if error_code:
        request.session["last_payment_error_code"] = error_code
    if conversation_id:
        request.session["last_payment_conversation_id"] = conversation_id

    logger.debug(f"Redirecting to error URL: {error_url}")
    return redirect(error_url)


# Optional: Helper view for testing webhooks in development
@csrf_exempt
@require_POST
def test_webhook_view(request: HttpRequest) -> JsonResponse:
    """
    Test webhook endpoint for development.

    This view can be used to manually trigger webhook events during development.

    URL: /iyzico/webhook/test/

    Note:
        This view should be disabled in production!
    """
    from django.conf import settings

    # Only allow in DEBUG mode
    if not getattr(settings, "DEBUG", False):
        return JsonResponse(
            {"status": "error", "message": "Not available in production"},
            status=403,
        )

    logger.info("Test webhook triggered")

    # Create test webhook data
    test_data = {
        "iyziEventType": "test_event",
        "paymentId": "test_payment_id",
        "conversationId": "test_conversation_id",
        "status": "success",
        "test": True,
    }

    # Trigger webhook signal
    webhook_received.send(
        sender=None,
        event_type=test_data["iyziEventType"],
        payment_id=test_data["paymentId"],
        conversation_id=test_data["conversationId"],
        data=test_data,
        request=request,
    )

    return JsonResponse(
        {"status": "success", "message": "Test webhook triggered"},
        status=200,
    )
