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

- [x] 0.1 Settle the open decisions D1–D5 in `docs/ARCHITECTURE.md` §9 (INSTITUTION role, `PENDING_DECISION` status, rename strategy, password policy rollout, public registration).
- [x] 0.2 Domain rename plan: map every table, column and enum from French to the target English names — [`RENAME_PLAN.md`](RENAME_PLAN.md) (boundary rules, task 1.1 glossary, later renames).
- [x] 0.3 Rule adopted: regenerate the OpenAPI client (`npm run api:generate`) whenever the HTTP contract changes and update the frontend in the same commit; CI `api:check` must stay green.

## Phase 1: Enterprise Management & Onboarding

- [x] 1.1 DB Models: Refactor `Company`, `ESGReport`, and `ESGMetric` models according to domain spec. (migration `21e17187789f`)
  - [x] Rename `entreprise`/`rapport_esg`/`indicateur_esg` to `companies`/`esg_reports`/`esg_metrics` per [`RENAME_PLAN.md`](RENAME_PLAN.md) §2, in one consolidated migration.
  - [x] Add `isin`, `lei` (check-digit validated), `revenue`, `enterprise_value` (EVIC) with currencies and dates, `status` (replaces `actif`; `published_at` keeps the publication timestamp).
  - [x] Split report `status` from `extraction_status`; add `DRAFT`, `PENDING_DECISION` (D2), `official_score`, `coverage_rate`, `config_hash`.
  - [x] Unique `(report_id, metric_code)` on metrics **[review]**; the extractor keeps the first exploitable occurrence of a repeated code.
  - [x] Auditor override fields on metrics (columns only; the auditor API is part of the audit workflow work).
  - [x] Explicit `ON DELETE` rules and indexes on every foreign key to or from the three tables (RENAME_PLAN §2.5).
  - Follow-ups: ISIN/LEI check-digit validation lands with registration input (1.3); `official_score`, `coverage_rate`, `config_hash` are filled by 1.6 and 3.1.
- [x] 1.2 Auth & Email Sanitization: Enforce lowercase email normalization and Pydantic password validation (12-72 bytes). (migration `7499c018ddb1`)
  - [x] Rename `utilisateur` → `users` (+ token tables, `Role` values) per RENAME_PLAN §3.
  - [x] Password policy per D4: 12 characters minimum on activation, reset and change; existing hashes untouched.
  - [x] Lower-case email on login, admin creation, profile update and reset; case-insensitive uniqueness (stored lower-case + CHECK + unique index); the migration refuses to run on existing case-duplicates **[review]**.
  - [x] One shared password validator used by activation, reset **and** change-password **[review]**.
  - [x] Rate-limit `POST /auth/changer-mot-de-passe` like verify-password **[review]**.
  - [x] Require the current password and a confirmation link to change email **[review]**; frontend confirmation page `/confirmer-email`.
  - [x] Atomic `INCR` + `EXPIRE` in rate-limit counters; add a per-IP limit behind a trusted proxy **[review]**.
  - [x] Found while testing: the activation e-mail linked to `/activer-compte`, a frontend page that did not exist — added (shares the reset page).
- [x] 1.3 Company Registration API: Implement Self-Service registration (`POST /api/v1/companies/register`).
  - [x] Public endpoint with the first English JSON contract; ISIN (ISO 6166) and LEI (ISO 17442) check digits validated when given (`app/company/identifiers.py`).
  - [x] Company `PENDING_ONBOARDING` + owner account without password; no activation link before onboarding (1.4); admins notified.
  - [x] Uniform `202` (no disclosure of known e-mails / ISIN / LEI); per-IP rate limit; trap field. No CAPTCHA — needs a third-party service decision before production.
  - [x] Admin actions can't bypass onboarding: reactivate only from `SUSPENDED`, suspend only from `ACTIVE`, no activation-link resend for a pending company; `statut` added to the company API contract.
  - [x] Frontend: public page `/inscription-entreprise` (linked from login), pending badge in the admin views.
- [ ] 1.4 Admin KYC API: Implement onboarding approval endpoint (`PATCH /api/v1/admin/companies/{id}/onboard`).
- [ ] 1.5 Fiscal Reporting Session API: Implement session creation and multi-tenant scoping (`POST /api/v1/reports`).
- [x] 1.6 Audit Queue & Atomic Validation: Refactor `valider_rapport` to run score calculation and status transition inside a single atomic BDD transaction. **[review]** (migration `834bf70ae1b9`)
  - [x] Remove `session.commit()` from `obtenir_configuration_reference`; `INSERT ... ON CONFLICT` on a new partial unique index (one reference row per version); existing duplicate rows merged by the migration.
  - [x] Stop GET endpoints (`score_officiel`, `score_public`, `score_calculable`) from creating rows (`trouver_configuration_reference` is read-only).
  - [x] Lock the report row (`SELECT ... FOR UPDATE`) during every decision and during score recalculation.
  - [x] Regression test: first validation under a reference version with no row yet and an uncomputable score leaves the report un-validated (verified to fail on the old code).
  - [x] `official_score` set in the validation transaction (backfilled for validated reports); the score uses the auditor override when one exists; the synthesis PDF is generated only after the commit.

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
- [ ] 4.7 Finish the English rename: remaining modules and the remaining French JSON field names (RENAME_PLAN §4), with the regenerated client and frontend.
- [ ] 4.6 Documentation: expand `README.md` (features, roles and permissions, architecture diagram, deployment, screenshots).
