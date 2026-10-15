# Frontend hierarchical navigation — foundation + Company pilot

Status: approved design, 2026-10-14 (four factual corrections made while writing the plan:
§2.2 L5 evidence link, §3.1 step 3, §3.3 step state, §4.1 `MetriqueVue.id`/`cle`). Branch `feat/refonte-navigation-entreprise` (cut from
`chore/upgrade-2026-10`).

## 1. Intent

Replace long single pages and stacked forms with a hierarchical, drill-down navigation (settings-app
style) across pages, sheets and wizards, so a user always knows where they are in the ESG taxonomy.

This spec covers **(a) a shared foundation** usable by every role space and **(b) the Company
(ENTERPRISE) space as the pilot** that proves it. The other five spaces (admin, audit, investor,
researcher, institution) each get their own later spec reusing the foundation.

Decisions taken during design:

| Topic | Decision |
|---|---|
| Taxonomy | Existing data model only: Pillar (E/S/G) → ~25 metric codes, carbon codes carry scope 1/2/3 and market/location-based for Scope 2. Families are a frontend config. No backend or migration change in this spec. |
| Slicing | Foundation + Company pilot first; one spec → plan → implementation cycle per later space. |
| Citation view | PDF page + metadata only. `proof_text`, `raw_value`, `section`, `proof_boxes` are never rendered in the company space. |
| Navigation architecture | Nested URL routes (React Router data router, already in place). Every level and every slide-over sheet is a route; breadcrumbs from route `handle`. No route loaders. |
| Status model | Four company-facing phases matching the real lifecycle; internal audit steps stay collapsed (decision 5.1 kept). |

Success criteria:

- No company page stacks more than one level of the hierarchy; the 467-line
  `CompanyReportDetailPage` no longer exists.
- Every level, sheet and wizard step is reachable by deep link and shows a correct breadcrumb.
- No dialog holds more than 3 fields; no form shows a field that does not apply.
- A sentinel test proves no forbidden extraction field reaches the DOM.
- Analysis progress never blocks navigation; lists and dashboard refresh themselves while an
  analysis runs.

## 2. Hierarchy and routes (Company pilot)

```
L1  Tableau de bord                     /company
L2  Mes déclarations                    /company/declarations
L3  Déclaration · Exercice 2025         /company/declarations/:rapportId            (overview, index route)
L4  Pilier                              /company/declarations/:rapportId/:pilier
      family section opened by URL       …/:pilier/:famille                         (same page, that section expanded + scrolled)
L5  Metric + citation (slide-over)       …/:pilier/:famille/:code                   (RouteSheet over L4)
    Correction (slide-over, 2 steps)     /company/declarations/:rapportId/correction
    New declaration wizard (pre-draft)   /company/declarations/nouvelle/:etape      (exercice | finances)
    Draft wizard (draft exists)          /company/declarations/:rapportId/brouillon/:etape   (document | verification)
    Profil entreprise                    /company/profile        (+ edit sheet: /company/profile/fiche-publique)
```

- `:pilier` ∈ `environnement | social | gouvernance` (slugs mapped to `Pillar`).
- An unknown `:pilier`, `:famille` or `:code` renders the level's contextual "not found" state (no
  silent redirect).
- Old addresses (`/company/rapports*`, `/company/deposer`, `/company/profil`) keep redirecting.
- The sidebar keeps its three links (Tableau de bord, Mes déclarations, Profil entreprise).

### 2.1 Family taxonomy (`features/company/esg/taxonomie.ts`)

