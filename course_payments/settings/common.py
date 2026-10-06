def plugin_settings(settings):
    """
    Defaults for the plugin. Real values (Stripe keys) are injected per
    environment by the Tutor plugin, never committed to the repo.
    """
    settings.COURSE_PAYMENTS_STRIPE_SECRET_KEY = getattr(settings, "COURSE_PAYMENTS_STRIPE_SECRET_KEY", "")
    settings.COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET = getattr(settings, "COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET", "")
    # Where Stripe sends the learner back; "{course_id}" is replaced. When empty,
    # services.py builds them from LEARNING_MICROFRONTEND_URL / LMS_ROOT_URL,
    # which aren't final yet when this runs.
    settings.COURSE_PAYMENTS_SUCCESS_URL = getattr(settings, "COURSE_PAYMENTS_SUCCESS_URL", "")
    settings.COURSE_PAYMENTS_CANCEL_URL = getattr(settings, "COURSE_PAYMENTS_CANCEL_URL", "")
