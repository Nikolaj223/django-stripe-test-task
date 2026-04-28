from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings

from .models import Discount, Item, Order, OrderItem, Tax
from .pricing import calculate_order_totals, money_to_minor_units
from .services.stripe_checkout import (
    StripeConfigurationError,
    create_item_checkout_session,
    create_order_checkout_session,
    create_order_payment_intent,
    get_keypair,
)


STRIPE_TEST_KEYPAIRS = {
    "usd": {
        "secret_key": "sk_test_usd",
        "publishable_key": "pk_test_usd",
    },
    "eur": {
        "secret_key": "sk_test_eur",
        "publishable_key": "pk_test_eur",
    },
}


class PricingTests(TestCase):
    def test_money_to_minor_units_for_decimal_currency(self):
        assert money_to_minor_units(Decimal("19.99"), "usd") == 1999

    def test_money_to_minor_units_for_zero_decimal_currency(self):
        assert money_to_minor_units(Decimal("1200.40"), "jpy") == 1200


@override_settings(STRIPE_KEYPAIRS=STRIPE_TEST_KEYPAIRS)
class CheckoutServiceTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.item = Item.objects.create(
            name="Test item",
            description="Description",
            price=Decimal("12.30"),
            currency="usd",
        )
        self.discount = Discount.objects.create(name="Launch 10", percent_off=Decimal("10.00"))
        self.tax = Tax.objects.create(display_name="Sales tax", percentage=Decimal("7.25"))
        self.order = Order.objects.create(title="Starter bundle", currency="usd", discount=self.discount)
        self.order.taxes.add(self.tax)
        OrderItem.objects.create(order=self.order, item=self.item, quantity=2)

    def test_get_keypair_raises_clear_error_for_missing_currency(self):
        with self.assertRaises(StripeConfigurationError):
            get_keypair("gbp")

    def test_create_item_checkout_session_uses_expected_payload(self):
        request = self.factory.get(f"/item/{self.item.pk}", HTTP_HOST="testserver")

        with patch("payments.services.stripe_checkout.stripe.checkout.Session.create") as create:
            create.return_value = SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.test/session")

            session = create_item_checkout_session(self.item, request)

        assert session.id == "cs_test_123"
        create.assert_called_once()
        payload = create.call_args.kwargs
        assert payload["api_key"] == "sk_test_usd"
        assert payload["mode"] == "payment"
        assert payload["line_items"][0]["price_data"]["unit_amount"] == 1230
        assert payload["line_items"][0]["price_data"]["currency"] == "usd"
        assert payload["client_reference_id"] == f"item:{self.item.pk}"

    def test_create_order_checkout_session_passes_discount_tax_and_line_items(self):
        request = self.factory.get(f"/order/{self.order.pk}", HTTP_HOST="testserver")

        with (
            patch("payments.services.stripe_checkout.stripe.Coupon.create") as create_coupon,
            patch("payments.services.stripe_checkout.stripe.TaxRate.create") as create_tax_rate,
            patch("payments.services.stripe_checkout.stripe.checkout.Session.create") as create_session,
        ):
            create_coupon.return_value = SimpleNamespace(id="coupon_test_123")
            create_tax_rate.return_value = SimpleNamespace(id="txr_test_123")
            create_session.return_value = SimpleNamespace(id="cs_order_123", url="https://checkout.stripe.test/order")

            session = create_order_checkout_session(self.order, request)

        assert session.id == "cs_order_123"
        create_coupon.assert_called_once()
        create_tax_rate.assert_called_once()
        create_session.assert_called_once()

        payload = create_session.call_args.kwargs
        assert payload["api_key"] == "sk_test_usd"
        assert payload["mode"] == "payment"
        assert payload["discounts"] == [{"coupon": "coupon_test_123"}]
        assert payload["line_items"][0]["quantity"] == 2
        assert payload["line_items"][0]["tax_rates"] == ["txr_test_123"]
        assert payload["line_items"][0]["price_data"]["unit_amount"] == 1230

    def test_create_order_checkout_session_rejects_mixed_currencies(self):
        eur_item = Item.objects.create(
            name="EUR item",
            description="EUR",
            price=Decimal("9.99"),
            currency="eur",
        )
        mixed_order = Order.objects.create(title="Mixed", currency="usd")
        OrderItem.objects.create(order=mixed_order, item=eur_item, quantity=1)

        with self.assertRaises(ValidationError):
            create_order_checkout_session(mixed_order, self.factory.get("/order/2", HTTP_HOST="testserver"))

    def test_order_payment_intent_uses_calculated_total(self):
        totals = calculate_order_totals(self.order)
        assert totals.subtotal == Decimal("24.60")
        assert totals.discount == Decimal("2.46")
        assert totals.tax == Decimal("1.61")
        assert totals.total == Decimal("23.75")

        with patch("payments.services.stripe_checkout.stripe.PaymentIntent.create") as create:
            create.return_value = SimpleNamespace(
                id="pi_test_123",
                client_secret="pi_test_123_secret",
                amount=2375,
                currency="usd",
            )
            payment_intent = create_order_payment_intent(self.order)

        assert payment_intent.id == "pi_test_123"
        payload = create.call_args.kwargs
        assert payload["api_key"] == "sk_test_usd"
        assert payload["amount"] == 2375
        assert payload["currency"] == "usd"


@override_settings(STRIPE_KEYPAIRS=STRIPE_TEST_KEYPAIRS)
class PaymentViewsTests(TestCase):
    def setUp(self):
        self.item = Item.objects.create(
            name="View item",
            description="Description",
            price=Decimal("15.00"),
            currency="usd",
        )

    def test_health_endpoint_reports_ready_status(self):
        response = self.client.get("/health/")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["database"] == "ok"
        assert response.json()["stripe"]["usd"] is True

    def test_item_page_contains_buy_button_and_publishable_key(self):
        response = self.client.get(f"/item/{self.item.pk}")

        assert response.status_code == 200
        self.assertContains(response, self.item.name)
        self.assertContains(response, 'id="buy-button"')
        self.assertContains(response, "pk_test_usd")
        self.assertContains(response, f"/buy/{self.item.pk}")

    def test_buy_item_view_returns_checkout_session_id(self):
        with patch("payments.services.stripe_checkout.stripe.checkout.Session.create") as create:
            create.return_value = SimpleNamespace(id="cs_view_123", url="https://checkout.stripe.test/view")

            response = self.client.get(f"/buy/{self.item.pk}")

        assert response.status_code == 200
        assert response.json() == {"id": "cs_view_123", "url": "https://checkout.stripe.test/view"}

    def test_missing_item_returns_404(self):
        assert self.client.get("/item/999").status_code == 404
        assert self.client.get("/buy/999").status_code == 404
