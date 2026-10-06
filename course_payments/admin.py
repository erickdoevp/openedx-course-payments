from django.contrib import admin

from .models import Order, PaymentEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "course_key", "amount", "currency", "status", "created", "paid_at")
    list_filter = ("status", "currency")
    search_fields = ("user__username", "user__email", "course_key", "stripe_checkout_session_id")
    raw_id_fields = ("user",)
    readonly_fields = ("created", "modified")


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "order", "created", "processed_at")
    list_filter = ("event_type",)
    search_fields = ("stripe_event_id",)
    raw_id_fields = ("order",)
    readonly_fields = ("created", "modified")
