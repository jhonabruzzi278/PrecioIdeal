# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

**Precio Ideal** is a Django 5.x price monitoring app that scrapes [knasta.cl](https://knasta.cl) (a Chilean price-comparison site). Users configure **Monitors** (each pointing to a product category), the app scrapes that category on demand or on a schedule, saves products and price history, and generates **UpdateReports** with statistics.

Audience: being converted from internal/personal use into a multi-tenant **SaaS** (see
[docs/saas-roadmap.md](docs/saas-roadmap.md)). All app views now require login
(`@login_required`); `Monitor` is scoped per user via its `owner` FK. Products and reports
are not yet per-user scoped — that's a pending Fase 1 item. Billing (subscriptions via the
Flow payment gateway) is planned, not yet built.

Locale: `es-cl`, timezone `America/Santiago`. User-visible text and model `verbose_name` are in **Spanish**; code, variable names, and comments are in **English**.

## Local setup

Config is read from environment via `django-environ` (`pricewatch/settings.py`). Copy
`.env.example` to `.env` and start the backing services with Docker before running Django:

```bash
cp .env.example .env          # then edit SECRET_KEY etc.
docker compose up -d          # starts PostgreSQL + Redis
pip install -r requirements.txt
python manage.py migrate
```

Settings have safe local defaults, so `.env` is optional in dev. `DEBUG=False` activates
production security headers (HSTS, secure cookies, SSL redirect). Database is **PostgreSQL**
(not SQLite anymore), connected via `DATABASE_URL`; cache/`CACHES` is **Redis** via
`django-redis`. To preserve legacy SQLite data when first switching, follow
[docs/migrate-sqlite-to-postgres.md](docs/migrate-sqlite-to-postgres.md).

## Commands

```bash
python manage.py migrate
python manage.py runserver
python manage.py test                        # run all tests
python manage.py test products               # run tests for one app
python manage.py update_prices               # manually trigger a scrape run
python manage.py backfill_pricing            # recalculate pricing fields on existing products
python manage.py createsuperuser
python manage.py shell
python manage.py makemigrations              # after any model change
```

No frontend build step — templates use plain HTML + Bootstrap via CDN.

## Architecture

Three Django apps:

- **`pricewatch/`** — project config, root URL conf, WSGI/ASGI
- **`products/`** — `Product` and `PriceHistory` models; scraping logic
- **`monitoring/`** — `Monitor`, `UpdateReport`, `UpdateReportEntry`, `UpdateSchedule` models; scheduler

### Service layer

Business logic lives in `<app>/services/`, never in views or models:

| File | Responsibility |
|------|---------------|
| `products/services/knasta.py` | `KnastaScraper` — HTTP scraping and product normalization |
| `products/services/pricing.py` | Pure pricing calculations (`compute_knasta_pricing`) |
| `products/services/persistence.py` | `save_products()` — upsert + price history writes |
| `products/services/database.py` | `clear_scraped_data()` — bulk delete |
| `monitoring/services/update.py` | `run_update_report()` / `update_all_prices()` — orchestrates a full update run |

### Key domain concepts

| Term | Meaning |
|------|---------|
| `kid` | Knasta's unique product ID — natural key for `Product`, use it for lookups (not `pk`) |
| `Monitor` | Watched category; holds `category_slug` used to build scraper URLs |
| `UpdateReport` | One scraping run with status, progress, and aggregate stats |
| `UpdateReportEntry` | A line item in a report: new product or price change |
| `PriceHistory` | Immutable price record at a point in time |
| `UpdateSchedule` | Singleton; always access via `UpdateSchedule.get_solo()` |

### Background execution

Long-running scraping jobs run in a **daemon `threading.Thread`** (see `monitoring/scheduler.py`). No Celery. Always call `connection.close()` in a `finally` block inside background threads.

### Conventions

- Views: function-based only. Mutating actions use `@require_POST`. Flash messages map to Bootstrap alert classes (`MESSAGE_TAGS` maps `ERROR` → `"danger"`).
- Prices: stored as `PositiveIntegerField` (Chilean pesos, no decimals). Format with `f"${price:,.0f}".replace(",", ".")`.
- Timestamps: use `auto_now_add` / `auto_now`; never assign manually.
- URLs: all names `snake_case`, flat namespace (no prefix).
- Templates: all extend `templates/base.html`; partials go in `<app>/templates/<app>/partials/`.
- Pagination: `Paginator` with 24 items per page.
- Migrations: never edit existing migration files; always add new ones.
