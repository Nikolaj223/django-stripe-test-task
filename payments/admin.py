from django.contrib import admin

from .models import Discount, Item, Order, OrderItem, Tax
from .pricing import calculate_order_totals


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "currency", "updated_at")
    list_filter = ("currency",)
    search_fields = ("name", "description")


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ("name", "percent_off", "amount_off", "currency", "active")
    list_filter = ("active", "currency")
    search_fields = ("name",)
    readonly_fields = ("stripe_coupon_ids",)


@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ("display_name", "percentage", "inclusive", "active")
    list_filter = ("active", "inclusive")
    search_fields = ("display_name",)
    readonly_fields = ("stripe_tax_rate_ids",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ("item",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("title", "currency", "subtotal", "discount", "total", "updated_at")
    list_filter = ("currency", "taxes")
    search_fields = ("title",)
    inlines = (OrderItemInline,)
    filter_horizontal = ("taxes",)

    @admin.display(description="Subtotal")
    def subtotal(self, obj: Order):
        return calculate_order_totals(obj).subtotal

    @admin.display(description="Total")
    def total(self, obj: Order):
        return calculate_order_totals(obj).total
