# Django Stripe Checkout test task

Реализация тестового задания: Django backend + Stripe Checkout для товаров, HTML-страница с кнопкой Buy, админка и бонусные сущности Order, Discount, Tax, currency-specific keypairs, Docker и отдельный PaymentIntent flow.

## Что реализовано

- `GET /item/{id}` - HTML-страница товара с кнопкой Buy.
- `GET /buy/{id}` - создает `stripe.checkout.Session` и возвращает JSON `{ "id": "cs_..." }`.
- `GET /order/{id}` и `GET /buy/order/{id}` - оплата заказа из нескольких Items.
- `Discount` подключается к Order как Stripe Coupon.
- `Tax` подключается к Order как Stripe Tax Rate и передается в Checkout line items.
- `Item.currency` и выбор Stripe keypair по валюте (`usd`, `eur`).
- Django Admin для всех моделей.
- Docker/Docker Compose, env variables, idempotent demo bootstrap.
- Render blueprint (`render.yaml`) and GitHub Actions CI.
- Health endpoint for hosting checks: `GET /health/`.
- Бонусный PaymentIntent API:
  - `GET /payment-intent/item/{id}`
  - `GET /payment-intent/order/{id}`
  - `GET /payment-intent/item/{id}/pay`

## Быстрый запуск через Docker

1. Создайте `.env`:

```bash
cp .env.example .env
```

2. Впишите Stripe test keys:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY_USD=sk_test_...
STRIPE_PUBLISHABLE_KEY_USD=pk_test_...
STRIPE_SECRET_KEY_EUR=sk_test_...
STRIPE_PUBLISHABLE_KEY_EUR=pk_test_...
```

3. Запустите:

```bash
docker compose up --build
```

4. Откройте:

- Store: http://localhost:8000/
- Required item page: http://localhost:8000/item/1
- Required API: http://localhost:8000/buy/1
- Order page: http://localhost:8000/order/1
- Health: http://localhost:8000/health/
- Admin: http://localhost:8000/admin/

Demo admin credentials from `.env.example`:

```text
login: admin
password: admin12345
```

## Локальный запуск без Docker

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

## API examples

```bash
curl -X GET http://localhost:8000/item/1
curl -X GET http://localhost:8000/buy/1
curl -X GET http://localhost:8000/order/1
curl -X GET http://localhost:8000/buy/order/1
curl -X GET http://localhost:8000/payment-intent/item/1
curl -X GET http://localhost:8000/health/
```

`/buy/{id}` intentionally returns the Checkout Session id for the task requirement. The response also includes `url` for easier debugging with newer Stripe-hosted Checkout flows.

## Stripe notes

- Prices in the database are stored in major units (`49.00` USD). The service converts them to minor units before calling Stripe.
- Stripe Coupons and Tax Rates are created lazily on the first order checkout and their ids are cached in `Discount.stripe_coupon_ids` and `Tax.stripe_tax_rate_ids`.
- Stripe Checkout currently accepts one coupon per Checkout Session, so `Order` has one optional `discount`.
- For test payments use Stripe card `4242 4242 4242 4242`, any future expiry date and any CVC.

## Tests

```bash
python manage.py test
```

or:

```bash
pytest
```

## Deployment checklist

Set these environment variables on the server:

```env
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=your-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
DJANGO_LOAD_DEMO_DATA=1
DJANGO_CREATE_SUPERUSER=1
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=strong-review-password
```

Then run:

```bash
python manage.py migrate --noinput
python manage.py bootstrap_demo
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

For platforms with Docker support, deploy the provided `Dockerfile`; the entrypoint runs migrations, optional demo data load and optional superuser creation.

Render shortcut: create a Blueprint from this repository, set `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, Stripe keys and admin credentials in the Render dashboard, then open `/item/1` and `/admin/`.

## Submission checklist

- Public app URL: `https://<your-domain>/item/1`
- Admin URL: `https://<your-domain>/admin/`
- Admin credentials: provide the demo username and password from deployment env vars.
- GitHub repository URL with this README.
- Stripe test keys configured in hosting environment.
- Smoke check before sending: `/health/` returns `{"status": "ok"}` and `/item/1` redirects to Stripe Checkout after clicking Buy.