| Pillar | Family slug / label | Codes |
|---|---|---|
| Environnement | `emissions-ges` Émissions GES | scope_1, scope_2, scope_2_market_based, scope_2_location_based, scope_3 |
| | `intensite-carbone` Intensité carbone | intensite_scope_1_2_marketbased, intensite_scope_1_2_3_hors_cat11, intensite_scope_1_2_3_total |
| | `energie-ressources` Énergie & ressources | part_renouvelable_pourcentage, dechets_valorises_pourcentage |
| Social | `effectifs-diversite` Effectifs & diversité | effectif_total, femmes_effectif_pourcentage, femmes_management_pourcentage |
| | `sante-securite` Santé & sécurité | deces_professionnels, taux_frequence_accidents |
| | `formation` Formation | heures_formation_par_employe |
| Gouvernance | `conseil` Conseil | taille_conseil, administrateurs_independants_pourcentage, femmes_conseil_pourcentage |
| each pillar | `score-declare` Score auto-déclaré | score_environnement_declare / score_social_declare / score_gouvernance_declare |
| each pillar | `autres` Autres indicateurs | any code of that pillar not listed above |

- Carbon rows (`DonneeCarboneDetail`) are placed by `scope` (and `ghg_category` for Scope 2) into
  `emissions-ges`.
- Declared scores stay a separate family, never merged into the computed score (methodology rule in
  `config/weights/default.yaml`).
- `score_global_declare` is shown on the L3 overview next to the official score, labelled as
  self-declared.

### 2.2 Layouts per level

- **AppShell**: adds the breadcrumb bar under the header. The page-level hand-written "Retour" link
  in the company space is removed.
- **L3 `DeclarationLayout`**: header with fiscal year, `StatusBadge`, `PhaseProgress` and the
  primary action for the current phase (Reprendre / Corriger / Synthèse PDF). Below it a
  `MasterDetailLayout`: rail = Vue d'ensemble + the three pillars (each with sub-score and
  found/expected count); detail = `<Outlet>`. While the report is a draft the rail is replaced by
  the wizard stepper.
- **L3 overview**: phase timeline, official score card (+ self-declared global score, labelled),
  three pillar summary cards linking to L4. No tables.
- **L4 pillar page**: one `DisclosureCard` per family. Collapsed: found/expected, review summary
  (e.g. "2 en revue"), headline value where meaningful (Émissions GES: Scope 1 + Scope 2
  market-based, tCO₂e). Expanded: compact list (label, value, unit, period, method badge); each row
  opens L5.
- **L5 `MetricSheet`**: value, unit, period, method, confidence, audit review status (and audited
  value when overridden), and "Rapport YYYY — p. X–Y" opening the company's own original PDF at
  that page (`/api/v1/company/rapports/{id}/fichier#page=X`, served inline). There is no
  company-scoped excerpt endpoint (only investor/researcher/institution/audit have one); adding one
  is out of scope.
- **L2 list**: unchanged DataTable and quick-look sheet, plus an "Ouvrir" link to L3.
- Below `md`, `MasterDetailLayout` turns the rail into its own list page (index) and the detail into
  a full screen; breadcrumbs collapse to "‹ parent".

## 3. Forms and workflows

### 3.1 New declaration wizard (replaces `NewDeclarationDialog`, `DraftPanel`, `SubmitDialog`)

| Step | URL | Content | Server call on leaving |
|---|---|---|---|
| 1 Exercice | `/company/declarations/nouvelle/exercice` | fiscal_year, report_type | none (wizard form state) |
| 2 Données financières | `…/nouvelle/finances` | currency; revenue and enterprise_value shown once a currency is chosen | `openReport` (201) → navigate to `/company/declarations/:id/brouillon/document` |
| 3 Document | `/company/declarations/:id/brouillon/document` | `FileDrop` (PDF); analysis starts. URL import is not offered: `import-url` creates a separate direct deposit, it cannot attach to a draft | none; progress shown, user may leave |
| 4 Vérification | `…/brouillon/verification` | completeness checklist (counts per group only), summary of steps 1–2, confirmation checkbox | `submitReport` (202) → receipt (SHA-256, ID) |

- Steps 1–2 share one React Hook Form instance with a Zod schema split per step; "Suivant"
  validates only the current step; "Précédent" keeps values.
