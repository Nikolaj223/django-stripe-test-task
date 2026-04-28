import decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Discount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                (
                    "percent_off",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.01")),
                            django.core.validators.MaxValueValidator(decimal.Decimal("100")),
                        ],
                    ),
                ),
                (
                    "amount_off",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(blank=True, choices=[("usd", "USD"), ("eur", "EUR")], max_length=3)),
                ("active", models.BooleanField(default=True)),
                ("stripe_coupon_ids", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(choices=[("usd", "USD"), ("eur", "EUR")], default="usd", max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Tax",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(max_length=80)),
                (
                    "percentage",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal("0.01")),
                            django.core.validators.MaxValueValidator(decimal.Decimal("100")),
                        ],
                    ),
                ),
                ("inclusive", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("stripe_tax_rate_ids", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("display_name",)},
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("currency", models.CharField(choices=[("usd", "USD"), ("eur", "EUR")], default="usd", max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "discount",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="orders",
                        to="payments.discount",
                    ),
                ),
                ("taxes", models.ManyToManyField(blank=True, related_name="orders", to="payments.tax")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "quantity",
                    models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)]),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_items",
                        to="payments.item",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="order_items",
                        to="payments.order",
                    ),
                ),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddField(
            model_name="order",
            name="items",
            field=models.ManyToManyField(related_name="orders", through="payments.OrderItem", to="payments.item"),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(fields=("order", "item"), name="unique_item_per_order"),
        ),
    ]
