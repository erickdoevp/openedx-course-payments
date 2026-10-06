from django.conf import settings
from django.urls import path, re_path

from .api.views import CheckoutView, CourseProductView, MyOrdersView
from .views import buy
from .webhooks import stripe_webhook

# Mounted under /payments/ by the plugin config in apps.py.
urlpatterns = [
    re_path(rf"^buy/{settings.COURSE_ID_PATTERN}/$", buy, name="buy"),
    re_path(
        rf"^api/v1/courses/{settings.COURSE_ID_PATTERN}/$",
        CourseProductView.as_view(),
        name="course-product",
    ),
    path("api/v1/checkout/", CheckoutView.as_view(), name="checkout"),
    path("api/v1/orders/", MyOrdersView.as_view(), name="my-orders"),
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
]
