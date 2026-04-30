from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(condition=models.Q(price__gt=0), name="item_price_positive"),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(amount_off__isnull=True, currency="", percent_off__isnull=False)
                    | (models.Q(amount_off__isnull=False, percent_off__isnull=True) & ~models.Q(currency=""))
                ),
                name="discount_exactly_one_value",
            ),
        ),
        migrations.AddConstraint(
            model_name="discount",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(percent_off__isnull=True) | models.Q(percent_off__gt=0, percent_off__lte=100))
                    & (models.Q(amount_off__isnull=True) | models.Q(amount_off__gt=0))
                ),
                name="discount_values_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="tax",
            constraint=models.CheckConstraint(
                condition=models.Q(percentage__gt=0, percentage__lte=100),
                name="tax_percentage_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="order_item_quantity_positive"),
        ),
    ]
