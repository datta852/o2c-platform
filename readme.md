# O2C Automation Platform

A small Order-to-Cash API built with FastAPI, Pydantic, SQLAlchemy, and SQLite. It models customer orders, invoices, cash receipts, allocation/reconciliation decisions, receivables, and collections actions.

## Current capabilities

- Customer, sales order, invoice, and payment APIs.
- Fixed-precision decimal amounts with request validation.
- Payment allocation across invoices with customer, lifecycle, and balance checks.
- Payment reconciliation plans that can match one payment to multiple invoices, leave it partially/unmatched, record exceptions, and be safely retried with an `Idempotency-Key`.
- Reconciliation status lookup and audit history.
- Receivables listing and summary with outstanding and overdue balances.
- Configurable dunning thresholds and an idempotent collection run that records scheduled actions and outcomes. It does not send email or make calls to external services.
- FastAPI OpenAPI and Swagger UI at `/docs`.

## Architecture

`main.py` registers route modules. Routes validate requests with Pydantic schemas, load ORM records through SQLAlchemy sessions, enforce business rules, and persist related changes in one commit. `database.py` defines entities and SQLite configuration; `schemas.py` defines API contracts and enums. Tests use synthetic entities in a separate in-memory SQLite database.

## Setup

Use Python 3.14 (the version used for local verification) and install the pinned project requirements:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The default database URL is `sqlite:///./o2c.db`. Set `DATABASE_URL` before migrating or starting the app to select another SQLAlchemy-supported database URL. The app does not create or migrate tables on import. Apply the versioned schema first:

```powershell
alembic upgrade head
fastapi dev main.py
```

For an existing database from the earlier version, stop the app and make a verified backup first. Confirm that its five original tables match revision `0001_core`; then mark that baseline and apply the additive/integrity migration:

```powershell
Copy-Item .\o2c.db .\o2c.db.backup
alembic stamp 0001_core
alembic upgrade head
```

Revision `0002_o2c_workflows` checks for null, non-positive, and duplicate allocation data before tightening constraints, and aborts with a message when cleanup is needed. The migration was verified on an isolated SQLite database containing synthetic legacy rows; this project has not run it against the repository's existing `o2c.db`.

Set `O2C_API_KEY` to require the `X-API-Key` header on business and receivables routes. If unset, the API allows requests for local development; keep the server bound to localhost in that mode. `/health` remains public. Never commit the key or store it in source control.

## API outline

| Area | Endpoints |
|---|---|
| Customers | `/customers/` create/list; `/customers/{id}` get/update/delete |
| Sales orders | `/orders/` create/list; `/orders/{id}` get/update/delete |
| Invoices | `/invoices/` create/list; `/invoices/{id}` get/update; DELETE is rejected because invoices are financial records |
| Payments | `/payments/` create/list; `/payments/{id}` get/update/delete |
| Reconciliation | `POST /payments/{id}/reconcile`, `GET /payments/{id}/reconciliation`, `GET /payments/{id}/reconciliation-audit` |
| Manual allocations | `/payment_allocations/` create/list; `/payment_allocations/{id}` get/update/delete |
| Receivables | `GET /receivables/`, `GET /receivables/summary` |
| Collections | `POST /collections/rules`, `GET /collections/rules`, `PUT /collections/rules/{id}`, `POST /collections/run`, `GET /collections/actions`, `PUT /collections/actions/{id}` |
| Service | `GET /health`, `GET /about` |

## Reconciliation example

Create a completed payment and outstanding invoice, then submit the complete allocation plan:

```http
POST /payments/42/reconcile
Idempotency-Key: bank-statement-row-2026-10-25-001
Content-Type: application/json

{
  "allocations": [
    {"invoice_id": 1001, "allocated_amount": "125.00"},
    {"invoice_id": 1002, "allocated_amount": "75.00"}
  ]
}
```

The request describes the desired allocation plan for that payment. Reusing the same key and payload returns the stored response. Reusing a key with a different payment or payload returns `409`. An empty allocation list records an unmatched payment; invalid matches create an exception record and leave the previous allocation plan intact. Successful corrected requests can resolve an exception under a new key.

## Receivables and collection run

`GET /receivables/summary?as_of=2026-10-25` returns total outstanding and overdue balances. `POST /collections/rules` configures an aging threshold and action type. `POST /collections/run?as_of=2026-10-25` creates one scheduled action per eligible invoice/rule pair; rerunning it does not duplicate actions. `PUT /collections/actions/{id}` records completion or failure and an outcome. A future worker or messaging integration is not included.

## Synthetic demo walkthrough

1. In Swagger UI, create a customer, a `PROCESSED` sales order, an `OPEN` invoice linked to that order, and a `COMPLETED` payment for the same customer.
2. Call `POST /payments/{payment_id}/reconcile` with a new `Idempotency-Key` header and an allocation plan. Inspect the result and history through the reconciliation status and audit endpoints.
3. Create a dunning rule (for example, 7 days overdue with action type `EMAIL_REMINDER`) and call `POST /collections/run?as_of=YYYY-MM-DD` with a date after the invoice due date.
4. Inspect `/receivables/summary` and `/collections/actions`, then record a synthetic completed or failed outcome for the scheduled action.

## Tests

Run the standard-library suite from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Tests use synthetic records and an in-memory database; they do not open the default `o2c.db`.

## Known limitations

- The MVP assumes a single currency; currency conversion and currency-specific balances are not modeled.
- Reconciliation requests use row locks on databases that support them; SQLite ignores those locks and serializes writes, so high-concurrency production workloads need PostgreSQL.
- Reconciliation audit records do not identify a user; API-key authentication is optional and offers no role-based authorization.
- Collection runs schedule records only. There is no background worker or email integration.
- Schema evolution is versioned, but legacy data must pass migration preflight checks; back up any existing database before migration.
- No request pagination is implemented for the legacy customer/order/invoice/payment list endpoints; receivables and collection actions are paginated.

## SDE-1 topics demonstrated

Relational modeling and constraints, REST contracts and status codes, fixed-precision money, multi-record validation, transactions, idempotency, audit trails, business-rule testing, and trade-offs between a simple SQLite MVP and production concurrency/migrations.