- Leaving steps 1–2 with entered values asks for confirmation (nothing exists server-side yet).
- After step 2 the draft is server state: leaving is safe; the dashboard "Session active" card
  offers "Reprendre", which opens the first incomplete step decided by `etatBrouillon`
  (`SANS_FICHIER`/`ANALYSE`/`ECHEC` → document, `PRET` → verification).
- The "one declaration at a time" rule is unchanged: "Nouvelle déclaration" stays disabled while a
  session blocks it, and a direct URL to `nouvelle/*` in that state shows the same explanation.

### 3.2 Slide-over sheets

- **Correction** (`…/:rapportId/correction`, only when `REVISION_REQUESTED`): step 1 = what is being asked
  (the decision comment if the company report response carries it; otherwise the phase text from
  `presentation.ts` — no new endpoint for it); step 2 = fiscal year + replacement PDF. Replaces the inline `FormulaireCorrection`.
- **Profile edit** (`/company/profile/fiche-publique`): description, website, impose_minimum; the
  minimum amount and its currency appear only when impose_minimum is on.
- `Sheet` gains `size="lg"` (≈ 640 px) for forms and a sticky `SheetFooter`; the default width
  (460 px) stays for read-only quick-look.

### 3.3 Registration wizard (`features/registration`)

`CompanyRegistrationPage` moves onto the same `Wizard`: Entreprise (company_name, sector, country,
tax_id) → Contact & mandat (contact_name, contact_email, mandate_letter) → Identifiants optionnels
(lei, isin, website), then the existing e-mail verification and confirmation steps. Fields,
validation and API calls are unchanged. Steps are held in component state, not the URL: this
public form carries a file that cannot survive a reload. A submit-time error on a field of an
earlier step (e.g. e-mail domain vs website) brings the user back to that step.

### 3.4 Conventions (apply to every space from now on)

- A field that depends on another stays hidden until it applies and is excluded from validation
  while hidden (Zod discriminated union matching the visible fields).
- A collapsed section always shows a summary; inputs and full lists appear only when expanded.
- Dialog = confirmation or at most 3 fields. Longer edit of one object = sheet. Multiple steps, or a
  server call between steps = wizard.

## 4. Data and security boundaries

### 4.1 Display allowlist

- Company components never receive generated DTOs for metrics. `features/company/esg/vueMetrique.ts`
  maps `IndicateurESGDetail` and `DonneeCarboneDetail` to:

  ```ts
  interface MetriqueVue {
    id: string; cle: string; libelle: string; pilier: Pillar; famille: string;
    valeur: number | null; unite: string | null; periode: number | null;
    methode: DataMethod; confiance: ConfidenceLevel | null;
    revue: MetricReviewStatus; valeurAuditee: number | null;
    preuve: { document: string; annee: number | null; pageDebut: number; pageFin: number } | null;
  }
  ```

  (Exact field types follow the generated schema; the key set is the contract.)
- `proof_text`, `raw_value`, `section`, `proof_boxes` are never copied. New backend fields stay
  hidden until explicitly mapped.
- Evidence = the company's own original PDF opened at the cited page (see §2.2 L5).
- Extraction failures show `libelleCauseExtraction` wording, never backend error text.
- Error views show a message, a recovery action and the copyable `correlation_id`; never payloads.

### 4.2 Backend follow-up (separate PR, out of this spec's implementation)

- Remove `proof_text`, `raw_value`, `section`, `proof_boxes` from the company-facing report
  response schema (the auditor schema keeps them); diff the exported OpenAPI; regenerate Orval.
- Then amend `FRONTEND-ARCHITECTURE.md` §7: the excerpt text is shown only in the auditor workspace.
  Until that PR lands, §7 carries a note pointing to this spec.

## 5. Asynchronous statuses

### 5.1 Phases (`shared/format/phaseDeclaration.ts`)

