"""
Tutor plugin: injects the course_payments settings into the LMS.

Install (single-file plugin):
    ln -s "$PWD/tutor/coursepayments.py" "$(tutor plugins printroot)/coursepayments.py"
    tutor plugins enable coursepayments
    tutor config save --set COURSE_PAYMENTS_STRIPE_SECRET_KEY=sk_test_... \
                      --set COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET=whsec_... \
                      --set COURSE_PAYMENTS_PUBLIC_SITE_URL=http://www.local.openedx.io:3000
"""
from tutor import hooks

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("COURSE_PAYMENTS_STRIPE_SECRET_KEY", ""),
        ("COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET", ""),
        # Public (Nuxt) site; course "About" pages redirect there.
        ("COURSE_PAYMENTS_PUBLIC_SITE_URL", ""),
    ]
)

hooks.Filters.ENV_PATCHES.add_item(
    (
        "openedx-lms-common-settings",
        """
COURSE_PAYMENTS_STRIPE_SECRET_KEY = "{{ COURSE_PAYMENTS_STRIPE_SECRET_KEY }}"
COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET = "{{ COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET }}"
COURSE_PAYMENTS_PUBLIC_SITE_URL = "{{ COURSE_PAYMENTS_PUBLIC_SITE_URL }}"
""",
    )
)

# Let login/logout send users back to the public site ("?next=" / "?redirect_url=").
# Development settings reassign LOGIN_REDIRECT_WHITELIST, so append at the end.
_REDIRECT_WHITELIST = """
{% if COURSE_PAYMENTS_PUBLIC_SITE_URL %}
LOGIN_REDIRECT_WHITELIST.append("{{ COURSE_PAYMENTS_PUBLIC_SITE_URL.split('://')[-1].rstrip('/') }}")
{% endif %}
"""
hooks.Filters.ENV_PATCHES.add_items(
    [
        ("openedx-lms-development-settings", _REDIRECT_WHITELIST),
        ("openedx-lms-production-settings", _REDIRECT_WHITELIST),
    ]
)
