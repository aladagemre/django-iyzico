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
from .utils import verify_webhook_signature, is_ip_allowed, get_client_ip

logger = logging.getLogger(__name__)

# Rate limiting constants
THREEDS_CALLBACK_RATE_LIMIT = 30  # requests per minute per IP
THREEDS_CALLBACK_RATE_WINDOW = 60  # seconds
WEBHOOK_RATE_LIMIT = 100  # requests per minute per IP
WEBHOOK_RATE_WINDOW = 60  # seconds


def _validate_redirect_url(url: Optional[str], request: HttpRequest) -> Optional[str]:
    """
    Validate that redirect URL is safe (relative or same host).

    Security: Rejects external URLs and handles wildcard ALLOWED_HOSTS safely
    to prevent open redirect attacks.

    Args:
        url: URL to validate
        request: HTTP request for host comparison

    Returns:
        Safe URL or None if URL is invalid/external
    """
    from urllib.parse import urlparse

    if not url:
        return None

    parsed = urlparse(url)

    # Allow relative URLs (no scheme or netloc)
    if not parsed.scheme and not parsed.netloc:
        return url

    # Check if host matches request host or is in ALLOWED_HOSTS
    from django.conf import settings as django_settings

    allowed_hosts = getattr(django_settings, 'ALLOWED_HOSTS', [])
    request_host = request.get_host().split(':')[0]  # Remove port if present

    # SECURITY: If ALLOWED_HOSTS contains wildcard '*', reject absolute URL redirects
    # to prevent open redirect attacks (only allow relative URLs in this case)
    if '*' in allowed_hosts:
        logger.warning(
            "ALLOWED_HOSTS contains wildcard '*' - rejecting absolute URL redirect "
            f"to prevent open redirect vulnerability: {url}"
        )
        return None

    if parsed.netloc:
        netloc_host = parsed.netloc.split(':')[0]  # Remove port if present

        # Allow if matches request host
        if netloc_host == request_host:
            return url

        # Allow if in ALLOWED_HOSTS (excluding wildcards)
        if netloc_host in allowed_hosts and netloc_host != '*':
            return url

        # Allow subdomain wildcard match (e.g., '.example.com' matches 'sub.example.com')
        for allowed in allowed_hosts:
            if allowed.startswith('.') and netloc_host.endswith(allowed):
                return url

    # Reject external URLs
    logger.warning(f"Rejected redirect to external URL: {url}")
    return None


