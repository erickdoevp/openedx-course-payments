from django.apps import AppConfig


class CoursePaymentsConfig(AppConfig):
    name = "course_payments"
    verbose_name = "Course payments"
    default_auto_field = "django.db.models.BigAutoField"

    # Registered through the "lms.djangoapp" and "cms.djangoapp" entry points
    # (see pyproject.toml). edx-platform reads this dict to mount our URLs and
    # settings. Studio only gets the course deletion endpoint (cms_urls).
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "course_payments",
                "regex": r"^payments/",
                "relative_path": "urls",
            },
            "cms.djangoapp": {
                "namespace": "course_payments",
                "regex": r"^campus/",
                "relative_path": "cms_urls",
            },
        },
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
            },
        },
    }
