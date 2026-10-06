from django.conf import settings
from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField


class Order(TimeStampedModel):
    """
    One attempt by a user to buy one course.

    A course can have several failed/pending orders for the same user, but at
    most one ``paid`` order (enforced by a DB constraint).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="course_orders")
    course_key = CourseKeyField(max_length=255, db_index=True)
    # Price is copied at purchase time so later price changes don't rewrite history.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    stripe_checkout_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # True only while status is PAID, NULL otherwise. MySQL ignores conditional
    # unique constraints but allows repeated NULLs in a unique index, so this
    # enforces "at most one paid order per user and course".
    paid_lock = models.BooleanField(null=True, editable=False)

    class Meta:
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course_key", "paid_lock"],
                name="course_payments_one_paid_order_per_course",
            ),
        ]

    def save(self, *args, **kwargs):
        self.paid_lock = True if self.status == self.Status.PAID else None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "status" in update_fields:
            kwargs["update_fields"] = {*update_fields, "paid_lock"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.pk} {self.user} {self.course_key} [{self.status}]"


class PaymentEvent(TimeStampedModel):
    """
    Raw Stripe webhook event. The unique ``stripe_event_id`` lets us ignore
    duplicate deliveries, and the payload is kept for auditing.
    """

    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.event_type} {self.stripe_event_id}"