| Phase | Statuses | Tone / icon |
|---|---|---|
| 1 Déposé | `DRAFT` (with or without file, no error) | neutral / file |
| 2 Analyse en cours | `EXTRACTING` | info / spinner (static under reduced motion) |
| 3 En cours d'examen 🔒 | `AWAITING_ASSIGNMENT`, `IN_AUDIT`, `PENDING_DECISION` | warning / lock |
| 4 Audité | `VALIDATED` ("Validé & publié"), `REJECTED` ("Refusé") | success / danger |
| branch: Analyse impossible | `EXTRACTION_FAILED`, or `DRAFT` with `extraction_error` | danger + retry action |
| branch: Correction demandée | `REVISION_REQUESTED` | warning + link to correction sheet |

`phaseDeclaration(rapport)` replaces `etapeCourante` and the `SessionStepper` steps. Internal step
names are never shown to the company.

### 5.2 Components

- `StatusBadge`: label + icon + tone; tone never carries meaning alone.
- `PhaseProgress`: 4 steps, current step, optional branch marker; inline (list, dashboard) or as the
  L3 header strip.
- During analysis the Document step shows an indeterminate bar and a polite `aria-live` message; the
  same phase is visible on the dashboard card, the list badge and the L3 header.

## 6. Data fetching (TanStack Query)

- Typed key factory `companyKeys`: `all`, `reports()`, `report(id)`, `checklist(id, analysedAt)`,
  `profile()`, `lei()`. Replaces `REPORTS_QUERY_KEY` / `reportQueryKey`. Every mutation lists the
  keys it invalidates.
- One `getCompanyReport` query serves L3, L4 and L5 via `queryOptions()`; pillar, family and metric
  are derived with `select`. No new endpoint; moving between levels causes no request.
- Polling:
  - report detail: every 5 s while `EXTRACTING` (unchanged);
  - report list: every 5 s while any row is `EXTRACTING` (new — dashboard and list refresh);
  - review phases are not polled; when the unread-notification count (already polled every 60 s)
    increases, `companyKeys.reports()` and open `companyKeys.report(id)` are invalidated.
- `staleTime`: reports 30 s, profile 5 min, LEI check 10 min. Retry policy unchanged (none on
  4xx, at most 3 on network/5xx).
- Each level handles loading (skeleton shaped like the final layout), empty, error, forbidden and
  not-found, and has its own route error boundary.

## 7. Component blueprint

### 7.1 Shared foundation

| Unit | Location | Responsibility | Depends on |
|---|---|---|---|
| `Breadcrumbs` | `shared/layout/Breadcrumbs.tsx` | Trail from `useMatches()` + `handle.crumb` (string or component reading cached data); hidden when no crumb; mobile "‹ parent" | react-router |
| `MasterDetailLayout` | `shared/layout/MasterDetailLayout.tsx` | Rail + `<Outlet>`; below `md` rail becomes index page | react-router |
| `RouteSheet` | `shared/ui/route-sheet.tsx` | `Sheet` open while its route matches; close → navigate to parent, focus back to the opener | `sheet`, react-router |
| `Sheet` (extended) | `shared/ui/sheet.tsx` | `size="lg"`, sticky `SheetFooter` | Radix Dialog |
| `Wizard`, `WizardStepper`, `useWizardNavigation` | `shared/ui/wizard/` | URL-driven steps, per-step validation, discard prompt, "Étape n sur N" on mobile | react-hook-form, react-router |
| `DisclosureCard` | `shared/ui/disclosure-card.tsx` | Collapsible card with always-visible summary; URL-openable + scroll into view | `collapsible`, `card` |
| `StatusBadge` | `shared/ui/status-badge.tsx` | Generic label/icon/tone | `badge` |
| `PhaseProgress` | `shared/ui/phase-progress.tsx` | Generic steps/current/branch | — |
| `phaseDeclaration` | `shared/format/phaseDeclaration.ts` | 9 statuses → phase + branch | generated `ReportStatus` |

`shared/` gains no business vocabulary except `phaseDeclaration`, which already has two users
(company now; admin/investor badges later) like the existing `shared/format/statut.ts`.

### 7.2 Company feature

