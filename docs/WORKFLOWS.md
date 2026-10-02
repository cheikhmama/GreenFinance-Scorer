# GreenFinance-Scorer — Target Workflows (v2)

> **Status: PROPOSED TARGET.** State machines and lifecycles for the redesign described in
> [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Each workflow notes what exists today and what
> changes. Names follow the English domain model — tables, classes and JSON fields use them since
> task 4.7; French equivalents are listed where URL paths, query parameters or enum values still
> differ.

Conventions used below:
- **Actor** — the role allowed to trigger the transition. Any other role gets `403`; a user of
  the right role who doesn't own the resource gets `404` (no existence leak).
- **Tx** — what commits together in one database transaction.
- **Job** — work enqueued on ARQ, executed by the worker after the transaction commits.

---

## 1. Enterprise management

### 1.1 Company lifecycle

```
            register (public)               approve (ADMIN)
   ∅ ─────────────────────────> PENDING_ONBOARDING ────────────────> ACTIVE
                                 │   ▲       │                          │  ▲
                request info     │   │ reply │ reject       suspend     │  │ reactivate
                (ADMIN)          ▼   │       ▼ (ADMIN)      (ADMIN)     ▼  │ (ADMIN)
                           INFO_REQUESTED   REJECTED                SUSPENDED
                                 │   (reject / approve      │
                                 │    also from here)       │ register again, same identifiers
                                 └──────────────────────────┴──────────> PENDING_ONBOARDING
```

*Task 5.2*: a rejected request is kept (`REJECTED`, reason) instead of deleted, and the applicant
follows the request on a public page opened with a token received by e-mail.

| Transition | Actor | Preconditions | Tx | Job |
|---|---|---|---|---|
| register (*tasks 1.3, 5.2, 5.10, 5.11*, multipart) | public | Identity (legal name, sector, country, **tax ID** checked by country — NIF / SIREN / EIN / other —, ISIN/LEI with valid check digits if given, website), contact name and **professional** e-mail (no public webmail; on the website's domain or a sub-domain when a website is given — *task 5.11*), **mandate letter PDF** (≤ 5 MB, PDF signature, not encrypted); email, ISIN, LEI and (country, tax ID) not already known — or all of them pointing to one `REJECTED` request, which is then reopened; 3 requests per IP per hour; trap field empty. Same `202` answer whatever the outcome — the requester learns it by e-mail | company `EMAIL_VERIFICATION_PENDING` (or the reopened one — a request never confirmed is reopened too) with a 6-digit code (*task 5.11*); follow-up token, acknowledgment and admin notification wait for *verify e-mail* + owner user `ENTERPRISE` **without password** + mandate letter stored + audit log (`company_registered` / `registration_resubmitted`) | e-mail with the 6-digit code (or « not processed » e-mail on a duplicate). The activation link is sent at onboarding, never before |
| verify e-mail (*task 5.11*, `POST /companies/registration/verify-email`) | public | the code e-mailed at registration: 30 min, 5 attempts, one answer `code_invalide` for every failure; resend (`/resend-code`) at most once a minute; IP limits | status `PENDING_ONBOARDING`, `email_verified_at`, code cleared, follow-up token, audit `registration_email_verified`, admin notification `ENTREPRISE_INSCRITE` | acknowledgment e-mail with the follow-up link |
| follow request (*task 5.2*, `POST /companies/registration-status`) | public, token in the body | token known | — (read only: status, info request, rejection reason) | — |
| reply to an info request (*task 5.2*, `POST /companies/registration-status/reply`) | public, token | `INFO_REQUESTED` (row locked); new mandate letter PDF; optional message ≤ 2 000 characters; 3 replies per IP per hour | status `PENDING_ONBOARDING`, new mandate letter, message kept, audit log `registration_info_provided`, admin notification `ENTREPRISE_INFOS_COMPLETEES` | — |
| onboard — approve (*task 1.4*) | ADMIN | status `PENDING_ONBOARDING` or `INFO_REQUESTED` (row locked); owner account present. **No ISIN/LEI or financial data required** — many unlisted companies have none; the admin may complete the profile first, and PCAF (task 2.3) asks for figures when it needs them | status `ACTIVE`, onboarded_by/at, activation token (valid **72 hours** since task 5.2), audit log | activation e-mail to the owner |
| onboard — reject (*tasks 1.4, 5.2*) | ADMIN | status `PENDING_ONBOARDING` or `INFO_REQUESTED`; a reason is required | status `REJECTED` with `rejection_reason` / `rejected_at`, owner account deactivated (it never had a password), audit log | e-mail with the reason; the reason stays on the follow-up page; registering again with the same identifiers reopens the request |
| KYC review (*task 5.3*, `GET /admin/companies/{id}/kyc`) | ADMIN | — | read only, recomputed on every call: GLEIF registration (`ISSUED`, entity `ACTIVE`) and legal-name match (legal or other known name; legal forms, accents and case ignored), contact e-mail domain vs declared website (public webmail always a gap), mandate letter present. Each check: result `PASSED` / `FAILED` / `NOT_VERIFIABLE` (GLEIF unreachable, 5 s timeout) / `NOT_APPLICABLE`, detail, source. **Checks inform the decision, they never block it** | — |
| request info (*task 5.3*) | ADMIN | status `PENDING_ONBOARDING` or `INFO_REQUESTED`; a message is required | status `INFO_REQUESTED`, message and date stored, previous reply cleared, **new follow-up token** (the old one stops working), audit log `registration_info_requested` | e-mail with the message and the new follow-up link |
| suspend / reactivate | ADMIN | — | status change, audit log, sessions of the owner revoked on suspend | — |

**Rules:**
- A `PENDING_ONBOARDING`, `INFO_REQUESTED` or `REJECTED` company is invisible to every role except
  `ADMIN`; its applicant only sees it through the follow-up page.
- Only an `ACTIVE` company can submit reports or receive new investments.
- Opening the activation link (`POST /auth/activer-compte`, 72 hours, single use) sets the
  password **and opens the session**: the user lands in their workspace without a separate login.
  An expired link is renewed by the admin only, never self-service.
- A `SUSPENDED` company stays visible to investors who already hold it (so they see the
  warning), but can't receive new positions.
- Onboarding and **publication** are separate: `published_at` records when the admin last
  published the company's official score, and only published companies appear in the
  investor and researcher catalogues.

*Current:* no public registration; the admin creates the user, the user activates by email link
(`app/auth/activation.py`). Publication is a separate `date_publication` timestamp set by the
admin. Decision D5 gates self-registration behind this onboarding step.

**Investor and researcher sign-up** (*task 5.10*).

| Transition | Actor | Preconditions | Tx | Job |
|---|---|---|---|---|
| request access (`POST /access-requests`) | public | full name, e-mail, organisation, investor type (investor) or research domain (researcher); e-mail unknown, or belonging to a `REJECTED` request (reopened); 3 requests per IP per hour; trap field empty. Same `202` whatever the outcome | user with the role and **no password** + `access_requests` row `PENDING_APPROVAL` + audit `access_requested` / `access_request_resubmitted` + admin notification `DEMANDE_ACCES` | acknowledgment e-mail (or « not processed » e-mail) |
| approve (`PATCH /admin/access-requests/{id}`) | ADMIN | `PENDING_APPROVAL`; e-mail service up | `APPROVED`, decider and date, activation token, audit `access_request_approved` | activation e-mail |
| reject (same route) | ADMIN | `PENDING_APPROVAL`; reason required | `REJECTED` with the reason, account deactivated, audit `access_request_rejected` | refusal e-mail with the reason |

### 1.2 Report lifecycle

One status carries the whole lifecycle, extraction included (*task 5.1*; tasks 1.1–4.7 kept the
extraction state in a separate `extraction_status` column).

```
   create session      upload/submit           extraction done                auditor assigned
 ∅ ─────────> DRAFT ──────────────> EXTRACTING ───────────────> AWAITING_ASSIGNMENT ─────────────> IN_AUDIT
                ▲                    │      ▲                                                         │
                │        failed      │      │ retry (ADMIN)                                           │ opinion
                │                    ▼      │                                                         ▼
                │              EXTRACTION_FAILED                                              PENDING_DECISION*
                │                                                                             │   │   │
                │  new version (ENTERPRISE, new row)        request revision (ADMIN)          │   │   │ reject (ADMIN)
                └─────────────────────────────── REVISION_REQUESTED <─────────────────────────┘   │   └──────> REJECTED
                                                                                                  │ validate (ADMIN)
                                                                                                  ▼
                                                                                              VALIDATED
```
\* `PENDING_DECISION` was added by decision D2 (replaces `EN_VALIDATION`).

**Draft analysis** (*task 5.8*). Attaching a PDF to a `DRAFT` moves it to `EXTRACTING` **without**
`submitted_at`; the pipeline brings it back to `DRAFT` (with its completeness checklist, or with
the failure cause) instead of `AWAITING_ASSIGNMENT` / `EXTRACTION_FAILED`. Only the explicit
submission sets `submitted_at` and moves the analysed draft to `AWAITING_ASSIGNMENT`: from then on
the report is locked. The one-step deposit, URL import and corrections still submit at once.

Within `EXTRACTING`, a job still in the queue has no `extraction_started_at`; a running one has
it. The supervision cron fails a started run older than `EXTRACTION_TIMEOUT_MINUTES`
(`delai_depasse`) and re-enqueues a queued one whose job was lost. The pipeline only acts on an
`EXTRACTING` report, so a replayed job never moves a report backwards.

**Enterprise view.** The enterprise sees `EXTRACTING`, `AWAITING_ASSIGNMENT`, `IN_AUDIT` and
`PENDING_DECISION` as one state, "En cours d'examen 🔒"; the other states are shown as they are.
A draft whose file is being analysed (not submitted) reads "Analyse du fichier".
Internal roles see the detailed state.

| Transition | Actor | Preconditions | Tx | Job |
|---|---|---|---|---|
| create session (*tasks 1.5, 5.9*, `POST /reports`) | ENTERPRISE (own ACTIVE company), or ADMIN with `company_id` | fiscal year between 2000 and the current year; optional financials of the year (`currency` required with an amount; EVIC dated at year end by default); no other active declaration (`declaration_en_cours`) and fiscal year not already validated, whatever the report type (`exercice_deja_valide`) — same rule for the one-step deposit and the URL import, not for corrections (*task 5.9*); no other unsubmitted report for `(company, fiscal_year, report type)` (partial unique index on `submitted_at IS NULL`, *task 5.8*) | report `DRAFT`, no file | — |
| attach file (*task 5.8*, `POST /reports/{id}/file`) | ENTERPRISE owner or ADMIN | `DRAFT` (row locked); PDF valid (magic bytes, size cap, checksum not used by another report) — same code path as the one-step deposit | status `EXTRACTING` (queued), file stored, checksum; **no** `submitted_at` | job `extract_report`; on success back to `DRAFT` + `RAPPORT_ANALYSE_TERMINEE`, on failure back to `DRAFT` with the cause |
| LEI verification (*task 5.9*, `GET /company/lei-verification`) | ENTERPRISE | — | — (live GLEIF check of registration and legal name: `PASSED`, `FAILED`, `NOT_VERIFIABLE`, `NOT_APPLICABLE` without a LEI; nothing stored) | — |
| checklist (*task 5.8*, `GET /reports/{id}/checklist`) | any role within scope | — (empty until an analysis succeeded) | — (found / expected per group, never values) | — |
| submit (*tasks 1.5, 5.8*, `POST /reports/{id}/submit`) | ENTERPRISE owner or ADMIN | `DRAFT` (row locked) with a file whose analysis succeeded (`fichier_manquant`, `analyse_non_terminee`); company `ACTIVE` | `submitted_at` (lock), status `AWAITING_ASSIGNMENT`, admin notifications, journal `report_submitted` (file SHA-256) | job `generate_synthesis_pdf` |
| discard (*task 1.5*, `DELETE /reports/{id}`) | ENTERPRISE owner or ADMIN | `DRAFT` | draft deleted, period free again | — |
| extraction | worker | `EXTRACTING` | an `extraction_runs` row (Docling version, LLM model, prompt version — *task 5.5*) opened at the start and closed with the outcome; metrics + carbon rows (each with its run id and the boxes of its cited value) + evidence replaced as a whole, coverage rows, status `AWAITING_ASSIGNMENT` (or `EXTRACTION_FAILED` with a fixed cause), **pre-score** (non-official score with the reference config) | `generate_synthesis_pdf` |
| retry extraction | ADMIN | `EXTRACTION_FAILED` | status `EXTRACTING` (queued), error cleared | job `extract_report` |
| assign auditor | ADMIN | `AWAITING_ASSIGNMENT` | `auditor_id`, `assigned_at`, status `IN_AUDIT`, notification | — |
| review a value (*task 5.6*, `POST /audit/rapports/{id}/reviews`) | AUDITOR (assigned) | `IN_AUDIT`; the value belongs to this report; `OVERRIDDEN` needs the new value, `OVERRIDDEN` / `NOT_FOUND` a reason category | an **append-only** `metric_reviews` row (original value, new value, reason, comment, auditor) + the value's current `review_status` / `audited_value`; deciding again adds a row | — |
| audit opinion | AUDITOR (assigned) | `IN_AUDIT`; every metric and carbon value reviewed (`422 revue_incomplete` otherwise — *task 5.7*); a comment unless `FAVORABLE` | opinion row (`FAVORABLE`, `FAVORABLE_WITH_RESERVATIONS`, `CORRECTION_REQUIRED`, `UNFAVORABLE` — *task 5.6*), status `PENDING_DECISION`; the review is closed | — |
| pre-score (*task 5.6*, `GET /audit/rapports/{id}/pre-score`) | AUDITOR (assigned) | opinion already submitted (`409 avis_requis` before) | — (reference score with the reviewed values, never official) | — |
| **validate** | ADMIN | `PENDING_DECISION`; score computable; coverage ≥ config threshold | see §1.3 | `generate_synthesis_pdf`, notification email |
| reject | ADMIN | `PENDING_DECISION` | status `REJECTED`, reason, notification | — |
| request revision | ADMIN | `PENDING_DECISION` | status `REVISION_REQUESTED`, reason, notification | — |
| new version | ENTERPRISE | `REVISION_REQUESTED` | new report row with its file, `version+1`, `previous_report_id`, status `EXTRACTING` | job `extract_report` |

*Current:* statuses `ENVOYE → EN_EXTRACTION → AFFECTE_AUDITEUR → EN_VALIDATION → VALIDE / REJETE / DEMANDE_CORRECTION`;
no draft state; no auditor overrides. Extraction ran as a FastAPI `BackgroundTasks` in the API
process until task 4.1; it now runs in the extraction worker.

**Separation of duties** (*task 5.6*): only the assigned auditor reviews values and issues the
opinion, and only while the report is `IN_AUDIT` — the opinion closes the review. The admin reads
the review log (`GET /admin/rapports/{id}/reviews`) but never writes to it, and decides only from
`PENDING_DECISION`. The auditor sees the pre-score only after the opinion, so the number never
steers the review. The enterprise doesn't see review states or audited values until the report is
validated.

### 1.3 Atomic score publication

All of the following happen in **one** transaction. If any step raises, nothing is committed and
the report stays in `PENDING_DECISION`.

1. Lock the report row (`SELECT … FOR UPDATE`) and re-check the status.
2. Resolve the reference `scoring_configs` row by content hash (get-or-create with
   `flush()` / `ON CONFLICT`, **never** `commit()`).
3. Compute the score from the effective metric values: the audited value of an `OVERRIDDEN` value,
   nothing for a `NOT_FOUND` one (it counts as not reported), else the extracted value.
4. Insert the `scores` row; set `official_score`, `coverage_rate`, `config_hash` on the report.
5. Set status `VALIDATED`; write the audit log entry and the in-app notification.
6. `COMMIT`.
7. After commit: enqueue `generate_synthesis_pdf` and the notification email.

*Implemented in task 1.6.* It fixed a bug where `obtenir_configuration_reference` committed in
the middle of `valider_rapport`, which could persist `VALIDE` without a score. Until the job
queue exists (task 4.1), step 7 runs synchronously right after the commit, as a best-effort step
that can never undo the validation.

*Task 3.1:* step 2 registers the reference by the hash of the file's content and step 3 always
parses the **stored** `content_yaml`; step 4 also stores `coverage_rate` and `config_hash`. If the
config sets `min_coverage` and the report's coverage is below it, step 3 raises
`couverture_insuffisante` and nothing is committed — the admin sees the coverage and the minimum
before deciding (`GET /admin/rapports/{id}/score-verification`). A report's official score is its
**latest** score under a reference config, so publishing a new methodology never hides the scores
already published.

---

## 2. Portfolio and investment analytics

### 2.1 Lifecycle

```
 create ──> EMPTY ──import positions──> IMPORTED ──match──> MATCHED ──enqueue──> COMPUTING ──> COMPUTED
                         ▲                                     │                                 │
                         └────────── edit / re-import ─────────┴──────────── (marks STALE) ──────┘
                                                                    new official score for a held company → STALE
```

### 2.2 Position import (ISIN / ticker, weight or amount)

Input: CSV or JSON, one line per holding.

| Column | Required | Notes |
|---|---|---|
| `identifier` | yes | ISIN (check digit validated) or ticker |
| `identifier_type` | no | `ISIN` (default) or `TICKER` |
| `outstanding_amount` + `currency` | one of amount/weight | required for PCAF financed emissions |
| `weight` | one of amount/weight | 0–1; if only weights are given, `total_value` is required at import to derive amounts |

Steps:
1. Parse and validate every line; the whole file is rejected with a per-line error report if
   any line is invalid (no partial import).
2. Match identifiers to `companies` (`ACTIVE` only): `MATCHED`, `UNMATCHED`, `AMBIGUOUS`
   (a ticker listed on several exchanges). Unmatched lines are kept, never dropped silently.
3. Normalise: weights must sum to 1 ± 0.001 over all lines; amounts converted to the portfolio
   reference currency with the FX rate frozen at import.
4. Tx: replace positions, set status `MATCHED`. Job: `recompute_portfolio`.

*Implemented in task 2.2* (`POST /portfolios/{id}/positions/import`, `app/investor/importation.py`),
with these differences from the target:
- import only into an **empty** portfolio (`portefeuille_non_vide` otherwise) — no replace and no
  status/job yet (recompute job: task 4.1);
- matching is against **published** companies (an unpublished one gives `UNMATCHED`); a matched
  company that is not `ACTIVE` or below its minimum investment is a line error, like a manual entry;
- each created line is an open position starting today; errors are returned as `fields.line_<n>`
  (CSV header = line 1) and `fields.file`.
Tickers are set by an admin (`PATCH /admin/companies/{id}/identifiers`).

### 2.3 Metric aggregation (job `recompute_portfolio`)

For the matched positions whose company has an **official** score:

- `total_esg_score = Σ wᵢ × scoreᵢ / Σ wᵢ` over covered positions.
- `esg_coverage = Σ wᵢ (covered) / Σ wᵢ (all)` — always shown next to the score.
- Pillar scores aggregated the same way.
- The config hash of every score used is recorded; if they differ, the result is flagged
  "mixed methodology".

### 2.4 PCAF carbon (Scope 1, 2, 3)

Per position *i*, for each scope *s* with reported emissions `Eᵢ,ₛ` (tCO₂e) for the matching
fiscal year:

| Metric | Formula | Needs |
|---|---|---|
| Attribution factor | `AFᵢ = outstanding_amountᵢ / EVICᵢ` (listed equity & corporate bonds, PCAF Part A) | amount, EVIC |
| Financed emissions | `FEₛ = Σ AFᵢ × Eᵢ,ₛ` | |
| Carbon footprint | `Σₛ FEₛ / portfolio_value` × 1 M (tCO₂e / M invested) | |
| WACI | `Σ wᵢ × (Eᵢ,₁ + Eᵢ,₂) / revenueᵢ` (tCO₂e / M revenue) | weight, revenue |
| Data quality | amount-weighted mean of `pcaf_data_quality` (1 = best, 5 = worst) | |

Rules:
- Scope 3 is reported **separately** from Scopes 1+2, never summed silently (PCAF guidance).
- Every amount is converted to one currency before division; EVIC and amount use the same
  currency and a date as close as possible to the reporting year.
- A position without emissions data is excluded and counted in `carbon_coverage`; it's never
  treated as zero.
- The PCAF data-quality score comes from the extraction (reported and verified = 1–2, reported
  unverified = 2–3, estimated = 4–5). No placeholder value is ever stored.

*Implemented in task 2.3* (`GET /portfolios/{id}/carbon`; engine `app/carbon/pcaf.py`, data
assembly `app/investor/carbon.py`), with these choices:
- only **active** positions count (PCAF measures holdings at a point in time; planned and closed
  positions are left out), computed on read — no cached aggregate or job yet (task 4.1);
- emissions come from the company's latest **validated** report; Scope 2 uses the market-based
  value, else the unqualified one, else location-based;
- Scopes 1+2 need **both** scopes — a company that reports only one is `MISSING_EMISSIONS`, never
  half-counted; the carbon footprint divides by the **covered** value (not the whole portfolio,
  which would dilute it), and WACI weights are renormalised over the covered lines;
- a line's data quality is the worse of its Scope 1 and Scope 2 scores; unknown stays unknown;
- quality derived at extraction from the method: reported 2, calculated 3, estimated 4. Score 1
  (verified) needs third-party assurance information the extraction does not capture yet;
- EVIC and revenue belong to the fiscal year of a report (*task 5.4*) and are entered by an admin
  (`PUT /admin/reports/{id}/financials`); the engine reads them from the same report as the
  emissions — the company's latest validated one — so figures entered on a report still in review
  wait for its validation. The EVIC date (`evic_date`) is shown next to the emissions year rather
  than matched automatically;
- coverages are returned as shares of the total amount (0–1), one per metric, and every excluded
  line carries its reason (`UNMATCHED`, `NO_VALIDATED_REPORT`, `MISSING_EMISSIONS`, `MISSING_EVIC`).

---

## 3. Researcher and explainability engine

### 3.1 Custom YAML weights

```
 upload YAML ──validate──> STORED (hash) ──recalculate──> RESULTS ──explain──> SHAP / waterfall
       │                         │
       └── invalid → 422 with    └── same hash already stored → reuse the existing config
           the exact error
```

Validation (reuses `app/scoring/config_schema.py`):
- the three pillars are present; pillar weights and the indicator weights in each pillar sum
  to 1 (± 1e-6);
- every indicator code exists in the metric vocabulary;
- `min < max` for every normalisation bound;
- optional `min_coverage` in [0, 1].

The stored row keeps the raw YAML and `content_hash = sha256(canonical YAML)`. Researcher
configs are private to their owner and **never** change official scores.

### 3.2 Recalculation

1. Researcher picks a config and a scope (a project perimeter, a sector, or a list of companies).
2. Job: for each `VALIDATED` report in scope, compute the score with that config; insert into
   `scores` with `config_id` (unique per report and config, so a rerun is idempotent).
3. Results page: official score vs. custom score, delta, coverage, per pillar.

### 3.3 SHAP attribution and waterfall

The score is linear in the normalised sub-scores, so SHAP values are exact and computed in
closed form (see `docs/ARCHITECTURE.md` §7):

```
φᵢ = w_eff,ᵢ × (xᵢ − baselineᵢ)          Σ φᵢ = score − baseline_score
```

- `baseline` = mean normalised value of the indicator in the chosen reference set (sector by
  default, whole universe as fallback), stored with the result.
- **Waterfall**: baseline → contributions grouped by pillar, sorted by |φ| → final score.
- Endpoint returns the contributions, the baseline set used, the config hash and the effective
  weights after renormalisation for missing indicators.

*Implemented in task 3.2* (`GET /reports/{id}/score-explanation`, `app/explainability/`). Peers are
the latest validated report of every **other** published company, normalised under the config
that produced the explained score; the sector falls back to the whole universe below 3 peers
(`baseline.requested` ≠ `baseline.used`). An indicator that no peer publishes keeps its own value
as baseline (zero contribution, `baseline_value: null`). Computed on read, not stored.

### 3.4 Cross-validation against public datasets

- Import a reference dataset (Kaggle ESG, CDP, GRI) into a staging table with its licence and
  source URL.
- Match companies by ISIN/LEI only (never by name alone).
- Report: rank correlation (Spearman) and mean absolute difference per pillar, plus the
  unmatched list. Results are researcher-scoped and never modify platform data.

*Implemented in task 3.3* (`/researcher/reference-datasets`, `app/researcher/cross_validation.py`).
The dataset's scale and direction are declared at import, and every value is rescaled to 0-100
before the mean absolute difference (Spearman is scale-free). Matching is limited to the
researcher's project perimeter, like every other researcher view, so the sample is only as large
as the perimeter the institution built. The report is computed on read.

*Current:* researchers work in projects supervised by an institution (`Analyse`, `Projet`,
`Rattachement`); explainability: see §3.3 (task 3.2).
