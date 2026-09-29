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
- [x] 1.4 Admin KYC API: Implement onboarding approval endpoint (`PATCH /api/v1/admin/companies/{id}/onboard`). (migration `e7d012541fce`)
  - [x] `approve`: company `ACTIVE`, `onboarded_at` / `onboarded_by_id` recorded, owner's activation link sent — status and token in one commit, company row locked.
  - [x] `reject` (reason required): registration deleted, reason e-mailed, decision kept in the audit journal; the requester can register again.
  - [x] Decision: no ISIN/LEI or financial data required to approve (unlisted companies); revisit with PCAF (2.3).
  - [x] `envoyer_lien_activation` no longer commits: callers commit the token with the rest of their change.
  - [x] Frontend: approve / reject panel on a pending company's admin page; end-to-end test register → approve → activate → log in.
- [x] 1.5 Fiscal Reporting Session API: Implement session creation and multi-tenant scoping (`POST /api/v1/reports`). (migration `fa4f8e80e840`)
  - [x] `POST /reports` opens a `DRAFT` (no file); one draft per company, fiscal year and report type; ADMIN may open for a designated company.
  - [x] `GET /reports`, `GET /reports/{id}` scoped by role in one place (`app/reporting/sessions.py::perimetre`): enterprise → its company, auditor → assigned reports, admin → all; out of scope → 404.
  - [x] `POST /reports/{id}/submit` (same deposit logic as the one-step upload, bounded read) and `DELETE /reports/{id}` (discard a draft).
  - [x] Schema: `created_at` added; `source_file` / `submitted_at` nullable for drafts, CHECK for every other status. Existing lists and file downloads handle drafts.
  - [ ] Frontend screens to open / submit / discard a draft (the existing one-step deposit keeps working; drafts already show as "Brouillon").
- [x] 1.6 Audit Queue & Atomic Validation: Refactor `valider_rapport` to run score calculation and status transition inside a single atomic BDD transaction. **[review]** (migration `834bf70ae1b9`)
  - [x] Remove `session.commit()` from `obtenir_configuration_reference`; `INSERT ... ON CONFLICT` on a new partial unique index (one reference row per version); existing duplicate rows merged by the migration.
  - [x] Stop GET endpoints (`score_officiel`, `score_public`, `score_calculable`) from creating rows (`trouver_configuration_reference` is read-only).
  - [x] Lock the report row (`SELECT ... FOR UPDATE`) during every decision and during score recalculation.
  - [x] Regression test: first validation under a reference version with no row yet and an uncomputable score leaves the report un-validated (verified to fail on the old code).
  - [x] `official_score` set in the validation transaction (backfilled for validated reports); the score uses the auditor override when one exists; the synthesis PDF is generated only after the commit.

## Phase 2: Investment Portfolios & Carbon Module (PCAF)

- [x] 2.1 DB Models: Implement `Portfolio` and `PortfolioPosition` models. (migration `be63d4541f22`)
  - [x] Renamed to `portfolios` / `portfolio_positions` with English columns (RENAME_PLAN §3b).
  - [x] Extended with `identifier_type`, `identifier_raw`, `match_status`, `weight`; `company_id` nullable for lines kept unmatched (CHECK ties it to `match_status`); cached aggregates on `portfolios` (filled by the recompute job, task 4.1 — see 2.3).
  - [x] Aggregation counts unmatched lines in the total but never scores them (coverage drops, scores don't); sector breakdown skips them.
  - [x] `ON DELETE`: `portfolios.user_id` CASCADE, `portfolio_positions.portfolio_id` CASCADE + index.
  - [x] Found while renaming: three attribute writes (archive, rename, close position) that mypy cannot see on SQLModel — fixed; archive/close were already covered by tests, a rename test was added (verified to fail on the old code); one more timing-flaky test made deterministic.
- [x] 2.2 Portfolio API: CSV/JSON upload endpoint for portfolio positions mapped by ISIN/Ticker. (migration `161f99c1f733`)
  - [x] `POST /portfolios/{id}/positions/import` (multipart `file` + optional `total_value`, `app/investor/importation.py`): CSV (`,` `;` or tab, decimal comma with `;`) or JSON, 1 MB / 5 000 lines max.
  - [x] All-or-nothing import with a per-line error report (`fields.line_<n>`, `fields.file`); unmatched lines kept (`UNMATCHED` / `AMBIGUOUS`), shown with their raw identifier and never scored.
  - [x] Weight-only imports require a total portfolio value (PCAF needs amounts); amount and weight modes cannot be mixed; weights sum to 1 ± 0.001.
  - [x] Matching only against **published** companies (an import never reveals a pending one); a matched company follows the manual-entry rules (`ACTIVE`, minimum investment).
  - [x] Scope choice: import only into an **empty**, non-archived portfolio — replacing positions that have a history would destroy it (re-import: later, with the recompute job of task 4.1).
  - [x] `companies.ticker` (indexed, never unique: one symbol can exist on several exchanges → `AMBIGUOUS`); `PATCH /admin/companies/{id}/identifiers` (partial, English contract) + admin form; ISIN/LEI/ticker added to the company contract.
  - [x] Frontend: import form in the empty-portfolio state; `ApiError.fields` exposed.
- [x] 2.3 PCAF Carbon Engine: Implement real Scope 1, 2, 3 carbon footprint calculations (replacing placeholder scores). **[review]** (migration `c3a9f2d71b58`)
  - [x] Attribution factor (amount / EVIC), financed emissions per scope, carbon footprint, WACI, weighted data quality — pure engine `app/carbon/pcaf.py`, assembled by `app/investor/carbon.py`, served by `GET /portfolios/{id}/carbon` (English contract) + carbon card on the portfolio page.
  - [x] Scope 3 reported separately; missing data excluded and counted in coverage, never zero (each excluded line carries its reason: `UNMATCHED`, `NO_VALIDATED_REPORT`, `MISSING_EMISSIONS`, `MISSING_EVIC`).
  - [x] Remove `PLACEHOLDER_SCORE_QUALITE_PCAF = 3`; `pcaf_data_quality` nullable and derived from the extraction method (reported 2, calculated 3, estimated 4 — never 1 without assurance information); existing rows re-derived by the migration.
  - [x] Use `Decimal` for monetary amounts and FX (`numeric` columns; amounts at most two decimals, refused otherwise); return `422` (`devise_non_prise_en_charge`) for a currency missing from the rates file instead of a `500` **[review]**.
  - [x] Revenue and EVIC had no input path: `GET`/`PUT /admin/companies/{id}/financials` + admin form (task 1.4 decision revisited: still not required at onboarding, PCAF reports the gap).
  - [x] Renamed `donnee_carbone` → `carbon_emissions`, `preuve_documentaire` → `evidence`, `couverture_indicateur` → `metric_coverage`, `signalement_ecart` → `discrepancy_flags` (RENAME_PLAN §4); `carbon_emissions.proof_id` gets `ON DELETE CASCADE` + index (it had neither).
  - [x] Scope choices: computed on read, active positions only; the cached aggregates on `portfolios` are left for the recompute job of task 4.1 (they need the worker to stay fresh when a new score is published).

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
