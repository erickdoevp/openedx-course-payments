FILTER_STEPS = {
    "org.openedx.learning.course_about.render.started.v1": "course_payments.filters.RedirectCourseAboutToPublicSite",
    "org.openedx.learning.course_about.page.url.requested.v1": "course_payments.filters.PublicSiteCourseAboutURL",
    "org.openedx.learning.course.enrollment.started.v1": "course_payments.filters.RequirePaidEnrollment",
}
# Access guards must fail closed: with fail_silently a broken step would be
# skipped and every enrollment would go through.
FAIL_CLOSED = {"org.openedx.learning.course.enrollment.started.v1"}


def plugin_settings(settings):
    """
    Defaults for the plugin. The real site URL is injected per environment by
    the Tutor plugin.
    """
    # Public site (Nuxt) where courses are presented, e.g. https://www.example.com.
    # When set, LMS course "About" pages redirect there.
    settings.COURSE_PAYMENTS_PUBLIC_SITE_URL = getattr(settings, "COURSE_PAYMENTS_PUBLIC_SITE_URL", "")
    # Only paid (verified) enrollments, which the Campus CMS creates after a
    # payment, plus staff and course teams. Turn off only to allow free
    # enrollments again.
    settings.COURSE_PAYMENTS_REQUIRE_PAID_ENROLLMENT = getattr(settings, "COURSE_PAYMENTS_REQUIRE_PAID_ENROLLMENT", True)

    # Append our steps to any pipeline already configured for these filters.
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {})
    for filter_type, step in FILTER_STEPS.items():
        config = filters_config.setdefault(filter_type, {"fail_silently": True, "pipeline": []})
        if step not in config.setdefault("pipeline", []):
            config["pipeline"].append(step)
        if filter_type in FAIL_CLOSED:
            config["fail_silently"] = False
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
