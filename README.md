# Django Stripe Store

Небольшой Django-сервис для оплаты товаров через Stripe Checkout. Основной сценарий ровно соответствует заданию: страница товара открывается по `/item/{id}`, кнопка Buy запрашивает `/buy/{id}`, backend создает `stripe.checkout.Session`, а браузер уходит на Stripe Checkout по `session.id`.

## Возможности

- Товар `Item`: `name`, `description`, `price`, `currency`.
- `GET /item/{id}` - HTML-страница товара с кнопкой Buy.
- `GET /buy/{id}` - создание Stripe Checkout Session для товара.
- Заказ `Order` с несколькими позициями через `OrderItem`.
- Скидка `Discount` для заказа через Stripe Coupon.
- Налог `Tax` для заказа через Stripe TaxRate.
- Отдельные Stripe keypair для USD и EUR через environment variables.
- Django Admin для всех моделей.
- Docker, Docker Compose, Render blueprint и GitHub Actions CI.
- Дополнительный PaymentIntent flow:
  - `GET /payment-intent/item/{id}`
  - `GET /payment-intent/order/{id}`
  - `GET /payment-intent/item/{id}/pay`
- `GET /health/` для проверки деплоя.

## Структура

```text
config/                         Django settings and URL root
payments/models.py              Item, Order, OrderItem, Discount, Tax
payments/services/              Stripe integration
payments/pricing.py             Money conversion and order totals
payments/selectors.py           Database access helpers
payments/templates/payments/    HTML pages
payments/management/commands/   Demo bootstrap command
```

Stripe-логика вынесена из views в `payments/services/stripe_checkout.py`; views только получают объекты, вызывают сервис и возвращают HTML/JSON.

## Быстрый запуск

Создайте `.env`:

```bash
cp .env.example .env
```

Укажите Stripe test keys:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY_USD=sk_test_...
STRIPE_PUBLISHABLE_KEY_USD=pk_test_...
STRIPE_SECRET_KEY_EUR=sk_test_...
STRIPE_PUBLISHABLE_KEY_EUR=pk_test_...
```

Запустите Docker:

```bash
docker compose up --build
```

После старта доступны:

- http://localhost:8000/
- http://localhost:8000/item/1
- http://localhost:8000/buy/1
- http://localhost:8000/order/1
- http://localhost:8000/health/
- http://localhost:8000/admin/

Локальные admin credentials из `.env.example`:

```text
login: admin
password: admin12345
```

## Запуск без Docker

Linux/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
export DJANGO_LOAD_DEMO_DATA=1
export DJANGO_CREATE_SUPERUSER=1
DJANGO_SUPERUSER_USERNAME=admin \
DJANGO_SUPERUSER_EMAIL=admin@example.com \
DJANGO_SUPERUSER_PASSWORD=admin12345 \
python manage.py bootstrap_demo
python manage.py runserver
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
Set-Item Env:DJANGO_LOAD_DEMO_DATA "1"
Set-Item Env:DJANGO_CREATE_SUPERUSER "1"
$env:DJANGO_SUPERUSER_USERNAME="admin"
$env:DJANGO_SUPERUSER_EMAIL="admin@example.com"
$env:DJANGO_SUPERUSER_PASSWORD="admin12345"
python manage.py bootstrap_demo
python manage.py runserver
```

## API

```bash
curl http://localhost:8000/item/1
curl http://localhost:8000/buy/1
curl http://localhost:8000/order/1
curl http://localhost:8000/buy/order/1
curl http://localhost:8000/payment-intent/item/1
curl http://localhost:8000/health/
```

`/buy/{id}` возвращает JSON:

```json
{
  "id": "cs_test_...",
  "url": "https://checkout.stripe.com/..."
}
```

Frontend использует именно `id`: `stripe.redirectToCheckout({ sessionId: session.id })`.

## Stripe

- Цены хранятся в основных денежных единицах: `49.00`, `18.50`.
- Перед отправкой в Stripe сумма конвертируется в minor units: cents для USD/EUR.
- Coupons и TaxRates создаются лениво при первой оплате заказа и сохраняются в `stripe_coupon_ids` / `stripe_tax_rate_ids`.
- Для тестовой оплаты можно использовать карту `4242 4242 4242 4242`, любую будущую дату и любой CVC.

## Тесты

```bash
python manage.py test
```

или:

```bash
pytest
```

В тестах проверяются Checkout Session для товара, Order с Discount/Tax, PaymentIntent, mixed currency validation, HTML-страница товара и health endpoint.

## Деплой

Минимальный набор environment variables:

```env
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1
DJANGO_SECURE_HSTS_PRELOAD=1

STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY_USD=sk_test_...
STRIPE_PUBLISHABLE_KEY_USD=pk_test_...
STRIPE_SECRET_KEY_EUR=sk_test_...
STRIPE_PUBLISHABLE_KEY_EUR=pk_test_...

DJANGO_LOAD_DEMO_DATA=1
DJANGO_CREATE_SUPERUSER=1
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=strong-review-password
```

Команды для обычного server/runtime:

```bash
python manage.py migrate --noinput
python manage.py bootstrap_demo
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

Для Render можно использовать `render.yaml` или создать Web Service из Dockerfile. После деплоя проверьте:

- `/health/`
- `/item/1`
- `/admin/`

На Render домен из `RENDER_EXTERNAL_HOSTNAME` автоматически добавляется в `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`, поэтому вручную достаточно задать Stripe keys и admin credentials. `/health/` покажет `stripe.usd=true` и `stripe.eur=true` только когда вместо placeholder-значений указаны реальные Stripe test keys.

## Что отправить на проверку

```text
GitHub: https://github.com/Nikolaj223/django-stripe-test-task
Demo: https://<domain>/item/1
Admin: https://<domain>/admin/
login: admin
password: <password from deployment env>
Health: https://<domain>/health/
```
