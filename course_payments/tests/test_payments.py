"""
Run inside the LMS container (see README):
    pytest /mnt/openedx-course-payments/course_payments/tests
"""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import TEST_PASSWORD, UserFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory

from course_payments.models import Order, PaymentEvent

WEBHOOK_SECRET = "whsec_test"


def signed_post(client, event):
    payload = json.dumps(event)
    timestamp = int(time.time())
    signature = hmac.new(WEBHOOK_SECRET.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        reverse("course_payments:stripe-webhook"),
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
    )


def session_event(event_id, event_type, order, payment_status="paid"):
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": {
            "id": order.stripe_checkout_session_id,
            "object": "checkout.session",
            "client_reference_id": str(order.pk),
            "metadata": {"order_id": str(order.pk)},
            "payment_status": payment_status,
            "payment_intent": "pi_123",
        }},
    }


@override_settings(COURSE_PAYMENTS_STRIPE_SECRET_KEY="sk_test_x", COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class PaymentsTestCase(TestCase):
    def setUp(self):
        self.course = CourseOverviewFactory()
        self.course_id = str(self.course.id)
        CourseModeFactory(course_id=self.course.id, mode_slug="audit", min_price=0)
        CourseModeFactory(course_id=self.course.id, mode_slug="verified", min_price=499, currency="mxn")
        self.user = UserFactory()
        self.client = APIClient()

    def make_order(self, **kwargs):
        defaults = dict(user=self.user, course_key=self.course.id, amount=499, currency="mxn",
                        stripe_checkout_session_id="cs_test_1")
        return Order.objects.create(**{**defaults, **kwargs})

    def mode(self):
        return CourseEnrollment.enrollment_mode_for_user(self.user, self.course.id)

    # --- checkout ---------------------------------------------------------

    @mock.patch("stripe.checkout.Session.create", return_value=SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.test/1"))
    def test_checkout_creates_pending_order(self, create):
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("course_payments:checkout"), {"course_id": self.course_id}, format="json")

        assert response.status_code == 201, response.content
        assert response.json()["checkout_url"] == "https://checkout.stripe.test/1"
        order = Order.objects.get()
        assert order.status == Order.Status.PENDING
        assert order.stripe_checkout_session_id == "cs_test_1"
        price_data = create.call_args.kwargs["line_items"][0]["price_data"]
        assert price_data["unit_amount"] == 49900
        assert price_data["currency"] == "mxn"
        assert create.call_args.kwargs["metadata"]["order_id"] == str(order.pk)

    @mock.patch("stripe.checkout.Session.create")
    def test_checkout_rejects_owned_course(self, create):
        CourseEnrollment.enroll(self.user, self.course.id, mode="verified")
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("course_payments:checkout"), {"course_id": self.course_id}, format="json")

        assert response.status_code == 409
        assert response.json()["code"] == "already_owned"
        create.assert_not_called()

    @mock.patch("stripe.checkout.Session.create")
    @mock.patch("stripe.checkout.Session.retrieve", return_value=SimpleNamespace(status="open", url="https://checkout.stripe.test/open"))
    def test_checkout_reuses_open_session(self, retrieve, create):
        order = self.make_order()
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("course_payments:checkout"), {"course_id": self.course_id}, format="json")

        assert response.status_code == 201
        assert response.json() == {"order_id": order.pk, "checkout_url": "https://checkout.stripe.test/open"}
        retrieve.assert_called_once()
        create.assert_not_called()
        assert Order.objects.count() == 1

    @mock.patch("stripe.checkout.Session.create", return_value=SimpleNamespace(id="cs_test_2", url="https://checkout.stripe.test/2"))
    @mock.patch("stripe.checkout.Session.retrieve", return_value=SimpleNamespace(status="expired", url=None))
    def test_checkout_ignores_expired_session(self, retrieve, create):
        self.make_order()
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("course_payments:checkout"), {"course_id": self.course_id}, format="json")

        assert response.json()["checkout_url"] == "https://checkout.stripe.test/2"
        assert Order.objects.count() == 2

    def test_checkout_requires_login(self):
        response = self.client.post(reverse("course_payments:checkout"), {"course_id": self.course_id}, format="json")
        assert response.status_code == 401

    # --- buy link (public site's "Comprar" button) -------------------------

    def buy_url(self):
        return reverse("course_payments:buy", kwargs={"course_id": self.course_id})

    def test_buy_sends_anonymous_users_to_login(self):
        response = self.client.get(self.buy_url())
        assert response.status_code == 302
        assert "login" in response["Location"]
        assert "next=" in response["Location"]

    @mock.patch("stripe.checkout.Session.create", return_value=SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.test/1"))
    def test_buy_redirects_to_stripe(self, create):
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        response = self.client.get(self.buy_url())
        assert response.status_code == 302
        assert response["Location"] == "https://checkout.stripe.test/1"

    @mock.patch("stripe.checkout.Session.create")
    def test_buy_owned_course_goes_to_course(self, create):
        CourseEnrollment.enroll(self.user, self.course.id, mode="verified")
        self.client.login(username=self.user.username, password=TEST_PASSWORD)
        response = self.client.get(self.buy_url())
        assert response.status_code == 302
        assert response["Location"].endswith(f"/course/{self.course_id}/home")
        create.assert_not_called()

    # --- webhook ----------------------------------------------------------

    def test_webhook_rejects_bad_signature(self):
        response = self.client.post(
            reverse("course_payments:stripe-webhook"), data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
        )
        assert response.status_code == 400
        assert not PaymentEvent.objects.exists()

    def test_card_payment_enrolls_as_verified(self):
        order = self.make_order()
        response = signed_post(self.client, session_event("evt_1", "checkout.session.completed", order))

        assert response.status_code == 200
        order.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert order.paid_at is not None
        assert order.stripe_payment_intent_id == "pi_123"
        assert self.mode() == ("verified", True)

    def test_duplicate_event_is_processed_once(self):
        order = self.make_order()
        event = session_event("evt_1", "checkout.session.completed", order)
        signed_post(self.client, event)
        with mock.patch("course_payments.services.CourseEnrollment.enroll") as enroll:
            response = signed_post(self.client, event)

        assert response.status_code == 200
        enroll.assert_not_called()
        assert PaymentEvent.objects.count() == 1

    def test_oxxo_waits_for_async_payment(self):
        order = self.make_order()
        signed_post(self.client, session_event("evt_1", "checkout.session.completed", order, payment_status="unpaid"))
        order.refresh_from_db()
        assert order.status == Order.Status.PENDING
        assert self.mode() == (None, None)

        signed_post(self.client, session_event("evt_2", "checkout.session.async_payment_succeeded", order))
        order.refresh_from_db()
        assert order.status == Order.Status.PAID
        assert self.mode() == ("verified", True)

    @mock.patch("stripe.Refund.create")
    def test_second_payment_for_same_course_is_refunded(self, refund_create):
        first = self.make_order()
        signed_post(self.client, session_event("evt_1", "checkout.session.completed", first))
        second = self.make_order(stripe_checkout_session_id="cs_test_2")
        event = session_event("evt_2", "checkout.session.completed", second)
        event["data"]["object"]["payment_intent"] = "pi_456"
        response = signed_post(self.client, event)

        assert response.status_code == 200
        refund_create.assert_called_once()
        assert refund_create.call_args.kwargs["payment_intent"] == "pi_456"
        second.refresh_from_db()
        assert second.status == Order.Status.REFUNDED
        first.refresh_from_db()
        assert first.status == Order.Status.PAID
        assert self.mode() == ("verified", True)

    def test_expired_session_fails_order(self):
        order = self.make_order()
        signed_post(self.client, session_event("evt_1", "checkout.session.expired", order, payment_status="unpaid"))
        order.refresh_from_db()
        assert order.status == Order.Status.FAILED

    def test_full_refund_unenrolls_even_with_audit_mode(self):
        order = self.make_order()
        signed_post(self.client, session_event("evt_1", "checkout.session.completed", order))
        refund = {"id": "evt_2", "type": "charge.refunded", "data": {"object": {
            "id": "ch_1", "object": "charge", "payment_intent": "pi_123", "refunded": True,
        }}}
        signed_post(self.client, refund)

        order.refresh_from_db()
        assert order.status == Order.Status.REFUNDED
        assert self.mode() == ("verified", False)

    def test_full_refund_without_audit_mode_unenrolls(self):
        CourseMode.objects.filter(course_id=self.course.id, mode_slug="audit").delete()
        order = self.make_order()
        signed_post(self.client, session_event("evt_1", "checkout.session.completed", order))
        refund = {"id": "evt_2", "type": "charge.refunded", "data": {"object": {
            "id": "ch_1", "object": "charge", "payment_intent": "pi_123", "refunded": True,
        }}}
        signed_post(self.client, refund)

        assert self.mode() == ("verified", False)
