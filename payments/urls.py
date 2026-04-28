from django.urls import path

from . import views


app_name = "payments"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.index, name="index"),
    path("item/<int:pk>", views.item_detail, name="item_detail"),
    path("item/<int:pk>/", views.item_detail),
    path("order/<int:pk>", views.order_detail, name="order_detail"),
    path("order/<int:pk>/", views.order_detail),
    path("buy/<int:pk>", views.buy_item, name="buy_item"),
    path("buy/<int:pk>/", views.buy_item),
    path("buy/order/<int:pk>", views.buy_order, name="buy_order"),
    path("buy/order/<int:pk>/", views.buy_order),
    path("payment-intent/item/<int:pk>", views.item_payment_intent, name="item_payment_intent"),
    path("payment-intent/item/<int:pk>/", views.item_payment_intent),
    path("payment-intent/item/<int:pk>/pay", views.item_payment_intent_page, name="item_payment_intent_page"),
    path("payment-intent/item/<int:pk>/pay/", views.item_payment_intent_page),
    path("payment-intent/order/<int:pk>", views.order_payment_intent, name="order_payment_intent"),
    path("payment-intent/order/<int:pk>/", views.order_payment_intent),
    path("success/", views.success, name="success"),
    path("cancel/", views.cancel, name="cancel"),
]
