"""
Open edX Filters pipeline steps.

- Course "About" pages go to the public site, which is where courses are
  presented and sold (no-ops while COURSE_PAYMENTS_PUBLIC_SITE_URL is empty).
- Enrollments are only for paying learners (see RequirePaidEnrollment).
"""
import re
from urllib.parse import quote

from django.conf import settings
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseAboutRenderStarted, CourseEnrollmentStarted

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseAccessRole

ABOUT_URL = re.compile(r"/courses/(?P<course_id>[^/]+)/about/?$")


def public_course_url(course_id):
    site = settings.COURSE_PAYMENTS_PUBLIC_SITE_URL.rstrip("/")
    if not site:
        return None
    return f"{site}/cursos/{quote(str(course_id), safe='')}"


class RedirectCourseAboutToPublicSite(PipelineStep):
    """org.openedx.learning.course_about.render.started.v1"""

    def run_filter(self, context, template_name):  # pylint: disable=arguments-differ
        course = context.get("course")
        url = public_course_url(course.id) if course is not None else None
        if url:
            raise CourseAboutRenderStarted.RedirectToPage("Course about lives on the public site.", redirect_to=url)
        return {"context": context, "template_name": template_name}


class PublicSiteCourseAboutURL(PipelineStep):
    """org.openedx.learning.course_about.page.url.requested.v1"""

    def run_filter(self, url, org):  # pylint: disable=arguments-differ
        match = ABOUT_URL.search(url or "")
        public_url = public_course_url(match["course_id"]) if match else None
        return {"url": public_url or url, "org": org}


class RequirePaidEnrollment(PipelineStep):
    """
    org.openedx.learning.course.enrollment.started.v1

    Blocks free enrollments: only ``verified`` enrollments go through, which
    are the ones created after a payment (learners can't request that mode
    themselves). Staff and the course team are let through so authors can
    preview their courses. Disabled with COURSE_PAYMENTS_REQUIRE_PAID_ENROLLMENT.
    """

    def run_filter(self, user, course_key, mode):  # pylint: disable=arguments-differ
        if (
            not settings.COURSE_PAYMENTS_REQUIRE_PAID_ENROLLMENT
            or mode == CourseMode.VERIFIED
            or user.is_staff
            or CourseAccessRole.objects.filter(user=user, course_id=course_key).exists()
        ):
            return {"user": user, "course_key": course_key, "mode": mode}
        raise CourseEnrollmentStarted.PreventEnrollment("Este curso solo está disponible comprándolo.")
