# Implementation Task Tracker

Target design: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/WORKFLOWS.md`](WORKFLOWS.md).
Current binding conventions: [`/ARCHITECTURE.md`](../ARCHITECTURE.md).

Rules for every task:
- One Alembic migration per schema change, with a working `downgrade()`.
- Tests land in the same commit (unit for pure logic, integration for routes and transactions).
- When a phase is complete, update `/ARCHITECTURE.md` and mark the section *Implemented* in
  `docs/ARCHITECTURE.md`.
- Tasks marked **[review]** fix a finding from the project review (2026-09-28).

## Phase 0: Decisions and groundwork

- [ ] 0.1 Settle the open decisions D1–D5 in `docs/ARCHITECTURE.md` §9 (INSTITUTION role, `PENDING_DECISION` status, rename strategy, password policy rollout, public registration).
- [ ] 0.2 Domain rename plan: map every table, column and enum from French to the target English names, and write it down as a checklist (one migration per module).
- [ ] 0.3 Regenerate the OpenAPI client (`npm run api:generate`) after each rename and update the frontend in the same commit; CI `api:check` must stay green.

## Phase 1: Enterprise Management & Onboarding

- [ ] 1.1 DB Models: Refactor `Company`, `ESGReport`, and `ESGMetric` models according to domain spec.
  - [ ] Add `isin`, `lei` (check-digit validated), `revenue`, `enterprise_value` (EVIC) with currencies and dates, `status`.
  - [ ] Split report `status` from `extraction_status`; add `DRAFT`, `official_score`, `coverage_rate`, `config_hash`.
  - [ ] Unique `(report_id, metric_code)` on metrics **[review]** (the scoring engine silently keeps the last duplicate today).
  - [ ] Auditor override fields on metrics.
- [ ] 1.2 Auth & Email Sanitization: Enforce lowercase email normalization and Pydantic password validation (12-72 bytes).
  - [ ] Lower-case email on login, admin creation, profile update and reset; unique index on `lower(email)`; data migration that reports existing case-duplicates before adding the index **[review]**.
  - [ ] One shared password validator used by activation, reset **and** change-password (change-password has none today) **[review]**.
  - [ ] Rate-limit `POST /auth/changer-mot-de-passe` like verify-password **[review]**.
  - [ ] Require the current password and a confirmation link to change email **[review]**.
  - [ ] Atomic `INCR` + `EXPIRE` in rate-limit counters; add a per-IP limit behind a trusted proxy **[review]**.
- [ ] 1.3 Company Registration API: Implement Self-Service registration (`POST /api/v1/companies/register`).
- [ ] 1.4 Admin KYC API: Implement onboarding approval endpoint (`PATCH /api/v1/admin/companies/{id}/onboard`).
- [ ] 1.5 Fiscal Reporting Session API: Implement session creation and multi-tenant scoping (`POST /api/v1/reports`).
- [ ] 1.6 Audit Queue & Atomic Validation: Refactor `valider_rapport` to run score calculation and status transition inside a single atomic BDD transaction. **[review]**
  - [ ] Remove `session.commit()` from `obtenir_configuration_reference` (`app/scoring/engine.py:64`); use `flush()` + `ON CONFLICT`.
  - [ ] Stop GET endpoints (`score_officiel`, `score_public`) from creating rows.
  - [ ] Lock the report row during validation.
  - [ ] Regression test: first validation on an empty `configuration_ponderation` table with an uncomputable score must leave the report un-validated.

## Phase 2: Investment Portfolios & Carbon Module (PCAF)

- [ ] 2.1 DB Models: Implement `Portfolio` and `PortfolioPosition` models.
  - Note: both exist today (`Portefeuille`, `PositionPortefeuille`). This task **extends** them with `identifier_type`, `identifier_raw`, `weight`, `match_status` and cached aggregates, and renames them per 0.2.
- [ ] 2.2 Portfolio API: CSV/JSON upload endpoint for portfolio positions mapped by ISIN/Ticker.
  - [ ] All-or-nothing import with a per-line error report; unmatched lines kept.
  - [ ] Weight-only imports require a total portfolio value (PCAF needs amounts).
- [ ] 2.3 PCAF Carbon Engine: Implement real Scope 1, 2, 3 carbon footprint calculations (replacing placeholder scores). **[review]**
  - [ ] Attribution factor (amount / EVIC), financed emissions per scope, carbon footprint, WACI, weighted data quality.
  - [ ] Scope 3 reported separately; missing data excluded and counted in coverage, never zero.
  - [ ] Remove `PLACEHOLDER_SCORE_QUALITE_PCAF = 3` (`app/ingestion/extractor.py:142`); make `pcaf_data_quality` nullable and derive it from the extraction.
  - [ ] Use `Decimal` for monetary amounts and FX; return `422` for an unknown currency instead of a `500` **[review]**.

## Phase 3: Researcher Tooling & SHAP Explainability

- [ ] 3.1 YAML Config Versioning: Hash and store YAML configuration files on every calculation. **[review]**
  - [ ] Store `content_yaml` + `content_hash` on `scoring_configs`; recalculation always uses the stored content.
  - [ ] Store `coverage_rate` with every score and show it next to the score; optional `min_coverage` per config **[review]**.
- [ ] 3.2 SHAP Explainability Module: Implement feature attribution endpoints for score decomposition.
  - [ ] Exact linear SHAP with a sector baseline; contributions must sum to `score − baseline` (property test).
  - [ ] Waterfall endpoint and frontend chart.
- [ ] 3.3 Public dataset cross-validation (Kaggle / CDP / GRI): staging import, ISIN/LEI matching, Spearman and MAE report.

## Phase 4: Architecture & Quality

- [ ] 4.1 ARQ/Redis Task Queue: Offload Docling extraction to asynchronous background tasks. **[review]**
  - [ ] Worker process with deterministic job IDs, retries with backoff, and a cron job that fails stuck extractions.
  - [ ] Replace `BackgroundTasks` + `threading.Lock` (`app/ingestion/extractor.py:60`); move synthesis PDF and emails to jobs.
- [ ] 4.2 Docker Multi-Stage Refactoring: Production build cleanup (non-root user, slim image). **[review]**
  - [ ] Separate `api` and `worker` images; `uv sync --no-dev --frozen`; no `tests/` in the image.
  - [ ] Move `pytest`, `pytest-cov` to the `dev` group.
  - [ ] Run `alembic upgrade head` at deploy; don't publish Postgres/Redis ports outside dev; Redis password.
- [ ] 4.3 Hardening leftovers **[review]**
  - [ ] `/health` returns a fixed message, not `str(exc)`.
  - [ ] URL import: block every non-global IP (`not ip.is_global`) and add a total download deadline.
  - [ ] Escape `%` and `_` in `ilike` search inputs.
  - [ ] Store avatars as files instead of base64 in the user row.
  - [ ] Frontend: global `401` handler that sends the user to the login page.
- [ ] 4.4 CI **[review]**
  - [ ] Run on `pull_request` + push to `main` only; add a `concurrency` group that cancels superseded runs; upgrade `setup-uv`.
  - [ ] Fail when Alembic has more than one head.
- [ ] 4.5 Test coverage **[review]**
  - [ ] Backend: extraction pipeline (with a stubbed LLM), semantic search, completeness, explainability, activation, avatar, CSRF middleware in isolation.
  - [ ] Frontend: at least one flow test per user space (currently only auth, contact, prototype, `RequireRole`).
- [ ] 4.6 Documentation: expand `README.md` (features, roles and permissions, architecture diagram, deployment, screenshots).
