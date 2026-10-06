# openedx-course-payments

Django plugin for the Open edX LMS: learners buy courses one by one (Stripe, MXN)
and get lifetime access. A paid order enrolls the learner in the course's
`verified` mode.

## How a purchase works

1. The frontend calls `POST /payments/api/v1/checkout/` → a `pending` Order and a
   Stripe Checkout Session are created; the learner is redirected to Stripe.
2. Stripe calls `POST /payments/webhook/stripe/`:
   - `checkout.session.completed` (card, paid) → Order `paid`, learner enrolled as `verified`.
   - OXXO: `completed` arrives unpaid; access is granted on `checkout.session.async_payment_succeeded`.
   - `checkout.session.expired` / `async_payment_failed` → Order `failed`.
   - `charge.refunded` (full refund) → Order `refunded`, learner back to `audit`
     (or unenrolled if the course has no audit mode).
3. Webhooks are verified with the signing secret and deduplicated by event id
   (`PaymentEvent`), so retries are safe.

## Endpoints (LMS)

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/payments/api/v1/courses/{course_id}/` | optional | Price (from the `verified` course mode) and whether the user owns the course |
| POST | `/payments/api/v1/checkout/` | required | `{"course_id": ...}` → `{"order_id", "checkout_url"}` |
| GET | `/payments/api/v1/orders/` | required | The current user's orders |
| POST | `/payments/webhook/stripe/` | Stripe signature | Stripe events |

Prices are set per course in Django admin: *Course modes → verified → min price*.

## Local development (Tutor)

The directory name must start with `openedx-` so Tutor installs it automatically.

```bash
tutor mounts add /path/to/openedx-course-payments
tutor dev stop                   # with 8 GB of RAM webpack runs out of memory otherwise
tutor images build openedx-dev   # rebuild whenever pyproject.toml dependencies change
tutor dev start -d
tutor dev exec lms ./manage.py lms migrate course_payments
```

Settings are injected by the single-file Tutor plugin in `tutor/coursepayments.py`:

```bash
ln -s "$PWD/tutor/coursepayments.py" "$(tutor plugins printroot)/coursepayments.py"
tutor plugins enable coursepayments
tutor config save --set COURSE_PAYMENTS_STRIPE_SECRET_KEY=sk_test_... \
                  --set COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET=whsec_...
tutor dev restart lms
```

Forward Stripe test webhooks to the local LMS:

```bash
stripe listen --api-key "$STRIPE_SECRET_KEY" \
  --forward-to http://local.openedx.io:8000/payments/webhook/stripe/
```

Keep `STRIPE_SECRET_KEY=sk_test_...` in `.env` (gitignored), never in the repo.

## Tests

```bash
tutor dev exec lms bash -c "cd /openedx/edx-platform && pytest -c setup.cfg --rootdir=. --ds=lms.envs.tutor.test -p no:cacheprovider /mnt/openedx-course-payments/course_payments/tests"
```

## Settings

| Setting | Default |
|---|---|
| `COURSE_PAYMENTS_STRIPE_SECRET_KEY` | `""` |
| `COURSE_PAYMENTS_STRIPE_WEBHOOK_SECRET` | `""` |
| `COURSE_PAYMENTS_SUCCESS_URL` | learning MFE course home (`{course_id}` is replaced) |
| `COURSE_PAYMENTS_CANCEL_URL` | LMS course about page |
