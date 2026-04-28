from decimal import Decimal

import stripe
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.urls import reverse

from payments.models import Discount, Item, Order, Tax
from payments.pricing import calculate_order_totals, money_to_minor_units


class StripeConfigurationError(ImproperlyConfigured):
    pass


def _configure_app_info() -> None:
    app_info = getattr(settings, "STRIPE_APP_INFO", None)
    if app_info:
        stripe.set_app_info(**app_info)


def get_keypair(currency: str) -> dict[str, str]:
    currency = currency.lower()
    keypair = getattr(settings, "STRIPE_KEYPAIRS", {}).get(currency) or {}
    secret_key = keypair.get("secret_key")
    publishable_key = keypair.get("publishable_key")
    if not secret_key:
        raise StripeConfigurationError(f"Stripe secret key for {currency.upper()} is not configured.")
    return {"secret_key": secret_key, "publishable_key": publishable_key or ""}


def get_publishable_key(currency: str) -> str:
    currency = currency.lower()
    keypair = getattr(settings, "STRIPE_KEYPAIRS", {}).get(currency) or {}
    return keypair.get("publishable_key", "")


def _success_url(request) -> str:
    return f"{request.build_absolute_uri(reverse('payments:success'))}?session_id={{CHECKOUT_SESSION_ID}}"


def _item_cancel_url(request, item: Item) -> str:
    return request.build_absolute_uri(reverse("payments:item_detail", args=[item.pk]))


def _order_cancel_url(request, order: Order) -> str:
    return request.build_absolute_uri(reverse("payments:order_detail", args=[order.pk]))


def _item_line_item(item: Item, quantity: int = 1, tax_rate_ids: list[str] | None = None) -> dict:
    product_data = {
        "name": item.name,
        "metadata": {"item_id": str(item.pk)},
    }
    if item.description:
        product_data["description"] = item.description[:1000]

    line_item = {
        "price_data": {
            "currency": item.currency,
            "product_data": product_data,
            "unit_amount": money_to_minor_units(item.price, item.currency),
        },
        "quantity": quantity,
    }
    if tax_rate_ids:
        line_item["tax_rates"] = tax_rate_ids
    return line_item


def create_item_checkout_session(item: Item, request):
    _configure_app_info()
    keypair = get_keypair(item.currency)
    return stripe.checkout.Session.create(
        api_key=keypair["secret_key"],
        mode="payment",
        line_items=[_item_line_item(item)],
        success_url=_success_url(request),
        cancel_url=_item_cancel_url(request, item),
        client_reference_id=f"item:{item.pk}",
        metadata={"item_id": str(item.pk), "source": "item"},
    )


def _ensure_coupon(discount: Discount, currency: str, api_key: str) -> str:
    coupon_ids = dict(discount.stripe_coupon_ids or {})
    if coupon_ids.get(currency):
        return coupon_ids[currency]

    params = {
        "name": discount.name,
        "duration": "once",
        "metadata": {"discount_id": str(discount.pk)},
    }
    if discount.percent_off is not None:
        params["percent_off"] = str(discount.percent_off)
    else:
        if discount.currency != currency:
            raise ValidationError("Discount currency must match order currency.")
        params["amount_off"] = money_to_minor_units(discount.amount_off, currency)
        params["currency"] = currency

    coupon = stripe.Coupon.create(api_key=api_key, **params)
    coupon_ids[currency] = coupon.id
    Discount.objects.filter(pk=discount.pk).update(stripe_coupon_ids=coupon_ids)
    discount.stripe_coupon_ids = coupon_ids
    return coupon.id


def _ensure_tax_rate(tax: Tax, currency: str, api_key: str) -> str:
    tax_rate_ids = dict(tax.stripe_tax_rate_ids or {})
    if tax_rate_ids.get(currency):
        return tax_rate_ids[currency]

    tax_rate = stripe.TaxRate.create(
        api_key=api_key,
        display_name=tax.display_name,
        percentage=str(tax.percentage),
        inclusive=tax.inclusive,
        metadata={"tax_id": str(tax.pk)},
    )
    tax_rate_ids[currency] = tax_rate.id
    Tax.objects.filter(pk=tax.pk).update(stripe_tax_rate_ids=tax_rate_ids)
    tax.stripe_tax_rate_ids = tax_rate_ids
    return tax_rate.id


def _validate_order(order: Order) -> None:
    order_items = list(order.order_items.select_related("item"))
    if not order_items:
        raise ValidationError("Order must contain at least one item.")
    mismatched = [order_item.item_id for order_item in order_items if order_item.item.currency != order.currency]
    if mismatched:
        raise ValidationError("All order items must have the same currency as the order.")
    if order.discount and order.discount.amount_off is not None and order.discount.currency != order.currency:
        raise ValidationError("Fixed amount discount currency must match order currency.")


def create_order_checkout_session(order: Order, request):
    _configure_app_info()
    _validate_order(order)
    keypair = get_keypair(order.currency)
    api_key = keypair["secret_key"]

    tax_rate_ids = [
        _ensure_tax_rate(tax, order.currency, api_key)
        for tax in order.taxes.filter(active=True)
    ]
    line_items = [
        _item_line_item(order_item.item, order_item.quantity, tax_rate_ids)
        for order_item in order.order_items.select_related("item").all()
    ]

    params = {
        "api_key": api_key,
        "mode": "payment",
        "line_items": line_items,
        "success_url": _success_url(request),
        "cancel_url": _order_cancel_url(request, order),
        "client_reference_id": f"order:{order.pk}",
        "metadata": {"order_id": str(order.pk), "source": "order"},
    }
    if order.discount and order.discount.active:
        params["discounts"] = [{"coupon": _ensure_coupon(order.discount, order.currency, api_key)}]

    return stripe.checkout.Session.create(**params)


def create_item_payment_intent(item: Item):
    _configure_app_info()
    keypair = get_keypair(item.currency)
    return stripe.PaymentIntent.create(
        api_key=keypair["secret_key"],
        amount=money_to_minor_units(item.price, item.currency),
        currency=item.currency,
        description=item.name,
        automatic_payment_methods={"enabled": True},
        metadata={"item_id": str(item.pk), "source": "item"},
    )


def create_order_payment_intent(order: Order):
    _configure_app_info()
    _validate_order(order)
    keypair = get_keypair(order.currency)
    totals = calculate_order_totals(order)
    amount = max(totals.total, Decimal("0"))
    return stripe.PaymentIntent.create(
        api_key=keypair["secret_key"],
        amount=money_to_minor_units(amount, order.currency),
        currency=order.currency,
        description=order.title,
        automatic_payment_methods={"enabled": True},
        metadata={"order_id": str(order.pk), "source": "order"},
    )
