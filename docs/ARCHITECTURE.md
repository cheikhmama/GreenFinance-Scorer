# GreenFinance-Scorer — Target Architecture (v2)

> **Status: PROPOSED TARGET.** This document describes the architecture the project is moving
> towards. It is **not** a description of the code as it exists today. The current, binding
> conventions remain in [`/ARCHITECTURE.md`](../ARCHITECTURE.md) until each phase of
> [`TASKS.md`](TASKS.md) lands; when a phase lands, the root file is updated in the same commit
> and the matching section here is marked *Implemented*.
>
> Every section below includes a **Current → Target** mapping so that the gap stays explicit.

---

## 1. Purpose and actors

GreenFinance-Scorer is an ESG and carbon-footprint evaluation engine for companies, investment
portfolios and financial research. It turns sustainability reports (PDF / CSRD) and raw ESG
metrics into auditable, evidence-backed scores, and aggregates them at portfolio level together
with PCAF financed emissions.

| Role (`app/core/enums.py::Role`) | Responsibility |
|---|---|
| `ADMIN` | Onboarding (KYC), audit queue, publication, platform configuration |
| `ENTERPRISE` | Company profile, report submission, corrections |
| `AUDITOR` | Reviews evidence snippets, issues the audit opinion |
| `INVESTOR` | Portfolios, positions, aggregated ESG and PCAF analytics |
| `RESEARCHER` | Comparative analyses within a project's scope, explainability, dataset cross-validation |
| `INSTITUTION` (kept, D1) | Creates research projects, invites researchers, reviews their analyses |

The mission brief uses both `PORTFOLIO_MANAGER` and `INVESTOR` for the same actor. This document
standardises on **`INVESTOR`** (matches the `users` role list in the brief and the existing
`INVESTISSEUR` value).

---

## 2. Tech stack

| Layer | Target | Current | Note |
|---|---|---|---|
| API | FastAPI, Python 3.11+ | same | unchanged |
| ORM | SQLAlchemy 2.0 (via SQLModel) | SQLModel, sync sessions | API stays **sync**; ARQ jobs may use async sessions. A full async migration of the API isn't planned: it costs a lot and doesn't make anything faster, because the heavy work moves to the worker anyway. |
| Database | PostgreSQL 16 (+ pgvector image) | same | unchanged |
| Migrations | Alembic | same | one migration per task; no hand-edited schema |
| Cache / locks / rate limits | Redis 7 | same | now also the ARQ broker |
| Job queue | **ARQ** (Redis) | ARQ workers since task 4.1 (was FastAPI `BackgroundTasks` + `threading.Lock`) | see §6 |
| Document extraction | Docling, PaddleOCR, PyMuPDF, bge-m3 + FAISS, Gemini | same | moves to the worker image only |
| Scoring config | PyYAML + Pydantic schema | same | config content hashed and frozen per score (§5) |
| Explainability | Exact linear SHAP (closed form); `shap` library optional | per-indicator decomposition (`app/explainability/`) | see §7 |
| Frontend | React 19 + Vite, TanStack Query, Orval-generated client | same | unchanged |
| Packaging | **Docker multi-stage**, non-root | single stage, root, dev deps and tests in image | see §8 |

---

## 3. Domain model

Four domains, each owned by one module. Cross-domain access only goes through the owning
module's public functions (rule inherited from `/ARCHITECTURE.md` §1).

```
companies 1───* esg_reports 1───* esg_metrics
    │                │  └──────* carbon_emissions
    │                └───* scores ───> scoring_configs (content + hash)
    └───* portfolio_positions *───1 portfolios *───1 users
```

### 3.1 `companies` — master data (module `app/company`)

