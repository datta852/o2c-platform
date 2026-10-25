# O2C Platform Roadmap

This roadmap targets a small, demonstrable O2C MVP using FastAPI, SQLAlchemy, Pydantic, SQLite, and synthetic test data. Milestones are implemented in dependency order. No production database migration or real financial data operation is authorized by this roadmap.

## Milestones

| Milestone | State | Acceptance criteria |
|---|---|---|
| 0. Baseline and safe test harness | Verified | Existing user changes are preserved; tests use isolated synthetic data; roadmap/status are maintained. |
| 1. Financial record integrity | Implemented | Decimal money validation, integrity constraints, ownership/lifecycle checks, and protections around linked financial records. |
| 2. Payment reconciliation | Verified | Multi-invoice plans, unmatched/exception states, correction, idempotency, audit history, and balance checks. |
| 3. Receivables and collections | Verified | Outstanding/overdue API, configurable dunning rules, idempotent action scheduling, and recorded outcomes. |
| 4. Reproducible operations | Verified | Configurable database URL, SQLite foreign-key enforcement, Alembic migrations, backup documentation, and an isolated migration test. |
| 5. Portfolio quality | In progress | Business-rule tests, migration tests, optional API-key protection, OpenAPI checks, and a CI workflow are in place; broader HTTP-level CRUD tests remain. |

## Current implementation sequence

1. Expand endpoint-level CRUD/error tests and validate CI on a hosted runner.
2. Decide the local API authentication/authorization scope and document boundaries.
3. Consider PostgreSQL and a background worker when concurrency and dispatch needs justify them.

## Scope decisions

- Use fixed-precision `Decimal` values for money and synthetic data in tests.
- Keep the first release as an API product; Swagger UI and a reproducible API walkthrough make the workflows demonstrable without introducing a frontend framework.
- Avoid a background worker until scheduling requirements justify the operational burden. The first collection workflow can be an idempotent API-triggered scheduler run.
- Do not modify the developer's existing SQLite database during implementation or verification. Schema changes will be exercised only on isolated test databases; applying migrations to local user data requires a separate explicit decision.
- Use `unittest` for the current suite; Alembic is included because schema evolution is required, while pytest is unnecessary for this MVP.
