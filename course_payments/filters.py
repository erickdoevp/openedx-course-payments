"""
Open edX Filters pipeline steps that send course "About" pages to the public
site, which is where courses are presented and sold. They are no-ops while
COURSE_PAYMENTS_PUBLIC_SITE_URL is empty.
"""
import re
from urllib.parse import quote

from django.conf import settings
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseAboutRenderStarted

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
