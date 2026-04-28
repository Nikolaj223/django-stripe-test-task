from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .constants import ZERO_DECIMAL_CURRENCIES


@dataclass(frozen=True)
class OrderTotals:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def money_to_minor_units(amount: Decimal, currency: str) -> int:
    currency = currency.lower()
    if currency in ZERO_DECIMAL_CURRENCIES:
        return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantize_money(amount: Decimal, currency: str) -> Decimal:
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_order_totals(order) -> OrderTotals:
    currency = order.currency
    subtotal = sum(
        (order_item.item.price * order_item.quantity for order_item in order.order_items.select_related("item").all()),
        Decimal("0"),
    )
    subtotal = quantize_money(subtotal, currency)

    discount = Decimal("0")
    if order.discount and order.discount.active:
        if order.discount.percent_off is not None:
            discount = subtotal * order.discount.percent_off / Decimal("100")
        elif order.discount.amount_off is not None:
            discount = order.discount.amount_off
        discount = min(quantize_money(discount, currency), subtotal)

    taxable_amount = subtotal - discount
    tax = Decimal("0")
    for tax_rate in order.taxes.filter(active=True):
        if not tax_rate.inclusive:
            tax += taxable_amount * tax_rate.percentage / Decimal("100")
    tax = quantize_money(tax, currency)

    total = quantize_money(taxable_amount + tax, currency)
    return OrderTotals(subtotal=subtotal, discount=discount, tax=tax, total=total)
