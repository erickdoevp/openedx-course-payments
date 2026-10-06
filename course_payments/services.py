"""
Business logic: create Stripe checkouts and turn Stripe events into enrollments.

Every function that reacts to Stripe is idempotent: Stripe retries webhooks and
can deliver the same event more than once.
"""
import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .filters import public_course_url
from .models import Order

log = logging.getLogger(__name__)


class PurchaseError(Exception):
    """A checkout can't be started; ``code`` is safe to show to API clients."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def get_verified_mode(course_key):
    return CourseMode.objects.filter(course_id=course_key, mode_slug=CourseMode.VERIFIED).first()


def user_owns_course(user, course_key):
    mode, is_active = CourseEnrollment.enrollment_mode_for_user(user, course_key)
    return bool(is_active and mode == CourseMode.VERIFIED)


def _success_url(course_id):
    template = settings.COURSE_PAYMENTS_SUCCESS_URL or (
        settings.LEARNING_MICROFRONTEND_URL + "/course/{course_id}/home?payment=success"
    )
    return template.format(course_id=course_id)


def _cancel_url(course_id):
    if settings.COURSE_PAYMENTS_CANCEL_URL:
        return settings.COURSE_PAYMENTS_CANCEL_URL.format(course_id=course_id)
    about_url = public_course_url(course_id) or f"{settings.LMS_ROOT_URL}/courses/{course_id}/about"
    return f"{about_url}?payment=cancelled"


def _open_checkout(user, course_key, amount):
    """
    Return ``(order, url)`` for the user's latest Stripe session for this course
    if it can still be paid, so two tabs/clicks don't create two payable checkouts.
    """
    order = Order.objects.filter(
        user=user, course_key=course_key, status=Order.Status.PENDING, amount=amount,
        stripe_checkout_session_id__isnull=False,
    ).first()  # newest first (Meta.ordering)
    if order is None:
        return None
    session = stripe.checkout.Session.retrieve(
        order.stripe_checkout_session_id, api_key=settings.COURSE_PAYMENTS_STRIPE_SECRET_KEY
    )
    if session.status != "open":
        return None
    return order, session.url


def create_checkout(user, course_key):
    """
    Create a pending Order and its Stripe Checkout Session.
    Returns ``(order, checkout_url)``.
    """
    course = CourseOverview.objects.filter(id=course_key).first()
    if course is None:
        raise PurchaseError("course_not_found", "Course not found.", status=404)
    verified = get_verified_mode(course_key)
    if verified is None or verified.min_price <= 0:
        raise PurchaseError("not_purchasable", "This course is not for sale.")
    if user_owns_course(user, course_key):
        raise PurchaseError("already_owned", "You already own this course.", status=409)

    reusable = _open_checkout(user, course_key, Decimal(verified.min_price))
    if reusable is not None:
        return reusable

    order = Order.objects.create(
        user=user,
        course_key=course_key,
        amount=Decimal(verified.min_price),
        currency=verified.currency.lower(),
    )
    course_id = str(course_key)
    session = stripe.checkout.Session.create(
        api_key=settings.COURSE_PAYMENTS_STRIPE_SECRET_KEY,
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": order.currency,
                # Stripe expects the smallest currency unit (centavos).
                "unit_amount": int(order.amount * 100),
                "product_data": {"name": course.display_name or course_id},
            },
        }],
        customer_email=user.email,
        client_reference_id=str(order.pk),
        metadata={"order_id": str(order.pk), "course_id": course_id},
        payment_intent_data={"metadata": {"order_id": str(order.pk), "course_id": course_id}},
        success_url=_success_url(course_id),
        cancel_url=_cancel_url(course_id),
        # Payment methods (card, OXXO...) are chosen in the Stripe Dashboard.
        idempotency_key=f"course-payments-order-{order.pk}",
    )
    order.stripe_checkout_session_id = session.id
    order.save(update_fields=["stripe_checkout_session_id", "modified"])
    return order, session.url


def _order_from_session(session):
    order_id = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")
    if not order_id:
        return None
    return Order.objects.select_for_update().filter(pk=order_id).first()


@transaction.atomic
def fulfill_checkout_session(session):
    """
    Mark the order as paid and enroll the user in ``verified`` mode.
    Called for ``checkout.session.completed`` (cards) and
    ``checkout.session.async_payment_succeeded`` (OXXO, paid days later).
    """
    order = _order_from_session(session)
    if order is None:
        log.warning("Stripe session %s has no matching order", session.get("id"))
        return None
    if session.get("payment_status") != "paid":
        # e.g. OXXO voucher created but not paid yet: wait for async_payment_succeeded.
        log.info("Order %s: session %s not paid yet (%s)", order.pk, session.get("id"), session.get("payment_status"))
        return order
    if order.status == Order.Status.PAID:
        return order

    payment_intent = session.get("payment_intent") or ""
    already_paid = Order.objects.filter(
        user=order.user, course_key=order.course_key, status=Order.Status.PAID
    ).exclude(pk=order.pk).exists()
    if already_paid:
        # Paid twice for the same course (e.g. two checkouts in two tabs, or an
        # OXXO voucher paid after a card). Give the money back automatically.
        stripe.Refund.create(
            api_key=settings.COURSE_PAYMENTS_STRIPE_SECRET_KEY,
            payment_intent=payment_intent,
            idempotency_key=f"course-payments-duplicate-{order.pk}",
        )
        order.status = Order.Status.REFUNDED
        order.stripe_payment_intent_id = payment_intent
        order.save(update_fields=["status", "stripe_payment_intent_id", "modified"])
        log.warning("Order %s: duplicate payment for %s by %s refunded", order.pk, order.course_key, order.user.username)
        return order

    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.stripe_payment_intent_id = payment_intent
    order.save(update_fields=["status", "paid_at", "stripe_payment_intent_id", "modified"])
    CourseEnrollment.enroll(order.user, order.course_key, mode=CourseMode.VERIFIED)
    log.info("Order %s paid: %s enrolled in %s as verified", order.pk, order.user.username, order.course_key)
    return order


@transaction.atomic
def fail_checkout_session(session):
    """The checkout expired or the async payment (OXXO) failed."""
    order = _order_from_session(session)
    if order is None or order.status != Order.Status.PENDING:
        return order
    order.status = Order.Status.FAILED
    order.save(update_fields=["status", "modified"])
    return order


@transaction.atomic
def refund_charge(charge):
    """
    A full refund removes the paid access: the learner goes back to ``audit``
    if the course offers it, otherwise the enrollment is deactivated.
    """
    if not charge.get("refunded"):  # partial refund: keep access
        return None
    order = Order.objects.select_for_update().filter(
        stripe_payment_intent_id=charge.get("payment_intent"), status=Order.Status.PAID
    ).first()
    if order is None:
        return None
    order.status = Order.Status.REFUNDED
    order.save(update_fields=["status", "modified"])

    enrollment = CourseEnrollment.get_enrollment(order.user, order.course_key)
    if enrollment is not None:
        if CourseMode.objects.filter(course_id=order.course_key, mode_slug=CourseMode.AUDIT).exists():
            enrollment.update_enrollment(mode=CourseMode.AUDIT)
        else:
            enrollment.update_enrollment(is_active=False)
    log.info("Order %s refunded: access to %s removed for %s", order.pk, order.course_key, order.user.username)
    return order
