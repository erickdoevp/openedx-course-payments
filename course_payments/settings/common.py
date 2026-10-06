FILTER_STEPS = {
    "org.openedx.learning.course_about.render.started.v1": "course_payments.filters.RedirectCourseAboutToPublicSite",
    "org.openedx.learning.course_about.page.url.requested.v1": "course_payments.filters.PublicSiteCourseAboutURL",
}


def plugin_settings(settings):
    """
    Defaults for the plugin. Real values (Stripe keys, site URL) are injected
    per environment by the Tutor plugin, never committed to the repo.
    """
    settings.COURSE_PAYMENTS_STRIPE_SECRET_KEY = getattr(settings, "COURSE_PAYMENTS_STRIPE_SECRET_KEY", "")
    settings.COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET = getattr(settings, "COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET", "")
    # Public site (Nuxt) where courses are presented, e.g. https://www.example.com.
    # When set, LMS course "About" pages redirect there.
    settings.COURSE_PAYMENTS_PUBLIC_SITE_URL = getattr(settings, "COURSE_PAYMENTS_PUBLIC_SITE_URL", "")
    # Where Stripe sends the learner back; "{course_id}" is replaced. When empty,
    # services.py derives them from other settings, which aren't final yet when
    # this runs.
    settings.COURSE_PAYMENTS_SUCCESS_URL = getattr(settings, "COURSE_PAYMENTS_SUCCESS_URL", "")
    settings.COURSE_PAYMENTS_CANCEL_URL = getattr(settings, "COURSE_PAYMENTS_CANCEL_URL", "")

    # Append our steps to any pipeline already configured for these filters.
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {})
    for filter_type, step in FILTER_STEPS.items():
        config = filters_config.setdefault(filter_type, {"fail_silently": True, "pipeline": []})
        if step not in config.setdefault("pipeline", []):
            config["pipeline"].append(step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