# get_client_ip is now imported from utils for centralized IP extraction


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

    Security:
        - Rate limited to 30 requests per minute per IP
        - Uses consistent error messages to prevent token enumeration
    """
    from django.core.cache import cache

    # Rate limiting - prevent brute force attacks
    client_ip = get_client_ip(request)
    rate_key = f"threeds_callback_rate_{client_ip}"
    request_count = cache.get(rate_key, 0)

    if request_count >= THREEDS_CALLBACK_RATE_LIMIT:
        logger.warning(f"3DS callback rate limit exceeded for IP {client_ip}")
        return _handle_3ds_error(
            request,
            "Too many requests. Please try again later.",
            error_code="RATE_LIMIT_EXCEEDED",
        )

    cache.set(rate_key, request_count + 1, THREEDS_CALLBACK_RATE_WINDOW)

    # Get token from either GET or POST
    token = request.GET.get("token") or request.POST.get("paymentId")

    # Use consistent error message to prevent token enumeration
    generic_error_message = "Payment processing failed. Please try again."

    if not token:
        logger.error("3DS callback received without token")
        return _handle_3ds_error(
            request,
            generic_error_message,
            error_code="PAYMENT_FAILED",
        )

    # Safe token logging - check length before accessing prefix
    token_log = f"token_prefix={token[:6]}***" if len(token) >= 6 else "token=<too_short>"
    logger.info(f"3DS callback received - {token_log}")

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

            # Trigger signal for failed payment (internal handlers get full details)
            threeds_failed.send(
                sender=None,
                conversation_id=response.conversation_id,
                error_code=response.error_code,
                error_message=response.error_message,
                request=request,
            )

            # Redirect to error page with generic message (prevents token enumeration)
            return _handle_3ds_error(
                request,
                generic_error_message,
                error_code="PAYMENT_FAILED",
                conversation_id=response.conversation_id,
            )

    except ThreeDSecureError as e:
        logger.error(f"3DS completion error: {str(e)}", exc_info=True)

        # Trigger signal for failed payment (internal handlers get full details)
        threeds_failed.send(
            sender=None,
            conversation_id=None,
            error_code=e.error_code,
            error_message=str(e),
            request=request,
        )

        # User gets generic message (prevents token enumeration)
        return _handle_3ds_error(
            request,
            generic_error_message,
            error_code="PAYMENT_FAILED",
        )

    except Exception as e:
        logger.error(f"Unexpected error in 3DS callback: {str(e)}", exc_info=True)

        # Trigger signal for failed payment (internal handlers get full details)
        threeds_failed.send(
            sender=None,
            conversation_id=None,
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
            request=request,
        )

        # User gets generic message (prevents token enumeration)
        return _handle_3ds_error(
            request,
            generic_error_message,
            error_code="PAYMENT_FAILED",
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
        - Rate limiting to prevent abuse
    """
    from django.core.cache import cache

    logger.info("Webhook received")

    # Get client IP
    client_ip = get_client_ip(request)
    logger.debug(f"Webhook from IP: {client_ip}")

    # Rate limiting - prevent abuse
    rate_key = f"webhook_rate_{client_ip}"
    request_count = cache.get(rate_key, 0)

    if request_count >= WEBHOOK_RATE_LIMIT:
        logger.warning(f"Webhook rate limit exceeded for IP {client_ip}")
        # Return 200 to prevent webhook retry storms from payment provider
        # Error is indicated in the response body for logging/debugging
        return JsonResponse(
            {"status": "error", "message": "Rate limit exceeded"},
            status=200,
        )

    cache.set(rate_key, request_count + 1, WEBHOOK_RATE_WINDOW)

    # Verify IP whitelist and webhook secret
    allowed_ips = iyzico_settings.webhook_allowed_ips
    webhook_secret = iyzico_settings.webhook_secret

    from django.conf import settings as django_settings
    is_debug = getattr(django_settings, 'DEBUG', False)

    # SECURITY: In production, require BOTH IP whitelist AND webhook secret
    if not is_debug:
        security_issues = []
        if not allowed_ips:
            security_issues.append("IYZICO_WEBHOOK_ALLOWED_IPS not configured")
        if not webhook_secret:
            security_issues.append("IYZICO_WEBHOOK_SECRET not configured")

        if security_issues:
            logger.error(
                f"SECURITY ERROR: Webhook security not properly configured! "
                f"Issues: {', '.join(security_issues)}. "
                f"Both IP whitelist AND webhook secret are required in production. "
                f"Rejecting webhook to prevent unauthorized access."
            )
            return JsonResponse(
                {"status": "error", "message": "Webhook security not configured"},
                status=403,
            )
    else:
        # Debug mode warnings
        if not allowed_ips:
            logger.warning(
                "Webhook IP whitelist not configured. Allowing all IPs in DEBUG mode. "
                "Configure IYZICO_WEBHOOK_ALLOWED_IPS for production."
            )
        if not webhook_secret:
            logger.warning(
                "Webhook secret not configured. Skipping signature validation in DEBUG mode. "
                "Configure IYZICO_WEBHOOK_SECRET for production."
            )

    # Verify IP whitelist (if configured)
    if allowed_ips and not is_ip_allowed(client_ip, allowed_ips):
        logger.warning(f"Webhook rejected - IP {client_ip} not in whitelist")
        return JsonResponse(
            {"status": "error", "message": "IP not allowed"},
            status=403,
        )

    # Verify webhook signature (if configured)
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

    # Try to get success URL from various sources, with validation
    session_url = _validate_redirect_url(request.session.get("iyzico_success_url"), request)
    settings_url = _validate_redirect_url(getattr(settings, "IYZICO_SUCCESS_URL", None), request)

    success_url = (
        session_url
        or settings_url
        or "/payment/success/"
    )

    # Clean up session - remove URL redirects and previous payment data (consistent with error handler)
    payment_session_keys = [
        'iyzico_success_url',
        'iyzico_error_url',
        'last_payment_id',
        'last_payment_status',
        'last_payment_error',
        'last_payment_error_code',
        'last_payment_conversation_id',
    ]
    for key in payment_session_keys:
        request.session.pop(key, None)

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

    # Try to get error URL from various sources, with validation
    session_url = _validate_redirect_url(request.session.get("iyzico_error_url"), request)
    settings_url = _validate_redirect_url(getattr(settings, "IYZICO_ERROR_URL", None), request)

    error_url = (
        session_url
        or settings_url
        or "/payment/error/"
    )

    # Clean up session - remove URL redirects and previous payment data
    payment_session_keys = [
        'iyzico_success_url',
        'iyzico_error_url',
        'last_payment_id',
        'last_payment_status',
        'last_payment_error',
        'last_payment_error_code',
        'last_payment_conversation_id',
    ]
    for key in payment_session_keys:
        request.session.pop(key, None)

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
