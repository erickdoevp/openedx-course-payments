"""
Stripe webhook endpoint: POST /payments/webhook/stripe/
"""
import json
import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services
from .models import PaymentEvent

log = logging.getLogger(__name__)

HANDLERS = {
    "checkout.session.completed": services.fulfill_checkout_session,
    "checkout.session.async_payment_succeeded": services.fulfill_checkout_session,
    "checkout.session.async_payment_failed": services.fail_checkout_session,
    "checkout.session.expired": services.fail_checkout_session,
    "charge.refunded": services.refund_charge,
}


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body.decode("utf-8")
    try:
        stripe.WebhookSignature.verify_header(
            payload,
            request.headers.get("Stripe-Signature", ""),
            settings.COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET,
            tolerance=300,
        )
    except stripe.SignatureVerificationError:
        log.warning("Rejected Stripe webhook with an invalid signature")
        return HttpResponse(status=400)

    event = json.loads(payload)
    record, _ = PaymentEvent.objects.get_or_create(
        stripe_event_id=event["id"],
        defaults={"event_type": event["type"], "payload": event},
    )
    if record.processed_at is not None:
        return HttpResponse(status=200)  # duplicate delivery

    handler = HANDLERS.get(event["type"])
    if handler is not None:
        # An exception here returns 500, so Stripe retries the event later.
        record.order = handler(event["data"]["object"])
    record.processed_at = timezone.now()
    record.save(update_fields=["order", "processed_at", "modified"])
    return HttpResponse(status=200)
