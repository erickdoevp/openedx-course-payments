from types import SimpleNamespace

import pytest
from django.test import override_settings
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseAboutRenderStarted, CourseEnrollmentStarted

from common.djangoapps.student.models import CourseAccessRole, CourseEnrollment, EnrollmentNotAllowed
from common.djangoapps.student.tests.factories import UserFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory

from course_payments.filters import PublicSiteCourseAboutURL, RedirectCourseAboutToPublicSite, RequirePaidEnrollment
from course_payments.services import _cancel_url

COURSE_ID = "course-v1:OpenedX+DemoX+DemoCourse"
PUBLIC_URL = "https://www.example.com/cursos/course-v1%3AOpenedX%2BDemoX%2BDemoCourse"


def step(cls):
    return cls(filter_type="test", running_pipeline=[])


@override_settings(COURSE_PAYMENTS_PUBLIC_SITE_URL="https://www.example.com/")
def test_about_url_points_to_public_site():
    result = step(PublicSiteCourseAboutURL).run_filter(
        url=f"https://lms.example.com/courses/{COURSE_ID}/about", org="OpenedX"
    )
    assert result == {"url": PUBLIC_URL, "org": "OpenedX"}


@override_settings(COURSE_PAYMENTS_PUBLIC_SITE_URL="https://www.example.com")
def test_non_about_url_is_left_alone():
    url = "https://social.example.com/share/123"
    assert step(PublicSiteCourseAboutURL).run_filter(url=url, org="OpenedX")["url"] == url


@override_settings(COURSE_PAYMENTS_PUBLIC_SITE_URL="")
def test_filters_are_noops_without_public_site():
    url = f"https://lms.example.com/courses/{COURSE_ID}/about"
    assert step(PublicSiteCourseAboutURL).run_filter(url=url, org="OpenedX")["url"] == url
    context = {"course": SimpleNamespace(id=CourseKey.from_string(COURSE_ID))}
    result = step(RedirectCourseAboutToPublicSite).run_filter(context=context, template_name="about.html")
    assert result == {"context": context, "template_name": "about.html"}


@override_settings(COURSE_PAYMENTS_PUBLIC_SITE_URL="https://www.example.com")
def test_about_page_redirects_to_public_site():
    context = {"course": SimpleNamespace(id=CourseKey.from_string(COURSE_ID))}
    with pytest.raises(CourseAboutRenderStarted.RedirectToPage) as exc:
        step(RedirectCourseAboutToPublicSite).run_filter(context=context, template_name="about.html")
    assert exc.value.redirect_to == PUBLIC_URL


@override_settings(COURSE_PAYMENTS_PUBLIC_SITE_URL="https://www.example.com", COURSE_PAYMENTS_CANCEL_URL="")
def test_cancelled_checkout_returns_to_public_site():
    assert _cancel_url(COURSE_ID) == f"{PUBLIC_URL}?payment=cancelled"


# --- RequirePaidEnrollment ------------------------------------------------


def enroll_step(user, mode):
    return step(RequirePaidEnrollment).run_filter(user=user, course_key=CourseKey.from_string(COURSE_ID), mode=mode)


@pytest.mark.django_db
@pytest.mark.parametrize("mode", [None, "audit", "honor"])
def test_free_enrollment_is_blocked(mode):
    with pytest.raises(CourseEnrollmentStarted.PreventEnrollment):
        enroll_step(UserFactory(), mode)


@pytest.mark.django_db
def test_paid_enrollment_goes_through():
    user = UserFactory()
    assert enroll_step(user, "verified")["mode"] == "verified"


@pytest.mark.django_db
def test_staff_and_course_team_can_enroll_for_free():
    assert enroll_step(UserFactory(is_staff=True), None)["mode"] is None
    author = UserFactory()
    CourseAccessRole.objects.create(user=author, course_id=CourseKey.from_string(COURSE_ID), role="instructor")
    assert enroll_step(author, "audit")["mode"] == "audit"


@pytest.mark.django_db
@override_settings(COURSE_PAYMENTS_REQUIRE_PAID_ENROLLMENT=False)
def test_guard_can_be_turned_off():
    assert enroll_step(UserFactory(), "audit")["mode"] == "audit"


@pytest.mark.django_db
def test_enroll_runs_the_guard():
    """The step is wired into CourseEnrollment.enroll() by the plugin settings."""
    course = CourseOverviewFactory()
    user = UserFactory()
    with pytest.raises(EnrollmentNotAllowed):
        CourseEnrollment.enroll(user, course.id)
    CourseEnrollment.enroll(user, course.id, mode="verified")
    assert CourseEnrollment.enrollment_mode_for_user(user, course.id) == ("verified", True)
