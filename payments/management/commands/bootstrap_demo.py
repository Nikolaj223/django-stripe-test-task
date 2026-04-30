import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from payments.models import Discount, Item, Order, OrderItem, Tax


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Seed sample store data and optionally create an admin user."

    def handle(self, *args, **options):
        if env_bool("DJANGO_LOAD_DEMO_DATA", False):
            self._create_demo_data()

        if env_bool("DJANGO_CREATE_SUPERUSER", False):
            self._create_admin_user()

    def _create_demo_data(self) -> None:
        hoodie, _ = Item.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Django Hoodie",
                "description": "Cotton hoodie with a clean Django print.",
                "price": Decimal("49.00"),
                "currency": "usd",
            },
        )
        Item.objects.update_or_create(
            pk=2,
            defaults={
                "name": "API Mug",
                "description": "Ceramic mug for API coffee breaks.",
                "price": Decimal("18.50"),
                "currency": "eur",
            },
        )
        discount, _ = Discount.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Launch 10",
                "percent_off": Decimal("10.00"),
                "amount_off": None,
                "currency": "",
                "active": True,
            },
        )
        tax, _ = Tax.objects.update_or_create(
            pk=1,
            defaults={
                "display_name": "Sales tax",
                "percentage": Decimal("7.25"),
                "inclusive": False,
                "active": True,
            },
        )
        order, _ = Order.objects.update_or_create(
            pk=1,
            defaults={
                "title": "Starter bundle",
                "currency": "usd",
                "discount": discount,
            },
        )
        order.taxes.set([tax])
        OrderItem.objects.update_or_create(
            order=order,
            item=hoodie,
            defaults={"quantity": 2},
        )
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))

    def _create_admin_user(self) -> None:
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not password:
            self.stdout.write(self.style.WARNING("DJANGO_SUPERUSER_PASSWORD is empty; admin user was not created."))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(update_fields=["email", "is_staff", "is_superuser", "password"])

        message = "Admin user created." if created else "Admin user updated."
        self.stdout.write(self.style.SUCCESS(message))
