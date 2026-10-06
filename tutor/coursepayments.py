"""
Tutor plugin: injects the course_payments settings into the LMS.

Install (single-file plugin):
    ln -s "$PWD/tutor/coursepayments.py" "$(tutor plugins printroot)/coursepayments.py"
    tutor plugins enable coursepayments
    tutor config save --set COURSE_PAYMENTS_STRIPE_SECRET_KEY=sk_test_... \
                      --set COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET=whsec_...
"""
from tutor import hooks

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("COURSE_PAYMENTS_STRIPE_SECRET_KEY", ""),
        ("COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET", ""),
    ]
)

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
COURSE_PAYMENTS_STRIPE_SECRET_KEY = "{{ COURSE_PAYMENTS_STRIPE_SECRET_KEY }}"
COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET = "{{ COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET }}"
""",
    )
)
