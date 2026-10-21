from django.apps import AppConfig


class CoursePaymentsConfig(AppConfig):
    name = "course_payments"
    verbose_name = "Course payments"
    default_auto_field = "django.db.models.BigAutoField"

    # Registered through the "lms.djangoapp" entry point (see pyproject.toml).
    # edx-platform reads this dict to load our settings in the LMS.
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
            },
        },
    }
