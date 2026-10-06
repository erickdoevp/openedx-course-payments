from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions, serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .. import services
from ..models import Order

AUTHENTICATION_CLASSES = (JwtAuthentication, SessionAuthenticationAllowInactiveUser)


class CourseProductView(APIView):
    """
    GET /payments/api/v1/courses/{course_id}/

    Public: price of a course and, for a logged-in user, whether they already own it.
    The price is the ``verified`` course mode's ``min_price`` (set in Django admin).
    """

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (permissions.AllowAny,)

    def get(self, request, course_id):
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response({"detail": "Invalid course id."}, status=400)
        if not CourseOverview.objects.filter(id=course_key).exists():
            return Response({"detail": "Course not found."}, status=404)

        verified = services.get_verified_mode(course_key)
        data = {
            "course_id": str(course_key),
            "purchasable": verified is not None and verified.min_price > 0,
            "price": verified.min_price if verified else None,
            "currency": verified.currency if verified else None,
            "owned": None,
        }
        if request.user.is_authenticated:
            data["owned"] = services.user_owns_course(request.user, course_key)
        return Response(data)


class CheckoutView(APIView):
    """
    POST /payments/api/v1/checkout/  {"course_id": "course-v1:..."}

    Starts a purchase and returns the Stripe Checkout URL to redirect the user to.
    Access is granted later, by the webhook, once Stripe confirms the payment.
    """

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            course_key = CourseKey.from_string(request.data.get("course_id", ""))
        except InvalidKeyError:
            return Response({"code": "invalid_course_id", "detail": "Invalid course id."}, status=400)
        try:
            order, checkout_url = services.create_checkout(request.user, course_key)
        except services.PurchaseError as exc:
            return Response({"code": exc.code, "detail": str(exc)}, status=exc.status)
        return Response({"order_id": order.pk, "checkout_url": checkout_url}, status=201)


class OrderSerializer(serializers.ModelSerializer):
    course_key = serializers.CharField()

    class Meta:
        model = Order
        fields = ("id", "course_key", "amount", "currency", "status", "created", "paid_at")


class MyOrdersView(ListAPIView):
    """
    GET /payments/api/v1/orders/

    The authenticated user's orders, newest first.
    """

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
