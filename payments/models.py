from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .constants import Currency


class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.USD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="item_price_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency.upper()} {self.price})"


class Discount(models.Model):
    name = models.CharField(max_length=255)
    percent_off = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    amount_off = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=Currency.choices, blank=True)
    active = models.BooleanField(default=True)
    stripe_coupon_ids = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(percent_off__isnull=False, amount_off__isnull=True, currency="")
                    | (
                        models.Q(percent_off__isnull=True, amount_off__isnull=False)
                        & ~models.Q(currency="")
                    )
                ),
                name="discount_exactly_one_value",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(percent_off__isnull=True) | models.Q(percent_off__gt=0, percent_off__lte=100))
                    & (models.Q(amount_off__isnull=True) | models.Q(amount_off__gt=0))
                ),
                name="discount_values_positive",
            ),
        ]

    def clean(self) -> None:
        has_percent = self.percent_off is not None
        has_amount = self.amount_off is not None
        if has_percent == has_amount:
            raise ValidationError("Set exactly one of percent_off or amount_off.")
        if has_amount and not self.currency:
            raise ValidationError({"currency": "Currency is required for fixed amount discounts."})
        if has_percent:
            self.currency = ""

    def __str__(self) -> str:
        if self.percent_off is not None:
            return f"{self.name}: {self.percent_off}%"
        return f"{self.name}: {self.currency.upper()} {self.amount_off}"


class Tax(models.Model):
    display_name = models.CharField(max_length=80)
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100"))],
    )
    inclusive = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    stripe_tax_rate_ids = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percentage__gt=0, percentage__lte=100),
                name="tax_percentage_range",
            ),
        ]

    def __str__(self) -> str:
        tax_type = "inclusive" if self.inclusive else "exclusive"
        return f"{self.display_name}: {self.percentage}% {tax_type}"


class Order(models.Model):
    title = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.USD)
    items = models.ManyToManyField(Item, through="OrderItem", related_name="orders")
    discount = models.ForeignKey(
        Discount,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    taxes = models.ManyToManyField(Tax, blank=True, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self) -> None:
        if self.discount and self.discount.amount_off is not None and self.discount.currency != self.currency:
            raise ValidationError({"discount": "Fixed amount discount currency must match order currency."})
        if self.pk:
            mismatched_items = self.order_items.exclude(item__currency=self.currency)
            if mismatched_items.exists():
                raise ValidationError("All order items must have the same currency as the order.")

    def __str__(self) -> str:
        return f"{self.title} ({self.currency.upper()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("order", "item"), name="unique_item_per_order"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_item_quantity_positive"),
        ]

    def clean(self) -> None:
        if self.order_id and self.item_id and self.order.currency != self.item.currency:
            raise ValidationError({"item": "Item currency must match order currency."})

    def __str__(self) -> str:
        return f"{self.quantity} x {self.item.name}"
