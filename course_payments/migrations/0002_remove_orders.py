# Payments moved to the Campus CMS: it keeps the orders now.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("course_payments", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="PaymentEvent"),
        migrations.DeleteModel(name="Order"),
    ]
