import stripe
from django.core.exceptions import ValidationError
from django.db import connections
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .models import Item, Order
from .pricing import calculate_order_totals
from .selectors import get_item_or_404, get_order_or_404
from .services.stripe_checkout import (
    StripeConfigurationError,
    create_item_checkout_session,
    create_item_payment_intent,
    create_order_checkout_session,
    create_order_payment_intent,
    get_publishable_key,
)

StripeError = getattr(stripe, "StripeError", None)
if StripeError is None:
    StripeError = stripe.error.StripeError


def _api_error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _stripe_error_message(exc: Exception) -> str:
    return getattr(exc, "user_message", None) or str(exc)


@require_GET
def health(request):
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")

    return JsonResponse(
        {
            "status": "ok",
            "database": "ok",
            "stripe": {
                "usd": bool(get_publishable_key("usd")),
                "eur": bool(get_publishable_key("eur")),
            },
        }
    )


@require_GET
def index(request):
    return render(
        request,
        "payments/index.html",
        {
            "items": Item.objects.all(),
            "orders": Order.objects.prefetch_related("order_items__item").all(),
        },
    )


@require_GET
def item_detail(request, pk: int):
    item = get_item_or_404(pk)
    return render(
        request,
        "payments/item_detail.html",
        {
            "item": item,
            "publishable_key": get_publishable_key(item.currency),
        },
    )


@require_GET
def order_detail(request, pk: int):
    order = get_order_or_404(pk)
    return render(
        request,
        "payments/order_detail.html",
        {
            "order": order,
            "totals": calculate_order_totals(order),
            "publishable_key": get_publishable_key(order.currency),
        },
    )


@require_GET
def buy_item(request, pk: int):
    item = get_item_or_404(pk)
    try:
        session = create_item_checkout_session(item, request)
    except StripeConfigurationError as exc:
        return _api_error(str(exc), 503)
    except StripeError as exc:
        return _api_error(_stripe_error_message(exc), 502)
    return JsonResponse({"id": session.id, "url": getattr(session, "url", None)})


@require_GET
def buy_order(request, pk: int):
    order = get_order_or_404(pk)
    try:
        session = create_order_checkout_session(order, request)
    except (StripeConfigurationError, ValidationError) as exc:
        return _api_error(str(exc), 400)
    except StripeError as exc:
        return _api_error(_stripe_error_message(exc), 502)
    return JsonResponse({"id": session.id, "url": getattr(session, "url", None)})


@require_GET
def item_payment_intent(request, pk: int):
    item = get_item_or_404(pk)
    try:
        payment_intent = create_item_payment_intent(item)
    except StripeConfigurationError as exc:
        return _api_error(str(exc), 503)
    except StripeError as exc:
        return _api_error(_stripe_error_message(exc), 502)
    return JsonResponse(
        {
            "id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
            "publishable_key": get_publishable_key(item.currency),
        }
    )


@require_GET
def order_payment_intent(request, pk: int):
    order = get_order_or_404(pk)
    try:
        payment_intent = create_order_payment_intent(order)
    except (StripeConfigurationError, ValidationError) as exc:
        return _api_error(str(exc), 400)
    except StripeError as exc:
        return _api_error(_stripe_error_message(exc), 502)
    return JsonResponse(
        {
            "id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
            "publishable_key": get_publishable_key(order.currency),
        }
    )


@require_GET
def item_payment_intent_page(request, pk: int):
    item = get_item_or_404(pk)
    return render(
        request,
        "payments/payment_intent_item.html",
        {
            "item": item,
            "publishable_key": get_publishable_key(item.currency),
        },
    )


@require_GET
def success(request):
    return render(request, "payments/success.html", {"session_id": request.GET.get("session_id", "")})


@require_GET
def cancel(request):
    return redirect("payments:index")
