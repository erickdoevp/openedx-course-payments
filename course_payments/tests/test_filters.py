from types import SimpleNamespace

import pytest
from django.test import override_settings
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseAboutRenderStarted

from course_payments.filters import PublicSiteCourseAboutURL, RedirectCourseAboutToPublicSite
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