```
features/company/
├── api.ts                       companyKeys, queryOptions, mutations
├── esg/taxonomie.ts             pillar → family → codes, fallback "autres"
├── esg/vueMetrique.ts           DTO → MetriqueVue allowlist
├── declaration/
│   ├── DeclarationLayout.tsx    L3
│   ├── OverviewPage.tsx         L3 index
│   ├── PillarPage.tsx           L4
│   ├── MetricSheet.tsx          L5
│   └── CorrectionSheet.tsx
├── wizard/
│   ├── NewDeclarationWizard.tsx ExerciceStep, FinancesStep
│   ├── DocumentStep.tsx
│   ├── VerificationStep.tsx     + receipt
│   └── schemas.ts               per-step Zod schemas
├── components/                  CompanyDashboardPage, CompanyDeclarationsPage, ProfilePage, ProfileEditSheet, CompanyRegistrationsCard, RegistrationStatusPage
├── session/                     etat.ts (etatBrouillon, separerDeclarations), presentation.ts, LockBanner, CompletenessChecklist
└── routes.tsx                   nested tree with handle.crumb + legacy redirects
```

Removed: `CompanyReportDetailPage`, `NewDeclarationDialog`, `DraftPanel`, `SubmitDialog`,
`SessionStepper`, `etapeCourante`, the page-local `RetourListe` and `FormulaireCorrection`.

## 8. Testing

Vitest + Testing Library, mocking API calls the way the existing company tests do.

- Routing: deep link to every level renders; breadcrumb trail correct per level; legacy URLs
  redirect; unknown pillar/family/code shows the not-found state.
- Boundary: sentinel strings in `proof_text`, `raw_value`, `section`, `proof_boxes` never appear in
  the DOM at L3/L4/L5; `MetriqueVue` key set pinned.
- `phaseDeclaration`: table test over all 9 statuses × with/without file × with/without error.
- Taxonomy: every known code maps to exactly one family; unknown code → `autres`; carbon rows placed
  by scope.
- Wizard: "Suivant" validates only the current step; "Précédent" keeps values; `openReport` called
  only when leaving step 2; resumed draft opens the right step; submit shows the receipt;
  the one-at-a-time block applies to direct URLs.
- `RouteSheet`: Esc returns to the parent URL and restores focus to the opener.
- Polling (fake timers): list polls while a row is `EXTRACTING`, stops after; unread-count increase
  invalidates report keys.
- Existing company and registration tests are rewritten to the new structure, not deleted.
- Definition of Done checks from `FRONTEND-ARCHITECTURE.md` §12: keyboard pass and mobile / tablet /
  desktop widths on every touched page.

## 9. Delivery order

One commit per step, each green (lint, tsc, tests, build) before the next. Tracked as a new phase in
`docs/TASKS.md`.

1. Shared primitives: `Sheet` sizes + footer, `RouteSheet`, `DisclosureCard`, `StatusBadge`,
   `PhaseProgress`, `Wizard` — with tests.
2. `Breadcrumbs` in `AppShell`, `MasterDetailLayout`.
3. `taxonomie.ts`, `vueMetrique.ts`, leak tests; `phaseDeclaration`; `companyKeys`.
4. Nested report routes L3–L5; remove `CompanyReportDetailPage`.
5. New-declaration and draft wizard; remove dialog and panels; list polling and
   notification-driven invalidation.
6. Correction sheet.
7. Profile edit sheet.
8. Registration wizard.
9. `FRONTEND-ARCHITECTURE.md` (navigation, forms and status conventions; §7 note) and
   `docs/TASKS.md`.

## 10. Out of scope

- The admin, audit, investor, researcher and institution spaces (later specs, same foundation).
- The backend schema clean-up of §4.2.
- Route loaders / prefetch-on-navigation.
- Facilities, GHG sub-categories (stationary/mobile combustion…), company-defined custom metrics.
- New dependencies (none needed: React Router, TanStack Query, React Hook Form, Zod and Radix are
  already in place).
