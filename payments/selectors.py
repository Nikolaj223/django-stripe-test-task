from django.shortcuts import get_object_or_404

from .models import Item, Order


def get_item_or_404(pk: int) -> Item:
    return get_object_or_404(Item, pk=pk)


def get_order_or_404(pk: int) -> Order:
    return get_object_or_404(
        Order.objects.select_related("discount").prefetch_related("taxes", "order_items__item"),
        pk=pk,
    )