*Implemented in task 1.1* (ISIN/LEI check-digit validation: task 1.3).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `isin` | char(12), unique, nullable | ISO 6166 check digit validated |
| `lei` | char(20), unique, nullable | ISO 17442 check digit validated |
| `name` | text | |
| `sector` | text | NACE / GICS code preferred over free text |
| `country` | char(2) | ISO 3166-1 alpha-2 |
| `revenue` | numeric(20,2) + `revenue_currency` | needed for carbon intensity (WACI) |
| `enterprise_value` | numeric(20,2) + `ev_currency` + `ev_as_of` | **EVIC**, needed for the PCAF attribution factor |
| `status` | enum `RegistrationStatus`: `PENDING_ONBOARDING`, `INFO_REQUESTED`, `ACTIVE`, `REJECTED`, `SUSPENDED` (task 5.2) | registration then account lifecycle; replaces the `actif` flag |
| `registered_at`, `status_token_hash` (unique) | timestamp, char(64) | public registration (task 5.2): only the SHA-256 of the follow-up token is stored |
| `mandate_letter_path`, `mandate_letter_uploaded_at` | | mandate letter PDF, stored like reports (`mandats/{company_id}/…`) |
| `info_request_message`, `info_requested_at`, `info_response_message` | | info request (task 5.3) and the applicant's reply |
| `rejection_reason`, `rejected_at` | | a rejected request is kept, with its reason |
| `published_at` | timestamptz, nullable | last publication of the company's official score (was `date_publication`); a separate concept from onboarding |
| `owner_user_id` | FK users, nullable | |

*Current:* `entreprise` (`nom`, `secteur`, `pays`, `actif`, `date_publication`, …). No ISIN,
LEI, revenue or EVIC — PCAF can't be computed without them. `country` stays free text until
registration (task 1.3) validates ISO codes on input.

### 3.2 `esg_reports` — fiscal reporting (module `app/ingestion` → `app/reporting`)

*Implemented in task 1.1* (`official_score`, `coverage_rate`, `config_hash` columns exist; filled by tasks 1.6 and 3.1).
Task 1.5 adds `created_at`, makes `source_file` / `submitted_at` nullable for `DRAFT` (a CHECK
constraint requires both for every other status) and creates `app/reporting/` for the `/reports`
API with its role-based scope.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `company_id` | FK companies | |
| `fiscal_year` | int | indexed with `company_id` (not unique, see below) |
| `version`, `previous_report_id` | int, FK self | correction chain (already exists) |
| `status` | enum, see §3.2.1 | one status for the whole lifecycle, extraction included (task 5.1) |
| `official_score` | numeric(5,2), nullable | denormalised from the official `scores` row, set in the validation transaction |
| `coverage_rate` | numeric(5,4) | present indicators ÷ targeted indicators, weighted |
| `config_hash` | char(64), nullable | SHA-256 of the scoring config used for `official_score` |
| `checksum_sha256`, `source_file`, `original_filename` | | already exist |

#### 3.2.1 Status mapping

*Task 5.1* folds the extraction state back into `status` (tasks 1.1–4.7 kept it in a separate
`extraction_status` column; migration `a4c7e2d9b6f1` maps every pair and back):

| `status` until 5.1 | `extraction_status` until 5.1 | `status` since 5.1 |
|---|---|---|
| `DRAFT` | `NOT_STARTED` | `DRAFT` |
| `SUBMITTED` | `QUEUED` / `RUNNING` | `EXTRACTING` (queued = no `extraction_started_at`) |
| `SUBMITTED` | `FAILED` | `EXTRACTION_FAILED` |
| `SUBMITTED` | `DONE` | `AWAITING_ASSIGNMENT` |
| `PENDING_AUDIT` | `DONE` | `IN_AUDIT` |
| `PENDING_DECISION`, `REVISION_REQUESTED`, `VALIDATED`, `REJECTED` | `DONE` | unchanged |

`(company_id, fiscal_year)` is **indexed, not unique**: a company can file several report types
(annual, ESG, climate) for the same year, and each correction adds a version.

### 3.3 `esg_metrics` — data points

*Implemented in task 1.1.*

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `report_id` | FK esg_reports | unique with `metric_code` |
| `pillar` | enum `E`, `S`, `G` | |
| `metric_code` | text | must exist in the metric vocabulary |
| `raw_value` | text | as written in the source |
| `value` | numeric | normalised numeric value |
| `unit` | text | canonical unit per `metric_code` |
| `proof_text`, `proof_page`, `proof_id` | | evidence (guarantee: no value without proof) |
| `auditor_overridden` | bool | + `override_value`, `override_reason`, `overridden_by`, `overridden_at` |

