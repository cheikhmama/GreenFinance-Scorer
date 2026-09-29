# GreenFinance-Scorer — Target Workflows (v2)

> **Status: PROPOSED TARGET.** State machines and lifecycles for the redesign described in
> [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). Each workflow notes what exists today and what
> changes. Names follow the target English domain model; the current French equivalents are
> listed where they differ.

Conventions used below:
- **Actor** — the role allowed to trigger the transition. Any other role gets `403`; a user of
  the right role who doesn't own the resource gets `404` (no existence leak).
- **Tx** — what commits together in one database transaction.
- **Job** — work enqueued on ARQ, executed by the worker after the transaction commits.

---

## 1. Enterprise management

### 1.1 Company lifecycle

```
            register (public)           onboard (ADMIN)
   ∅ ─────────────────────────> PENDING_ONBOARDING ──────────────> ACTIVE
                                        │                           │  ▲
                                        │ reject (ADMIN)   suspend  │  │ reactivate
                                        ▼                  (ADMIN)  ▼  │ (ADMIN)
                                     (deleted)                   SUSPENDED
```

| Transition | Actor | Preconditions | Tx | Job |
|---|---|---|---|---|
| register | public | Valid ISIN/LEI check digits if given; email not already used (case-insensitive); rate limit per IP | company `PENDING_ONBOARDING` + user `ENTERPRISE` (inactive) + audit log | activation email |
| onboard (KYC) | ADMIN | status `PENDING_ONBOARDING`; ISIN or LEI present; revenue and EVIC present | status `ACTIVE`, onboarded_by/at, audit log, notification | — |
| suspend / reactivate | ADMIN | — | status change, audit log, sessions of the owner revoked on suspend | — |

**Rules:**
- A `PENDING_ONBOARDING` company is invisible to every role except `ADMIN` and its owner.
- Only an `ACTIVE` company can submit reports or receive new investments.
- A `SUSPENDED` company stays visible to investors who already hold it (so they see the
  warning), but can't receive new positions.
- Onboarding and **publication** are separate: `published_at` records when the admin last
  published the company's official score, and only published companies appear in the
  investor and researcher catalogues.

*Current:* no public registration; the admin creates the user, the user activates by email link
(`app/auth/activation.py`). Publication is a separate `date_publication` timestamp set by the
admin. Decision D5 gates self-registration behind this onboarding step.

### 1.2 Report lifecycle

```
   create session            upload/submit                 extraction DONE + auditor assigned
 ∅ ───────────> DRAFT ────────────────────> SUBMITTED ─────────────────────────────> PENDING_AUDIT
                  ▲                            │                                          │
                  │                            │ extraction FAILED (retry by ADMIN)       │ opinion
                  │                            ▼                                          ▼
                  │                     SUBMITTED (extraction_status=FAILED)      PENDING_DECISION*
                  │                                                              │   │   │
                  │  new version (ENTERPRISE)           request revision (ADMIN)  │   │   │ reject (ADMIN)
                  └──────────────── REVISION_REQUESTED <─────────────────────────┘   │   └──────> REJECTED
                                                                                      │ validate (ADMIN)
                                                                                      ▼
                                                                                  VALIDATED
```
\* `PENDING_DECISION` was added by decision D2 (replaces `EN_VALIDATION`).

| Transition | Actor | Preconditions | Tx | Job |
|---|---|---|---|---|
| create session | ENTERPRISE (own ACTIVE company) | no other open report for `(company, fiscal_year)` | report `DRAFT` | — |
| submit | ENTERPRISE | `DRAFT`; PDF valid (magic bytes, size cap, checksum not already used) or raw metrics provided | status `SUBMITTED`, `extraction_status=QUEUED`, file stored | `extract_report` |
| extraction | worker | `extraction_status in (QUEUED, FAILED-retry)` | metrics + carbon rows + evidence replaced as a whole, coverage rows, `extraction_status=DONE`, **pre-score** (non-official score with the reference config) | `generate_synthesis_pdf` |
| assign auditor | ADMIN | `extraction_status=DONE` | `auditor_id`, `assigned_at`, status `PENDING_AUDIT`, notification | — |
| audit opinion | AUDITOR (assigned) | `PENDING_AUDIT` | opinion row, optional metric overrides (`auditor_overridden=true` + reason), status `PENDING_DECISION` | — |
| **validate** | ADMIN | `PENDING_DECISION`; score computable; coverage ≥ config threshold | see §1.3 | `generate_synthesis_pdf`, notification email |
| reject | ADMIN | `PENDING_DECISION` | status `REJECTED`, reason, notification | — |
| request revision | ADMIN | `PENDING_DECISION` | status `REVISION_REQUESTED`, reason, notification | — |
| new version | ENTERPRISE | `REVISION_REQUESTED` | new report row, `version+1`, `previous_report_id`, status `DRAFT` | — |

*Current:* statuses `ENVOYE → EN_EXTRACTION → AFFECTE_AUDITEUR → EN_VALIDATION → VALIDE / REJETE / DEMANDE_CORRECTION`;
extraction runs as a FastAPI `BackgroundTasks` in the API process; no draft state; no auditor
overrides.

### 1.3 Atomic score publication

All of the following happen in **one** transaction. If any step raises, nothing is committed and
the report stays in `PENDING_DECISION`.

1. Lock the report row (`SELECT … FOR UPDATE`) and re-check the status.
2. Resolve the reference `scoring_configs` row by content hash (get-or-create with
   `flush()` / `ON CONFLICT`, **never** `commit()`).
3. Compute the score from the effective metric values (auditor override if present, else the
   extracted value).
4. Insert the `scores` row; set `official_score`, `coverage_rate`, `config_hash` on the report.
5. Set status `VALIDATED`; write the audit log entry and the in-app notification.
6. `COMMIT`.
7. After commit: enqueue `generate_synthesis_pdf` and the notification email.

*Current bug this fixes:* `obtenir_configuration_reference` commits in the middle of
`valider_rapport`, which can persist `VALIDE` without a score (see `docs/TASKS.md` 1.6).

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

*Current:* positions are entered one at a time with an amount, currency and a fixed/open
duration; there is no ISIN, no ticker, no bulk import and no weight.

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

*Current:* `app/carbon/pcaf.py` and `emission_factors.py` are empty; carbon rows store a
hard-coded `score_qualite_pcaf = 3`.

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

### 3.4 Cross-validation against public datasets

- Import a reference dataset (Kaggle ESG, CDP, GRI) into a staging table with its licence and
  source URL.
- Match companies by ISIN/LEI only (never by name alone).
- Report: rank correlation (Spearman) and mean absolute difference per pillar, plus the
  unmatched list. Results are researcher-scoped and never modify platform data.

*Current:* researchers work in projects supervised by an institution (`Analyse`, `Projet`,
`Rattachement`), and explainability is a per-indicator decomposition without a baseline.
