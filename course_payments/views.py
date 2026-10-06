"""
Browser-facing views (plain redirects, no JSON).
"""
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from . import services


@require_GET
def buy(request, course_id):
    """
    GET /payments/buy/{course_id}/

    Target of the public site's "Comprar" button: a plain link, so the site
    never deals with sessions, tokens or CSRF. Sends anonymous users through
    login, then redirects to Stripe Checkout (reusing an open one if any).
    """
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError:
        return HttpResponse("Invalid course id.", status=404)
    try:
        _order, checkout_url = services.create_checkout(request.user, course_key)
    except services.PurchaseError as exc:
        if exc.code == "already_owned":
            return redirect(f"{settings.LEARNING_MICROFRONTEND_URL}/course/{course_key}/home")
        return HttpResponse(str(exc), status=exc.status)
    return redirect(checkout_url)