*Current:* `indicateur_esg`. There is **no** uniqueness on `(rapport_id, code)` today — the
scoring engine silently keeps the last duplicate. Auditor overrides don't exist today: the
auditor can only issue an opinion.

Carbon data (`carbon_emissions`) keeps its structure: `scope` 1/2/3, `ghg_category`,
`tonnes_co2e`, `year`, `pcaf_data_quality` (1–5, **nullable**, derived from the extraction
method — the old hard-coded placeholder `3` is gone). *Implemented in task 2.3*, together with
`evidence`, `metric_coverage` and `discrepancy_flags` (renamed from `preuve_documentaire`,
`couverture_indicateur`, `signalement_ecart`); their JSON fields take the same English names since
task 4.7.

### 3.4 `portfolios` and `portfolio_positions` (module `app/investor`)

*Implemented in task 2.1*; amounts and FX rate in `numeric` / `Decimal` since task 2.3. Import
endpoint: task 2.2, which also adds `companies.ticker` (indexed, not unique). The cached
aggregates on `portfolios` stay empty until the recompute job (task 4.1); until then every figure
is computed on read.

| Table | Column | Notes |
|---|---|---|
| `portfolios` | `id`, `user_id`, `name`, `reference_currency`, `archived` | exists today as `portefeuille` |
| | `total_esg_score`, `waci`, `financed_emissions_tco2e`, `computed_at`, `config_hash` | cached aggregates, recomputed by a job |
| `portfolio_positions` | `id`, `portfolio_id`, `company_id` | exists today as `position_portefeuille` |
| | `identifier_type` (`ISIN`/`TICKER`), `identifier_raw` | kept even when no company matches |
| | `outstanding_amount` + `currency` | **required for PCAF** |
| | `weight` | derived from amounts, or imported directly |
| | `match_status` (`MATCHED`, `UNMATCHED`, `AMBIGUOUS`) | |

**Design correction to the brief.** Weights alone are enough for weighted-average scores and for
**WACI** (Σ wᵢ × emissionsᵢ / revenueᵢ). They are **not** enough for PCAF **financed emissions**,
which need the outstanding amount of each position:
`attribution_factorᵢ = outstanding_amountᵢ / EVICᵢ`, `financed_emissions = Σ attribution_factorᵢ × emissionsᵢ`.
An import that only has weights needs a total portfolio value so that amounts can be derived.

### 3.5 `users`

`id`, `email` (stored lower-case, unique index on `lower(email)`), `name`, `role`, `active`,
`password_hash`, `activated_at`, `avatar_path` (file storage, not a base64 column — done in
task 4.3; company logos are still data URIs in `companies.logo`).

### 3.6 `scoring_configs` and `scores`

| Table | Column | Notes |
|---|---|---|
| `scoring_configs` | `id`, `owner_user_id` (NULL = reference), `name`, `version` | |
| | `content_yaml` (text), `content_hash` (char(64), unique per owner) | **the content is stored, not only the file path** |
| `scores` | `report_id`, `config_id`, `global`, `e`, `s`, `g`, `coverage_rate`, `computed_at` | unique `(report_id, config_id)` |

*Implemented in task 3.1.* Columns are `global_score`, `environmental_score`, `social_score`,
`governance_score`. `content_hash` is SHA-256 of the canonical form (parsed YAML, re-serialised as
sorted JSON); uniqueness is one partial index for references (owner NULL) and one per owner.
`version` is informational. Configs migrated from before 3.1 whose original content could not be
recovered keep NULL content and hash (a CHECK ties them) and cannot be used for a calculation.

### 3.7 Audit, notifications and research supervision

*Renamed in task 4.7* (RENAME_PLAN §3e): `audit_opinions`, `audit_log`, `notifications`,
`institution_profiles`, `researcher_affiliations`, `projects` with `project_assignments`,
`project_companies`, `project_documents`, and `analyses` with `analysis_companies`. A project's
children are deleted with it (`CASCADE`); a project that still has analyses cannot be deleted
(`RESTRICT` — an analysis is delivered work); a new analysis version keeps pointing to its
predecessor, or to nothing if that row is gone (`SET NULL`). Audit log actions, resource types and
results are English codes (`login`, `User`, `success`); the frontend owns their French labels.

**API contract.** JSON field names equal the model attribute names on every endpoint; schemas read
the rows directly (`from_attributes`). URL paths, path/query parameters, multipart form fields and
enum values are still French.

---

## 4. Security standards

| Control | Target | Current state |
|---|---|---|
| Session | `__Host-` httpOnly cookie, `Secure`, `SameSite=Lax`, JWT HS256, 12 h | ✅ in place |
| CSRF | Signed double-submit (`X-CSRF-Token`) + Origin check on mutating requests | ✅ in place |
| Revocation | Per-user generation counter in Redis, fail-closed | ✅ in place |
| Email identity | Lower-cased at every entry point, case-insensitive uniqueness | ✅ task 1.2: normalized at the HTTP boundary, stored lower-case (CHECK constraint) with a unique index |
| Password policy | **12 characters minimum, 72 UTF-8 bytes maximum**, on every endpoint that sets a password (activation, reset, change) | ✅ task 1.2 (one shared validator; login unaffected, D4) |
| Rate limiting | Login, verify-password, **change-password**, email change, reset request, contact, URL import. Per account **and** per client IP (behind a trusted proxy). Atomic counters (`INCR` + `EXPIRE` in one Lua call) | ✅ task 1.2 (`app/core/redis.py::incrementer_fenetre`; login also per IP) |
| Sensitive profile changes | Changing email requires the current password and confirmation via a link sent to the new address | ✅ task 1.2 (`app/auth/email_change.py`; old address notified) |
| SSRF (URL import) | Scheme allow-list, DNS check with `not ip.is_global`, manual redirect revalidation, size cap, **total** download deadline | ✅ task 4.3 (`not is_global` + IPv4 embedded in IPv6 checked; 60 s deadline across redirects and the whole stream). Residual: DNS rebinding between check and connection (documented in `app/company/url_fetch.py`) |
| Search inputs | `%` and `_` typed by a user are characters, never LIKE wildcards | ✅ task 4.3 (`app/core/recherche.py::contient`, every `ilike`) |
| Error detail | Public endpoints never return exception messages | ✅ task 4.3 (`/health` returns a fixed body, details in the logs) |
| Secrets | Production refuses placeholder values and `*` CORS | ✅ in place |
| Tenant scoping | Every query on tenant data filters by owner / assignment inside the owning module | ✅ in place; kept as a rule |

---

## 5. Transactions and traceability

*Rules 1, 2 and 4 implemented for scoring and report decisions in task 1.6; rule 3 (locked
configuration content) comes with task 3.1.*

1. **One unit of work per HTTP request.** Domain functions never call `session.commit()`;
   the route (or the job) owns the transaction boundary. Helpers that "get or create" a row
   (e.g. the reference scoring config, today `obtenir_configuration_reference`) use
   `session.flush()` and `INSERT … ON CONFLICT DO NOTHING`, never `commit()`.
2. **Atomic validation.** Setting the report to `VALIDATED`, writing the `scores` row, setting
   `official_score`/`coverage_rate`/`config_hash`, the audit log entry and the notification all
   commit together, or not at all. Side effects outside the database (the synthesis PDF) run
   **after** the commit, as a job.
3. **Locked configuration.** Every score references a `scoring_configs` row whose
   `content_hash = sha256(canonical YAML bytes)`. Changing the YAML without changing the hash is
   impossible by construction; recalculating an old score always uses its stored content.
4. **Reads never write.** GET endpoints must not create rows.

---

## 6. Asynchronous processing (ARQ)

```
API (FastAPI) ──enqueue──> Redis (ARQ) ──> worker process(es)
     │                                        ├── extract_report(report_id)
     │                                        ├── generate_synthesis_pdf(report_id)
     │                                        ├── recompute_portfolio(portfolio_id)
     │                                        └── send_email(...)
     └── reads esg_reports.status / job result
```

- Job IDs are deterministic (`extract:{report_id}`), so a double submission doesn't start two jobs.
- Retries with backoff for transient errors (LLM 429/5xx); classified permanent errors set
  `status=EXTRACTION_FAILED` with a fixed error code (never `str(exc)`).
- The worker image contains torch/Docling/Paddle; the API image doesn't. *Done in task 4.2*
  (`Dockerfile` targets `api` and `worker`; the default worker runs on the `api` image).
- A cron job in the worker marks started extractions stuck longer than
  `EXTRACTION_TIMEOUT_MINUTES` as `EXTRACTION_FAILED`, replacing today's read-time detection.

*Implemented in task 4.1*, with two queues so an e-mail never waits behind a long extraction:
`arq:extraction` (one job at a time per worker) and `arq:queue` (e-mails, synthesis PDF, the cron).
Jobs are enqueued after the database commit. `recompute_portfolio` is not implemented: portfolio
figures are still computed on read. The separate worker image is task 4.2 (the API process
already no longer imports the extraction stack).

---

## 7. Scoring and explainability

- **Score.** For each pillar, a weighted mean of normalised indicator sub-scores (0–100). The
  global score is the weighted mean of the pillar scores. Missing indicators are excluded and
  their weight is renormalised (current rule), **and** `coverage_rate` is stored and displayed
  next to every score. An optional minimum-coverage threshold per config blocks publication
  below it.
- **Explainability.** The score is a linear function of the normalised sub-scores, so exact
  SHAP values have a closed form: `φᵢ = wᵢ_eff × (xᵢ − baselineᵢ)`, where `baselineᵢ` is the
  sector (or universe) mean and `wᵢ_eff` the effective weight after renormalisation. This needs
  no model training and no sampling, and it is reproducible. The `shap` library is only needed
  if a non-linear model (e.g. a researcher-trained predictor) is added later.
- **Waterfall.** baseline score → contribution per indicator, grouped by pillar → final score;
  contributions always sum exactly to `score − baseline`. *Implemented in task 3.2*; the `shap`
  library is not a dependency.

---

## 8. Deployment

- **Multi-stage Dockerfile**: `builder` (uv sync `--no-dev --frozen`) → `api` (slim runtime,
  non-root user, no tests, no ML stack) and `worker` (runtime + ML stack).
- `pytest`/`pytest-cov` move to the `dev` dependency group.
- The container entrypoint runs `alembic upgrade head` (or a one-shot `migrate` service).
- Postgres and Redis aren't published on the host outside development; Redis requires a password.
- Reverse proxy in front of the API sets `X-Forwarded-For`, and uvicorn is started with
  `FORWARDED_ALLOW_IPS=<proxy address>` so that `request.client.host` is the real client — the
  per-IP login limit and the contact limit rely on it and never read the header themselves.

---

## 9. Decisions (resolved 2026-09-29)

| # | Decision | Consequence |
|---|---|---|
| D1 | **Keep** the `INSTITUTION` role. | Research-project supervision stays as it is; the role is renamed with its module. |
| D2 | **Add** `PENDING_DECISION` for reports that have an auditor opinion and wait for the admin's sign-off. | Replaces `EN_VALIDATION`; the admin decision queue filters on it. |
| D3 | **Rename to English in place**, module by module, together with each phase's refactoring, using consolidated Alembic migrations. | Plan and boundary rules: [`RENAME_PLAN.md`](RENAME_PLAN.md). Completed in task 4.7 (tables, classes, JSON). |
| D4 | **12 characters minimum** (72 UTF-8 bytes maximum) on every password that is set: registration/activation, reset, change. | Existing hashes stay valid; nobody is forced to change a password. |
| D5 | **Gate self-registration** behind admin onboarding: a registered company starts in `PENDING_ONBOARDING`. | Nothing about the company is visible to other roles until an admin onboards it. |
