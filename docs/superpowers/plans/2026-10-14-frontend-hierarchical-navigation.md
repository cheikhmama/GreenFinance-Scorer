# Frontend hierarchical navigation (foundation + Company pilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Company space's long detail page and stacked dialogs with a URL-addressable drill-down (Tableau de bord → Mes déclarations → Déclaration → Pilier → Famille → Indicateur), multi-step wizards and routed slide-over sheets, on a shared foundation the other five spaces can reuse later.

**Architecture:** Nested React Router data-router routes; every level and every sheet is a route; breadcrumbs come from `handle.fil` via `useMatches()`. One `getCompanyReport` TanStack query feeds every level of a declaration, sliced with `select` through an allowlist view model (`MetriqueVue`) so extraction internals never reach the DOM. Wizards are URL-driven per step (company) and validate one step at a time with React Hook Form + Zod.

**Tech Stack:** React 19, React Router 7 (`createBrowserRouter`), TanStack Query 5, React Hook Form 7 + Zod 4, Radix (`radix-ui`), Tailwind 4, Vitest 4 + Testing Library, Biome.

**Spec:** `docs/superpowers/specs/2026-10-14-frontend-hierarchical-navigation-design.md`

## Global Constraints

- No new dependency (spec §10). Everything uses what is in `frontend/package.json`.
- No backend, OpenAPI or migration change. Never edit `src/shared/api/generated/` by hand.
- Company components never render `proof_text`, `raw_value`, `section` or `proof_boxes` (spec §4.1).
- Evidence link = `/api/v1/company/rapports/{id}/fichier#page={page_start}` opened in a new tab (spec §2.2 L5).
- Company-facing status = the four phases `Déposé`, `Analyse en cours`, `En cours d'examen`, `Audité` plus branches `Analyse impossible`, `Correction demandée` (spec §5.1); internal step names are never shown to the company.
- A dialog holds at most 3 fields; longer edits are sheets; multi-step or mid-flow server call = wizard (spec §3.4).
- Polling only while `EXTRACTING` (5 s, `DELAI_SUIVI_ANALYSE_MS`); review phases refresh through the unread-notification count (spec §6).
- UI copy is French, typographic apostrophes (`’`) as in the existing code; identifiers follow the codebase's French naming (`titre`, `libelle`, `taille`…).
- Import boundaries: `shared/` never imports `features/`; a feature never imports another feature (existing exception: `features/company` already imports `features/registration/*`, keep as is).
- Every task ends green: from `frontend/`, `npx biome check src`, `npx tsc -b`, `npx vitest run`, `npm run build`.
- One commit per task, French commit message in the repo's style (`feat(interface): …`), ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Branch: `feat/refonte-navigation-entreprise`.

## Review Focus

1. **Bare-UUID deep links from old e-mails** (`/company/declarations/<uuid>/environnement`): must resolve through `idDepuisSlug` like slugged links → test in Task 9.
2. **A submitted report with no extracted values yet** (empty `metrics` and `carbon_data`): pillar page must list every family with "Aucun indicateur trouvé", never a blank page → test in Task 9.
3. **Typing `…/brouillon/verification` while the file is still being analysed or failed**: must land on the Document step, not a half-empty checklist → test in Task 10.
4. **Registration error on a field of an earlier step found only at submit** (e-mail domain vs website entered on step 3): user is taken back to step 2 with the message shown → test in Task 13.
5. **Unread-notification count going down** (user reads notifications) must not trigger a refetch storm; only an increase invalidates report queries → test in Task 6.

---

## File map

| File | Status | Responsibility |
|---|---|---|
| `frontend/src/shared/ui/sheet.tsx` | modify | `taille` prop (`standard` 460 px / `large` 640 px) |
| `frontend/src/shared/ui/route-sheet.tsx` | create | Sheet open while its route matches; close → `retour` |
| `frontend/src/shared/ui/disclosure-card.tsx` | create | Controlled collapsible card with always-visible summary |
| `frontend/src/shared/ui/status-badge.tsx` | create | Label + icon + tone badge |
| `frontend/src/shared/ui/phase-progress.tsx` | create | Generic ordered phase indicator |
| `frontend/src/shared/ui/wizard/wizard-stepper.tsx` | create | Step list (desktop) / "Étape n sur N" (mobile) |
| `frontend/src/shared/ui/wizard/use-confirmation-abandon.ts` | create | `useBlocker` + confirm dialog before leaving a dirty wizard |
| `frontend/src/shared/layout/handle.ts` | create | `HandleRoute` type (`pleineLargeur`, `fil`) |
| `frontend/src/shared/layout/Breadcrumbs.tsx` | create | Trail from `useMatches()` |
| `frontend/src/shared/layout/MasterDetailLayout.tsx` | create | Rail + detail, rail hidden on mobile when a detail is active |
| `frontend/src/shared/layout/RouteError.tsx` | create | Route `errorElement` with correlation id |
| `frontend/src/shared/layout/AppShell.tsx` | modify | Uses `HandleRoute`, renders `Breadcrumbs` |
| `frontend/src/shared/format/phaseDeclaration.ts` | create | 9 statuses → phase/branch |
| `frontend/src/features/company/api.ts` | modify | `companyKeys`, `rapportQueryOptions`, list polling, `useActualisationSurNotification` |
| `frontend/src/features/company/esg/taxonomie.ts` | create | Pillar slugs, families, code → family |
| `frontend/src/features/company/esg/vueMetrique.ts` | create | DTO → `MetriqueVue` allowlist |
| `frontend/src/features/company/declaration/*` | create | L3 layout, overview, rail, pillar page, metric sheet, correction sheet, status badge, score card |
| `frontend/src/features/company/wizard/*` | create | New-declaration wizard, Document and Vérification steps |
| `frontend/src/features/company/components/ProfileEditSheet.tsx` | create | Public profile form in a sheet |
| `frontend/src/features/company/routes.tsx` | modify | Nested tree with `handle.fil` |
| `frontend/src/features/company/test/renderCompany.tsx` | create | Test helper mounting the company routes in a memory data router |
| `frontend/src/features/company/components/CompanyRegistrationPage.tsx` | modify | 3-step wizard |
| `frontend/src/features/company/components/CompanyReportDetailPage.tsx` (+ test) | delete (Task 8) | split into `declaration/*` |
| `frontend/src/features/company/session/{NewDeclarationDialog,DraftPanel,SubmitDialog,SessionStepper}.tsx` | delete (Task 10) | replaced by the wizard |
| `FRONTEND-ARCHITECTURE.md`, `docs/TASKS.md` | modify (Task 14) | conventions + task tracking |

All commands below run from `frontend/` unless stated.

---

### Task 1: Sheet sizes and `RouteSheet`

**Files:**
- Modify: `frontend/src/shared/ui/sheet.tsx` (`SheetContent`)
- Create: `frontend/src/shared/ui/route-sheet.tsx`
- Test: `frontend/src/shared/ui/route-sheet.test.tsx`

**Interfaces:**
- Produces: `SheetContent` prop `taille?: "standard" | "large"`; `RouteSheet({ retour: string; titre: ReactNode; description?: ReactNode; taille?: "standard" | "large"; children: ReactNode })`.

- [ ] **Step 1: Write the failing test**

`frontend/src/shared/ui/route-sheet.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SheetBody } from "./sheet";
import { RouteSheet } from "./route-sheet";

function Liste() {
  const { pathname } = useLocation();
  return (
    <>
      <p data-testid="chemin">{pathname}</p>
      <Link to="detail">Ouvrir le détail</Link>
      <Outlet />
    </>
  );
}

function renderSheet(chemin = "/liste") {
  return render(
    <MemoryRouter initialEntries={[chemin]}>
      <Routes>
        <Route path="/liste" element={<Liste />}>
          <Route
            path="detail"
            element={
              <RouteSheet retour="/liste" titre="Détail" taille="large">
                <SheetBody>contenu</SheetBody>
              </RouteSheet>
            }
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("RouteSheet", () => {
  it("s’ouvre sur sa route et revient à la route parente avec Échap", async () => {
    const user = userEvent.setup();
    renderSheet();
    const lien = screen.getByRole("link", { name: "Ouvrir le détail" });
    await user.click(lien);
    expect(await screen.findByRole("dialog", { name: "Détail" })).toHaveTextContent("contenu");

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByTestId("chemin")).toHaveTextContent("/liste");
    expect(lien).toHaveFocus();
  });

  it("s’ouvre directement depuis un lien profond", async () => {
    renderSheet("/liste/detail");
    expect(await screen.findByRole("dialog", { name: "Détail" })).toBeInTheDocument();
  });

  it("taille large : 640 px au lieu de 460 px", async () => {
    renderSheet("/liste/detail");
    const dialogue = await screen.findByRole("dialog");
    expect(dialogue.className).toContain("sm:max-w-[640px]");
    expect(dialogue.className).not.toContain("sm:max-w-[460px]");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/shared/ui/route-sheet.test.tsx`
Expected: FAIL — `Failed to resolve import "./route-sheet"`.

- [ ] **Step 3: Add `taille` to `SheetContent`**

In `frontend/src/shared/ui/sheet.tsx`, replace the `SheetContent` signature and class list:

```tsx
const LARGEURS = {
  /** Consultation (tiroir de détail d'une table). */
  standard: "sm:max-w-[460px]",
  /** Formulaire (modification d'un objet, assistant court). */
  large: "sm:max-w-[640px]",
} as const;

function SheetContent({
  className,
  children,
  taille = "standard",
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & { taille?: keyof typeof LARGEURS }) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        data-slot="sheet-overlay"
        className="fixed inset-0 z-50 bg-[rgb(10_24_38/0.32)]"
      />
      <DialogPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed inset-y-0 right-0 z-[60] flex w-full flex-col border-l bg-card shadow-(--shadow-e4) outline-none",
          LARGEURS[taille],
          className,
        )}
        {...props}
      >
```

(The rest of the function — `{children}` and the close button — is unchanged. `SheetFooter` already sits below the scrolling `SheetBody`, so it is already sticky: no change needed.)

- [ ] **Step 4: Create `RouteSheet`**

`frontend/src/shared/ui/route-sheet.tsx`:

```tsx
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./sheet";

/** Tiroir adressable (refonte de la navigation, spec §7.1) : ouvert tant que sa route est active,
 * le fermer (Échap, ×, clic à côté) ramène à `retour`, la route parente. Le focus revient à
 * l'élément qui l'a ouvert (Radix le mémorise au montage et le rend au démontage). */
export function RouteSheet({
  retour,
  titre,
  description,
  taille,
  children,
}: {
  retour: string;
  titre: ReactNode;
  description?: ReactNode;
  taille?: "standard" | "large";
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <Sheet
      open
      onOpenChange={(ouvert) => {
        if (!ouvert) navigate(retour, { preventScrollReset: true });
      }}
    >
      <SheetContent taille={taille} {...(description ? {} : { "aria-describedby": undefined })}>
        <SheetHeader>
          <SheetTitle>{titre}</SheetTitle>
          {description ? <SheetDescription>{description}</SheetDescription> : null}
        </SheetHeader>
        {children}
      </SheetContent>
    </Sheet>
  );
}
```

Note: without a `description`, Radix warns unless `aria-describedby={undefined}` is passed explicitly; with one, the prop must be left out so Radix links `SheetDescription` itself — hence the conditional spread.

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/shared/ui/route-sheet.test.tsx`
Expected: PASS (3 tests). Focus return relies on Radix `FocusScope` restoring the element that had focus when the sheet mounted (the clicked link). If the focus assertion fails, do not add `onCloseAutoFocus` handlers; first check that the link really had focus before the sheet opened.

- [ ] **Step 6: Full checks and commit**

Run: `npx biome check src && npx tsc -b && npx vitest run`
Expected: all green.

```bash
git add frontend/src/shared/ui/sheet.tsx frontend/src/shared/ui/route-sheet.tsx frontend/src/shared/ui/route-sheet.test.tsx
git commit -m "feat(interface): tiroir routé et largeur large des tiroirs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `DisclosureCard`, `StatusBadge`, `PhaseProgress`

**Files:**
- Create: `frontend/src/shared/ui/disclosure-card.tsx`, `frontend/src/shared/ui/status-badge.tsx`, `frontend/src/shared/ui/phase-progress.tsx`
- Test: `frontend/src/shared/ui/disclosure.test.tsx`

**Interfaces:**
- Produces:
  - `DisclosureCard({ id: string; titre: ReactNode; resume: ReactNode; ouvert: boolean; onOuvertChange: (ouvert: boolean) => void; children: ReactNode })`
  - `type TonStatut = "neutre" | "info" | "attention" | "succes" | "danger"`; `StatusBadge({ libelle: string; ton: TonStatut; icone: LucideIcon; enCours?: boolean })`
  - `PhaseProgress({ etapes: readonly string[]; courante: number; branche?: { libelle: string; ton: "attention" | "danger" } | null; label?: string })`

- [ ] **Step 1: Write the failing tests**

`frontend/src/shared/ui/disclosure.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileText } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { DisclosureCard } from "./disclosure-card";
import { PhaseProgress } from "./phase-progress";
import { StatusBadge } from "./status-badge";

describe("DisclosureCard", () => {
  it("fermée : le résumé reste visible, le contenu non ; un clic demande l’ouverture", async () => {
    const onOuvertChange = vi.fn();
    const user = userEvent.setup();
    render(
      <DisclosureCard
        id="famille-conseil"
        titre="Conseil"
        resume="2/3 trouvé(s)"
        ouvert={false}
        onOuvertChange={onOuvertChange}
      >
        <p>Taille du conseil</p>
      </DisclosureCard>,
    );
    expect(screen.getByText("2/3 trouvé(s)")).toBeVisible();
    expect(screen.queryByText("Taille du conseil")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Conseil/ }));
    expect(onOuvertChange).toHaveBeenCalledWith(true);
  });

  it("ouverte : contenu et résumé visibles, région nommée par le titre", () => {
    render(
      <DisclosureCard id="f" titre="Conseil" resume="2/3" ouvert onOuvertChange={() => {}}>
        <p>Taille du conseil</p>
      </DisclosureCard>,
    );
    expect(screen.getByRole("region", { name: "Conseil" })).toBeInTheDocument();
    expect(screen.getByText("Taille du conseil")).toBeVisible();
    expect(screen.getByRole("button", { name: /Conseil/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});

describe("StatusBadge", () => {
  it("porte le libellé, pas seulement une couleur", () => {
    render(<StatusBadge libelle="Analyse en cours" ton="info" icone={FileText} />);
    expect(screen.getByText("Analyse en cours")).toBeInTheDocument();
  });
});

describe("PhaseProgress", () => {
  it("marque l’étape courante et annonce une branche", () => {
    render(
      <PhaseProgress
        etapes={["Déposé", "Analyse en cours", "En cours d’examen", "Audité"]}
        courante={2}
        branche={{ libelle: "Correction demandée", ton: "attention" }}
      />,
    );
    const liste = screen.getByRole("list", { name: "Progression" });
    expect(liste.querySelector("[aria-current='step']")).toHaveTextContent("En cours d’examen");
    expect(screen.getByText("Correction demandée")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/shared/ui/disclosure.test.tsx`
Expected: FAIL — unresolved imports.

- [ ] **Step 3: Implement `DisclosureCard`**

`frontend/src/shared/ui/disclosure-card.tsx`:

```tsx
import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./collapsible";

/** Carte repliable à résumé (spec §2.2, §3.4) : le résumé reste lisible replié comme déplié, le
 * détail n'apparaît que déplié. Contrôlée : l'URL décide de l'ouverture (famille d'un pilier).
 * Ouverte au montage (lien profond), elle se fait défiler en vue. */
export function DisclosureCard({
  id,
  titre,
  resume,
  ouvert,
  onOuvertChange,
  children,
}: {
  id: string;
  titre: ReactNode;
  resume: ReactNode;
  ouvert: boolean;
  onOuvertChange: (ouvert: boolean) => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const ouverteAuMontage = useRef(ouvert);
  useEffect(() => {
    if (ouverteAuMontage.current) ref.current?.scrollIntoView({ block: "start" });
  }, []);

  return (
    <Collapsible open={ouvert} onOpenChange={onOuvertChange} asChild>
      <section
        ref={ref}
        id={id}
        aria-labelledby={`${id}-titre`}
        className="rounded-xl border bg-card shadow-(--shadow-e1)"
      >
        <CollapsibleTrigger className="group flex w-full items-center justify-between gap-4 rounded-xl px-5 py-4 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="min-w-0">
            <span id={`${id}-titre`} className="block font-semibold text-foreground">
              {titre}
            </span>
            <span className="mt-0.5 block text-sm text-muted-foreground">{resume}</span>
          </span>
          <ChevronDown
            className="size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none group-data-[state=open]:rotate-180"
            aria-hidden="true"
          />
        </CollapsibleTrigger>
        <CollapsibleContent className="border-t px-5 py-4">{children}</CollapsibleContent>
      </section>
    </Collapsible>
  );
}
```

- [ ] **Step 4: Implement `StatusBadge`**

`frontend/src/shared/ui/status-badge.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";
import { Badge } from "./badge";
import { cn } from "./cn";

export type TonStatut = "neutre" | "info" | "attention" | "succes" | "danger";

const VARIANTES = {
  neutre: "secondary",
  info: "info",
  attention: "warning",
  succes: "success",
  danger: "destructive",
} as const;

/** Statut d'objet : libellé + icône + ton (spec §5.2) — la couleur ne porte jamais seule
 * l'information. `enCours` fait tourner l'icône, sauf si l'utilisateur réduit les animations. */
export function StatusBadge({
  libelle,
  ton,
  icone: Icone,
  enCours = false,
}: {
  libelle: string;
  ton: TonStatut;
  icone: LucideIcon;
  enCours?: boolean;
}) {
  return (
    <Badge variant={VARIANTES[ton]}>
      <Icone aria-hidden="true" className={cn(enCours && "motion-safe:animate-spin")} />
      {libelle}
    </Badge>
  );
}
```

- [ ] **Step 5: Implement `PhaseProgress`**

`frontend/src/shared/ui/phase-progress.tsx`:

```tsx
import { Check } from "lucide-react";
import { cn } from "./cn";

/** Progression d'un objet en phases ordonnées (spec §5.2). Les phases franchies et la courante
 * sont pleines ; une branche (« Correction demandée »…) est dite en toutes lettres à côté. */
export function PhaseProgress({
  etapes,
  courante,
  branche = null,
  label = "Progression",
}: {
  etapes: readonly string[];
  courante: number;
  branche?: { libelle: string; ton: "attention" | "danger" } | null;
  label?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <ol aria-label={label} className="flex flex-wrap items-center gap-2">
        {etapes.map((etape, i) => {
          const franchie = i < courante;
          const active = i === courante;
          return (
            <li
              key={etape}
              aria-current={active ? "step" : undefined}
              className="flex items-center gap-2 text-sm"
            >
              {i > 0 ? <span aria-hidden="true" className="h-px w-4 bg-border sm:w-6" /> : null}
              <span
                className={cn(
                  "grid size-6 place-items-center rounded-full border text-xs font-semibold",
                  franchie && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary text-primary",
                  !franchie && !active && "text-muted-foreground",
                )}
                aria-hidden="true"
              >
                {franchie ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span
                className={cn(
                  active ? "font-medium text-foreground" : "text-muted-foreground",
                  !active && "sr-only sm:not-sr-only",
                )}
              >
                {etape}
              </span>
            </li>
          );
        })}
      </ol>
      {branche ? (
        <p
          className={cn(
            "text-sm font-medium",
            branche.ton === "danger" ? "text-danger" : "text-warning",
          )}
        >
          {branche.libelle}
        </p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6: Run tests, full checks, commit**

Run: `npx vitest run src/shared/ui/disclosure.test.tsx` → PASS (4 tests).
Run: `npx biome check src && npx tsc -b && npx vitest run` → green.

```bash
git add frontend/src/shared/ui/disclosure-card.tsx frontend/src/shared/ui/status-badge.tsx frontend/src/shared/ui/phase-progress.tsx frontend/src/shared/ui/disclosure.test.tsx
git commit -m "feat(interface): carte repliable à résumé, badge de statut et progression par phases

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Wizard primitives

**Files:**
- Create: `frontend/src/shared/ui/wizard/wizard-stepper.tsx`, `frontend/src/shared/ui/wizard/use-confirmation-abandon.ts`, `frontend/src/shared/ui/wizard/index.ts`
- Test: `frontend/src/shared/ui/wizard/wizard.test.tsx`

**Interfaces:**
- Produces:
  - `interface EtapeWizard { id: string; titre: string }`
  - `WizardStepper({ etapes: readonly EtapeWizard[]; courante: string })` — `<nav aria-label="Étapes">`, the current `<li>` has `aria-current="step"`; on mobile a line "Étape n sur N — titre".
  - `useConfirmationAbandon(doitConfirmer: (prochaine: Location) => boolean): void` — must be used under a data router (`createBrowserRouter` / `createMemoryRouter`) and inside `ConfirmProvider`.
  - Per-step validation is plain RHF: `await form.trigger(CHAMPS_PAR_ETAPE[etape])` (no wrapper — YAGNI).

- [ ] **Step 1: Write the failing tests**

`frontend/src/shared/ui/wizard/wizard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { createMemoryRouter, Link, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { useConfirmationAbandon, WizardStepper } from ".";

const ETAPES = [
  { id: "exercice", titre: "Exercice" },
  { id: "finances", titre: "Données financières" },
  { id: "document", titre: "Document" },
];

describe("WizardStepper", () => {
  it("marque l’étape courante et annonce la position", () => {
    render(<WizardStepper etapes={ETAPES} courante="finances" />);
    const nav = screen.getByRole("navigation", { name: "Étapes" });
    expect(nav.querySelector("[aria-current='step']")).toHaveTextContent("Données financières");
    expect(nav).toHaveTextContent("Étape 2 sur 3");
  });
});

function Saisie() {
  const sale = useRef(true);
  useConfirmationAbandon(() => sale.current);
  return (
    <>
      <p>Saisie en cours</p>
      <Link to="/ailleurs">Quitter</Link>
    </>
  );
}

function renderAbandon() {
  const router = createMemoryRouter(
    [
      { path: "/saisie", element: <Saisie /> },
      { path: "/ailleurs", element: <p>Ailleurs</p> },
    ],
    { initialEntries: ["/saisie"] },
  );
  render(
    <ConfirmProvider>
      <RouterProvider router={router} />
    </ConfirmProvider>,
  );
  return router;
}

describe("useConfirmationAbandon", () => {
  it("demande confirmation ; « Continuer la saisie » reste sur place", async () => {
    const user = userEvent.setup();
    renderAbandon();
    await user.click(screen.getByRole("link", { name: "Quitter" }));
    await user.click(await screen.findByRole("button", { name: "Continuer la saisie" }));
    expect(screen.getByText("Saisie en cours")).toBeInTheDocument();
  });

  it("« Abandonner » quitte la page", async () => {
    const user = userEvent.setup();
    renderAbandon();
    await user.click(screen.getByRole("link", { name: "Quitter" }));
    await user.click(await screen.findByRole("button", { name: "Abandonner" }));
    expect(await screen.findByText("Ailleurs")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/shared/ui/wizard/wizard.test.tsx`
Expected: FAIL — unresolved import `.`.

- [ ] **Step 3: Implement `WizardStepper`**

`frontend/src/shared/ui/wizard/wizard-stepper.tsx`:

```tsx
import { Check } from "lucide-react";
import { cn } from "@/shared/ui/cn";

export interface EtapeWizard {
  id: string;
  titre: string;
}

/** Étapes d'un assistant (spec §3.1) : liste verticale sur grand écran, « Étape n sur N » au
 * téléphone. Purement présentatif : l'étape courante vient de l'URL (ou de l'état local). */
export function WizardStepper({
  etapes,
  courante,
}: {
  etapes: readonly EtapeWizard[];
  courante: string;
}) {
  const index = Math.max(
    0,
    etapes.findIndex((etape) => etape.id === courante),
  );
  return (
    <nav aria-label="Étapes">
      <p className="text-sm text-muted-foreground md:hidden">
        Étape {index + 1} sur {etapes.length} —{" "}
        <span className="font-medium text-foreground">{etapes[index]?.titre}</span>
      </p>
      <ol className="hidden flex-col gap-1 md:flex">
        {etapes.map((etape, i) => (
          <li
            key={etape.id}
            aria-current={i === index ? "step" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
              i === index ? "bg-secondary font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full border text-xs font-semibold",
                i < index && "border-primary bg-primary text-primary-foreground",
                i === index && "border-primary text-primary",
              )}
            >
              {i < index ? <Check className="size-3.5" /> : i + 1}
            </span>
            {etape.titre}
          </li>
        ))}
      </ol>
    </nav>
  );
}
```

- [ ] **Step 4: Implement `useConfirmationAbandon`**

`frontend/src/shared/ui/wizard/use-confirmation-abandon.ts`:

```ts
import { useEffect } from "react";
import { type Location, useBlocker } from "react-router-dom";
import { useConfirm } from "@/shared/ui/confirm-dialog";

/** Avant de quitter un assistant dont la saisie n'existe encore que dans le navigateur (spec
 * §3.1) : confirmation explicite. `doitConfirmer` est évalué au moment de la navigation — lire
 * l'état depuis une ref pour qu'une navigation voulue (après création du brouillon) passe. */
export function useConfirmationAbandon(doitConfirmer: (prochaine: Location) => boolean) {
  const confirm = useConfirm();
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      currentLocation.pathname !== nextLocation.pathname && doitConfirmer(nextLocation),
  );

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    confirm({
      title: "Abandonner la saisie ?",
      description: "Les informations saisies dans cet assistant seront perdues.",
      confirmLabel: "Abandonner",
      cancelLabel: "Continuer la saisie",
      destructive: true,
    }).then((abandonner) => (abandonner ? blocker.proceed() : blocker.reset()));
  }, [blocker, confirm]);
}
```

`frontend/src/shared/ui/wizard/index.ts`:

```ts
export { useConfirmationAbandon } from "./use-confirmation-abandon";
export { type EtapeWizard, WizardStepper } from "./wizard-stepper";
```

- [ ] **Step 5: Run tests, full checks, commit**

Run: `npx vitest run src/shared/ui/wizard/wizard.test.tsx` → PASS (3 tests).
Run: `npx biome check src && npx tsc -b && npx vitest run` → green.

```bash
git add frontend/src/shared/ui/wizard
git commit -m "feat(interface): primitives d'assistant par étapes (stepper, confirmation d'abandon)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Breadcrumbs, master-detail layout, route error view

**Files:**
- Create: `frontend/src/shared/layout/handle.ts`, `frontend/src/shared/layout/Breadcrumbs.tsx`, `frontend/src/shared/layout/MasterDetailLayout.tsx`, `frontend/src/shared/layout/RouteError.tsx`
- Modify: `frontend/src/shared/layout/AppShell.tsx` (lines 29–31 and the `<main>` block near line 216)
- Test: `frontend/src/shared/layout/Breadcrumbs.test.tsx`

**Interfaces:**
- Produces:
  - `interface HandleRoute { pleineLargeur?: boolean; fil?: string | ((params: Readonly<Params<string>>) => ReactNode) }`
  - `Breadcrumbs()` — renders nothing when fewer than 2 matches carry `fil`.
  - `MasterDetailLayout({ rail: ReactNode; railLabel?: string; detailActif: boolean; children: ReactNode })` — the rail is a `<nav>` when `railLabel` is given, a `<div>` otherwise.
  - `RouteError()` — for `errorElement`.

- [ ] **Step 1: Write the failing test**

`frontend/src/shared/layout/Breadcrumbs.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Breadcrumbs } from "./Breadcrumbs";
import type { HandleRoute } from "./handle";

function renderA(chemin: string) {
  const router = createMemoryRouter(
    [
      {
        element: (
          <>
            <Breadcrumbs />
            <Outlet />
          </>
        ),
        children: [
          {
            path: "/company",
            handle: { fil: "Tableau de bord" } satisfies HandleRoute,
            children: [
              { index: true, element: <p>accueil</p> },
              {
                path: "declarations",
                handle: { fil: "Mes déclarations" } satisfies HandleRoute,
                children: [
                  { index: true, element: <p>liste</p> },
                  {
                    path: ":rapportId",
                    handle: { fil: (p) => `Déclaration ${p.rapportId}` } satisfies HandleRoute,
                    element: <p>détail</p>,
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
    { initialEntries: [chemin] },
  );
  render(<RouterProvider router={router} />);
}

describe("Breadcrumbs", () => {
  it("construit le fil depuis les routes, la dernière étape sans lien", async () => {
    renderA("/company/declarations/fy2025");
    const fil = await screen.findByRole("navigation", { name: "Fil d’Ariane" });
    const liste = within(fil).getByRole("list");
    expect(within(liste).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute(
      "href",
      "/company",
    );
    expect(within(liste).getByRole("link", { name: "Mes déclarations" })).toHaveAttribute(
      "href",
      "/company/declarations",
    );
    expect(within(liste).getByText("Déclaration fy2025")).toHaveAttribute("aria-current", "page");
    // Au téléphone : un seul lien, vers le parent.
    expect(within(fil).getByRole("link", { name: /Retour à Mes déclarations/ })).toHaveAttribute(
      "href",
      "/company/declarations",
    );
  });

  it("aucun fil sur une page de premier niveau", async () => {
    renderA("/company");
    await screen.findByText("accueil");
    expect(screen.queryByRole("navigation", { name: "Fil d’Ariane" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/shared/layout/Breadcrumbs.test.tsx`
Expected: FAIL — unresolved imports.

- [ ] **Step 3: Implement `handle.ts` and `Breadcrumbs`**

`frontend/src/shared/layout/handle.ts`:

```ts
import type { ReactNode } from "react";
import type { Params } from "react-router-dom";

/** `handle` des routes de l'application. `fil` : libellé de la route dans le fil d'Ariane (spec
 * §2.2) — une fonction quand il dépend d'un paramètre ou d'une donnée (« Déclaration FY2025 »).
 * `pleineLargeur` : la page occupe toute la largeur (tâche 5.7). */
export interface HandleRoute {
  pleineLargeur?: boolean;
  fil?: string | ((params: Readonly<Params<string>>) => ReactNode);
}
```

`frontend/src/shared/layout/Breadcrumbs.tsx`:

```tsx
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useMatches } from "react-router-dom";
import type { HandleRoute } from "./handle";

interface Etape {
  chemin: string;
  contenu: ReactNode;
}

/** Fil d'Ariane (spec §2.2) : une étape par route qui déclare `handle.fil`. Masqué sur une page
 * de premier niveau ; au téléphone, réduit à un lien vers le niveau parent. */
export function Breadcrumbs() {
  const etapes: Etape[] = useMatches().flatMap((match) => {
    const fil = (match.handle as HandleRoute | undefined)?.fil;
    if (fil === undefined) return [];
    return [{ chemin: match.pathname, contenu: typeof fil === "string" ? fil : fil(match.params) }];
  });
  if (etapes.length < 2) return null;
  const parent = etapes[etapes.length - 2];

  return (
    <nav aria-label="Fil d’Ariane" className="mb-4">
      <Link
        to={parent.chemin}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground sm:hidden"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        <span className="sr-only">Retour à </span>
        {parent.contenu}
      </Link>
      <ol className="hidden flex-wrap items-center gap-1 text-sm text-muted-foreground sm:flex">
        {etapes.map((etape, i) => (
          <li key={etape.chemin} className="flex items-center gap-1">
            {i > 0 ? <ChevronRight className="size-3.5" aria-hidden="true" /> : null}
            {i === etapes.length - 1 ? (
              <span aria-current="page" className="font-medium text-foreground">
                {etape.contenu}
              </span>
            ) : (
              <Link to={etape.chemin} className="hover:text-foreground hover:underline">
                {etape.contenu}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
```

- [ ] **Step 4: Implement `MasterDetailLayout` and `RouteError`**

`frontend/src/shared/layout/MasterDetailLayout.tsx`:

```tsx
import type { ReactNode } from "react";
import { cn } from "@/shared/ui/cn";

/** Rail de sections + détail (spec §2.2), à la manière des réglages d'un téléphone : côte à côte
 * à partir de `md` ; en dessous, le rail est masqué dès qu'une section est ouverte (le fil
 * d'Ariane ramène au niveau du rail). */
export function MasterDetailLayout({
  rail,
  railLabel,
  detailActif,
  children,
}: {
  rail: ReactNode;
  /** Nomme le rail quand c'est une navigation ; omis quand le rail porte déjà la sienne
   * (WizardStepper). */
  railLabel?: string;
  detailActif: boolean;
  children: ReactNode;
}) {
  const Rail = railLabel ? "nav" : "div";
  return (
    <div className="grid gap-6 md:grid-cols-[16rem_minmax(0,1fr)]">
      <Rail aria-label={railLabel} className={cn(detailActif && "hidden md:block")}>
        {rail}
      </Rail>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
```

`frontend/src/shared/layout/RouteError.tsx`:

```tsx
import { FileWarning } from "lucide-react";
import { Link, useRouteError } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";

/** Erreur imprévue d'un niveau de navigation (spec §6) : message utile, reprise, identifiant de
 * corrélation copiable — jamais de pile ni de charge brute. */
export function RouteError() {
  const erreur = useRouteError();
  const correlation = erreur instanceof ApiError ? erreur.correlationId : null;
  return (
    <Card role="alert">
      <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
        <FileWarning className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium text-foreground">Cette section n’a pas pu s’afficher.</p>
        {correlation ? (
          <p className="text-xs text-muted-foreground">
            Référence : <code className="select-all font-mono">{correlation}</code>
          </p>
        ) : null}
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.location.reload()}>
            Réessayer
          </Button>
          <Button asChild variant="ghost">
            <Link to="..">Niveau précédent</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Wire into `AppShell`**

In `frontend/src/shared/layout/AppShell.tsx`:

1. Add imports: `import { Breadcrumbs } from "./Breadcrumbs";` and `import type { HandleRoute } from "./handle";`
2. Replace lines 29–31:

```tsx
  // Une route peut demander toute la largeur via `handle: { pleineLargeur: true }` (tâche 5.7).
  const pleineLargeur = useMatches().some(
    (match) => (match.handle as HandleRoute | undefined)?.pleineLargeur,
  );
```

3. In `<main id="app-content" …>`, render `<Breadcrumbs />` immediately before `<Outlet />`.

- [ ] **Step 6: Run tests, full checks, commit**

Run: `npx vitest run src/shared/layout` → PASS (Breadcrumbs 2 tests + existing roleNav tests).
Run: `npx biome check src && npx tsc -b && npx vitest run` → green. No existing page declares `fil`, so no other space changes.

```bash
git add frontend/src/shared/layout
git commit -m "feat(interface): fil d'Ariane depuis les routes, gabarit rail + détail, erreur de route

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `phaseDeclaration`

**Files:**
- Create: `frontend/src/shared/format/phaseDeclaration.ts`
- Test: `frontend/src/shared/format/phaseDeclaration.test.ts`

**Interfaces:**
- Consumes: `TonStatut` from `@/shared/ui/status-badge` (type-only import).
- Produces:
  - `PHASES_DECLARATION: readonly ["Déposé", "Analyse en cours", "En cours d’examen", "Audité"]`
  - `type BrancheDeclaration = "ANALYSE_IMPOSSIBLE" | "CORRECTION_DEMANDEE"`
  - `interface PhaseDeclaration { index: 0 | 1 | 2 | 3; libelle: string; ton: TonStatut; branche: BrancheDeclaration | null }`
  - `phaseDeclaration(rapport: { status: ReportStatus; extraction_error: string | null }): PhaseDeclaration`

- [ ] **Step 1: Write the failing test**

`frontend/src/shared/format/phaseDeclaration.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { PHASES_DECLARATION, phaseDeclaration } from "./phaseDeclaration";

const CAS: [ReportStatus, string | null, number, string, string, string | null][] = [
  ["DRAFT", null, 0, "Déposé", "neutre", null],
  ["DRAFT", "pdf_illisible", 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["EXTRACTING", null, 1, "Analyse en cours", "info", null],
  ["EXTRACTION_FAILED", "pdf_illisible", 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["EXTRACTION_FAILED", null, 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["AWAITING_ASSIGNMENT", null, 2, "En cours d’examen", "attention", null],
  ["IN_AUDIT", null, 2, "En cours d’examen", "attention", null],
  ["PENDING_DECISION", null, 2, "En cours d’examen", "attention", null],
  ["REVISION_REQUESTED", null, 2, "Correction demandée", "attention", "CORRECTION_DEMANDEE"],
  ["VALIDATED", null, 3, "Validé & publié", "succes", null],
  ["REJECTED", null, 3, "Refusé", "danger", null],
];

describe("phaseDeclaration", () => {
  it.each(CAS)("%s (erreur %s) → phase %i « %s »", (status, erreur, index, libelle, ton, branche) => {
    expect(phaseDeclaration({ status, extraction_error: erreur })).toEqual({
      index,
      libelle,
      ton,
      branche,
    });
  });

  it("une erreur d’analyse ancienne ne masque pas l’examen en cours", () => {
    expect(phaseDeclaration({ status: "IN_AUDIT", extraction_error: "quota_llm_epuise" }).index).toBe(2);
  });

  it("quatre phases, dans l’ordre du cycle", () => {
    expect(PHASES_DECLARATION).toEqual(["Déposé", "Analyse en cours", "En cours d’examen", "Audité"]);
  });

  it("aucun nom d’étape interne", () => {
    const libelles = CAS.map(([s, e]) => phaseDeclaration({ status: s, extraction_error: e }).libelle);
    for (const interne of ["affecter", "audit", "décision", "Extraction"]) {
      expect(libelles.join(" ")).not.toContain(interne);
    }
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/shared/format/phaseDeclaration.test.ts`
Expected: FAIL — unresolved import.

- [ ] **Step 3: Implement**

`frontend/src/shared/format/phaseDeclaration.ts`:

```ts
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import type { TonStatut } from "@/shared/ui/status-badge";

/** Les quatre phases d'une déclaration vues par l'Entreprise (spec §5.1). Les étapes internes
 * de l'examen (affectation, audit, décision) restent regroupées (décision 5.1). */
export const PHASES_DECLARATION = [
  "Déposé",
  "Analyse en cours",
  "En cours d’examen",
  "Audité",
] as const;

export type BrancheDeclaration = "ANALYSE_IMPOSSIBLE" | "CORRECTION_DEMANDEE";

export interface PhaseDeclaration {
  index: 0 | 1 | 2 | 3;
  libelle: string;
  ton: TonStatut;
  branche: BrancheDeclaration | null;
}

const ANALYSE_IMPOSSIBLE: PhaseDeclaration = {
  index: 1,
  libelle: "Analyse impossible",
  ton: "danger",
  branche: "ANALYSE_IMPOSSIBLE",
};

const EN_EXAMEN: PhaseDeclaration = {
  index: 2,
  libelle: "En cours d’examen",
  ton: "attention",
  branche: null,
};

export function phaseDeclaration(rapport: {
  status: ReportStatus;
  extraction_error: string | null;
}): PhaseDeclaration {
  switch (rapport.status) {
    case "DRAFT":
      return rapport.extraction_error !== null
        ? ANALYSE_IMPOSSIBLE
        : { index: 0, libelle: "Déposé", ton: "neutre", branche: null };
    case "EXTRACTING":
      return { index: 1, libelle: "Analyse en cours", ton: "info", branche: null };
    case "EXTRACTION_FAILED":
      return ANALYSE_IMPOSSIBLE;
    case "AWAITING_ASSIGNMENT":
    case "IN_AUDIT":
    case "PENDING_DECISION":
      return EN_EXAMEN;
    case "REVISION_REQUESTED":
      return { ...EN_EXAMEN, libelle: "Correction demandée", branche: "CORRECTION_DEMANDEE" };
    case "VALIDATED":
      return { index: 3, libelle: "Validé & publié", ton: "succes", branche: null };
    case "REJECTED":
      return { index: 3, libelle: "Refusé", ton: "danger", branche: null };
  }
}
```

- [ ] **Step 4: Run, full checks, commit**

Run: `npx vitest run src/shared/format/phaseDeclaration.test.ts` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run` → green.

```bash
git add frontend/src/shared/format/phaseDeclaration.ts frontend/src/shared/format/phaseDeclaration.test.ts
git commit -m "feat(interface): quatre phases d'une déclaration côté Entreprise

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `companyKeys`, list polling, notification-driven refresh

**Files:**
- Modify: `frontend/src/features/company/api.ts`
- Modify: `frontend/src/features/company/components/CompanyDashboardPage.tsx`, `frontend/src/features/company/components/CompanyDeclarationsPage.tsx` (one line each: call the new hook)
- Test: `frontend/src/features/company/api.test.tsx`

**Interfaces:**
- Produces:
  - `companyKeys` (`all`, `reports()`, `report(id)`, `checklist(id, analyseeLe)`, `profile()`, `lei(lei)`, `registrationStatus(token)`) — same key **values** as today, so no cache behaviour changes.
  - `rapportQueryOptions(rapportId: string)` — `queryOptions` for `getCompanyReport` with polling while `EXTRACTING`, `staleTime: 30_000`.
  - `useCompanyReport(rapportId)` keeps its signature (now `useQuery(rapportQueryOptions(rapportId))`).
  - `useCompanyReports()` polls every `DELAI_SUIVI_ANALYSE_MS` while any row is `EXTRACTING`; `staleTime: 30_000`.
  - `useActualisationSurNotification(): void`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/features/company/api.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  companyKeys,
  DELAI_SUIVI_ANALYSE_MS,
  useActualisationSurNotification,
  useCompanyReports,
} from "./api";

const fetchMock = vi.fn<typeof fetch>();

function ligne(status: string) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    company_id: "c",
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: null,
    status,
    source_file: "x.pdf",
    original_filename: "x.pdf",
    fiscal_year: 2025,
    extraction_finished_at: null,
    extraction_error: null,
    extraction_attempts: 0,
    version: 1,
    previous_report_id: null,
    checksum_sha256: null,
    synthesis_available: false,
  };
}

function enveloppe(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

function appelsListe() {
  return fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/company/rapports")).length;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useCompanyReports", () => {
  it("se rafraîchit tant qu’une analyse tourne, puis s’arrête", async () => {
    const reponses = [[ligne("EXTRACTING")], [ligne("DRAFT")]];
    fetchMock.mockImplementation(async () => Response.json(reponses.shift() ?? [ligne("DRAFT")]));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCompanyReports(), { wrapper: enveloppe(client) });
    await waitFor(() => expect(result.current.data?.[0].status).toBe("EXTRACTING"));

    await vi.advanceTimersByTimeAsync(DELAI_SUIVI_ANALYSE_MS);
    await waitFor(() => expect(result.current.data?.[0].status).toBe("DRAFT"));
    const apres = appelsListe();

    await vi.advanceTimersByTimeAsync(DELAI_SUIVI_ANALYSE_MS * 3);
    expect(appelsListe()).toBe(apres);
  });
});

describe("useActualisationSurNotification", () => {
  function compteur(total: number) {
    return Response.json({ items: [], total, page: 1, page_size: 1 });
  }

  it("invalide les déclarations quand le nombre de non-lues augmente, pas quand il baisse", async () => {
    const totaux = [1, 2, 0];
    fetchMock.mockImplementation(async () => compteur(totaux.shift() ?? 0));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalider = vi.spyOn(client, "invalidateQueries");
    renderHook(() => useActualisationSurNotification(), { wrapper: enveloppe(client) });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(invalider).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000); // 1 → 2
    await waitFor(() =>
      expect(invalider).toHaveBeenCalledWith({ queryKey: companyKeys.reports() }),
    );
    invalider.mockClear();

    await vi.advanceTimersByTimeAsync(60_000); // 2 → 0
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(invalider).not.toHaveBeenCalled();
  });
});
```

Check the shape `listMyNotifications` returns (`frontend/src/shared/api/generated/notifications/notifications.ts`) before running: `useUnreadNotificationsCount` reads `page.total`; if the page type has other required fields, add them to `compteur()`.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/api.test.tsx`
Expected: FAIL — `companyKeys`/`useActualisationSurNotification` not exported; the polling test times out on the third assertion window or fails the "stops" expectation.

- [ ] **Step 3: Implement in `api.ts`**

Edit `frontend/src/features/company/api.ts`:

1. Imports: change the first line to
   `import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";`
   and add `import { useEffect, useRef } from "react";` and
   `import { useUnreadNotificationsCount } from "@/shared/notifications/api";`
2. Replace the two key constants with:

```ts
/** Clés de requête de l'espace Entreprise (FRONTEND-ARCHITECTURE.md §3.2) : une fabrique typée,
 * mêmes valeurs qu'avant — un rapport est rangé sous la liste, invalider la liste l'invalide. */
export const companyKeys = {
  all: ["company"] as const,
  reports: () => [...companyKeys.all, "rapports"] as const,
  report: (rapportId: string) => [...companyKeys.reports(), rapportId] as const,
  checklist: (rapportId: string, analyseeLe: string | null) =>
    [...companyKeys.report(rapportId), "checklist", analyseeLe] as const,
  profile: () => [...companyKeys.all, "profil"] as const,
  lei: (lei: string | null | undefined) => [...companyKeys.all, "lei-verification", lei] as const,
  registrationStatus: (token: string | null) =>
    [...companyKeys.all, "registration-status", token] as const,
};

/** Les données d'un rapport changent à chaque étape d'examen : fraîches 30 s au plus. */
const FRAICHEUR_RAPPORTS_MS = 30_000;
```

3. Replace `useCompanyReports` and `useCompanyReport` with:

```ts
/** GET /company/rapports — la liste des rapports de l'entreprise connectée. Suivie tant qu'une
 * analyse tourne : tableau de bord et liste passent seuls à l'état suivant (spec §6). */
export function useCompanyReports() {
  return useQuery<RapportESGPublic[], ApiError>({
    queryKey: companyKeys.reports(),
    queryFn: () => listCompanyReports(),
    staleTime: FRAICHEUR_RAPPORTS_MS,
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "EXTRACTING") ? DELAI_SUIVI_ANALYSE_MS : false,
  });
}

/** Intervalle de rafraîchissement pendant l'analyse du fichier d'un brouillon (tâche 5.8). */
export const DELAI_SUIVI_ANALYSE_MS = 5000;

/** GET /company/rapports/{id} — une seule requête pour tous les niveaux d'une déclaration
 * (synthèse, pilier, indicateur : `select`). Suivie tant qu'une extraction est en cours. */
export function rapportQueryOptions(rapportId: string) {
  return queryOptions<RapportESGDetail, ApiError>({
    queryKey: companyKeys.report(rapportId),
    queryFn: () => getCompanyReport(rapportId),
    enabled: rapportId.length > 0,
    staleTime: FRAICHEUR_RAPPORTS_MS,
    refetchInterval: (query) =>
      query.state.data?.status === "EXTRACTING" ? DELAI_SUIVI_ANALYSE_MS : false,
  });
}

export function useCompanyReport(rapportId: string) {
  return useQuery(rapportQueryOptions(rapportId));
}

/** L'examen est fait par des personnes : pas de suivi périodique. Une décision produit une
 * notification ; quand le compteur de non-lues (déjà suivi chaque minute) augmente, les
 * déclarations sont relues (spec §6). Une baisse (lecture) ne déclenche rien. */
export function useActualisationSurNotification() {
  const queryClient = useQueryClient();
  const { data: nonLues } = useUnreadNotificationsCount();
  const precedent = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (nonLues === undefined) return;
    if (precedent.current !== undefined && nonLues > precedent.current) {
      queryClient.invalidateQueries({ queryKey: companyKeys.reports() });
    }
    precedent.current = nonLues;
  }, [nonLues, queryClient]);
}
```

4. Replace every remaining literal key in the file:
   - `[...reportQueryKey(rapportId), "checklist", analyseTermineeLe]` → `companyKeys.checklist(rapportId, analyseTermineeLe)`
   - `REPORTS_QUERY_KEY` → `companyKeys.reports()`; `reportQueryKey(x)` → `companyKeys.report(x)`
   - `["company", "profil"]` (2×) → `companyKeys.profile()`; add `staleTime: 5 * 60 * 1000` to `useMyCompanyProfile`
   - `["company", "lei-verification", lei]` → `companyKeys.lei(lei)`
   - `["company", "registration-status", token]` (2×) → `companyKeys.registrationStatus(token)`

5. In `CompanyDashboardPage` and `CompanyDeclarationsPage`, call `useActualisationSurNotification();` as the first line of the component (import from `../api`).

- [ ] **Step 4: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS (new tests + existing company tests unchanged).
Run: `npx biome check src && npx tsc -b && npx vitest run` → green. Run `grep -rn "\"company\", \"" src/features/company` → only `api.ts` `companyKeys.all`.

```bash
git add frontend/src/features/company
git commit -m "feat(company): fabrique de clés, suivi de la liste pendant l'analyse, relecture sur notification

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Taxonomy and `MetriqueVue` allowlist

**Files:**
- Create: `frontend/src/features/company/esg/taxonomie.ts`, `frontend/src/features/company/esg/vueMetrique.ts`
- Test: `frontend/src/features/company/esg/esg.test.ts`

**Interfaces:**
- Produces (`taxonomie.ts`):
  - `type SlugPilier = "environnement" | "social" | "gouvernance"`
  - `PILIERS: readonly { slug: SlugPilier; pilier: Pillar }[]`
  - `pilierDepuisSlug(slug: string | undefined): Pillar | null`, `slugPilier(pilier: Pillar): SlugPilier`
  - `interface Famille { slug: string; libelle: string; pilier: Pillar; codes: readonly string[] }`
  - `FAMILLE_AUTRES = "autres"`
  - `famillesDuPilier(pilier: Pillar): Famille[]` (listed families + the `autres` family with `codes: []`)
  - `familleDuCode(pilier: Pillar, code: string): string` (slug)
  - `pilierDuCode(code: string): Pillar | null` (known codes only)
  - `libelleFamille(pilier: Pillar, slug: string | undefined): string | null`
- Produces (`vueMetrique.ts`):
  - `interface PreuveVue { document: string; annee: number; pageDebut: number; pageFin: number }`
  - `interface MetriqueVue { id; cle; libelle; pilier; famille; valeur; unite; periode; methode; confiance; revue; valeurAuditee; preuve }` (types below)
  - `CLES_METRIQUE_VUE` (the exact key list)
  - `vueIndicateur(i: IndicateurESGDetail): MetriqueVue`, `vueCarbone(c: DonneeCarboneDetail): MetriqueVue`
  - `metriquesDuRapport(r: Pick<RapportESGDetail, "metrics" | "carbon_data">): MetriqueVue[]`
  - `libellePreuveVue(p: PreuveVue): string` → `"Rapport 2025 — p. 41–42"` / `"Rapport 2025 — p. 41"`

- [ ] **Step 1: Write the failing tests**

`frontend/src/features/company/esg/esg.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type {
  DonneeCarboneDetail,
  IndicateurESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  FAMILLE_AUTRES,
  familleDuCode,
  famillesDuPilier,
  pilierDepuisSlug,
  pilierDuCode,
} from "./taxonomie";
import { CLES_METRIQUE_VUE, libellePreuveVue, metriquesDuRapport, vueCarbone, vueIndicateur } from "./vueMetrique";

/** Codes cibles de l'extraction (app/ingestion/cibles.py) — à tenir à jour avec ce fichier. */
const CODES_CONNUS: Record<string, string> = {
  scope_1: "ENVIRONNEMENT",
  scope_2: "ENVIRONNEMENT",
  scope_2_market_based: "ENVIRONNEMENT",
  scope_2_location_based: "ENVIRONNEMENT",
  scope_3: "ENVIRONNEMENT",
  intensite_scope_1_2_marketbased: "ENVIRONNEMENT",
  intensite_scope_1_2_3_hors_cat11: "ENVIRONNEMENT",
  intensite_scope_1_2_3_total: "ENVIRONNEMENT",
  part_renouvelable_pourcentage: "ENVIRONNEMENT",
  dechets_valorises_pourcentage: "ENVIRONNEMENT",
  score_environnement_declare: "ENVIRONNEMENT",
  effectif_total: "SOCIAL",
  femmes_effectif_pourcentage: "SOCIAL",
  femmes_management_pourcentage: "SOCIAL",
  deces_professionnels: "SOCIAL",
  taux_frequence_accidents: "SOCIAL",
  heures_formation_par_employe: "SOCIAL",
  score_social_declare: "SOCIAL",
  taille_conseil: "GOUVERNANCE",
  administrateurs_independants_pourcentage: "GOUVERNANCE",
  femmes_conseil_pourcentage: "GOUVERNANCE",
  score_gouvernance_declare: "GOUVERNANCE",
};

const SENTINELLE = "SENTINELLE-NE-DOIT-PAS-FUIR";

const preuve = {
  id: "p1",
  document_name: "rapport-2025.pdf",
  year: 2025,
  total_pages: 80,
  page_start: 41,
  page_end: 42,
  excerpt_pdf_path: `/stockage/${SENTINELLE}.pdf`,
};

function indicateur(surcharges: Partial<IndicateurESGDetail> = {}): IndicateurESGDetail {
  return {
    id: "i1",
    pillar: "GOUVERNANCE",
    metric_code: "taille_conseil",
    value: 12,
    unit: "count",
    method: "RAPPORTEE",
    proof: preuve,
    raw_value: SENTINELLE,
    section: SENTINELLE,
    proof_text: SENTINELLE,
    value_year: 2025,
    confidence: "ELEVE",
    proof_boxes: [{ page: 41, x0: 0, y0: 0, x1: 1, y1: 1, sentinelle: SENTINELLE } as never],
    review_status: "ACCEPTED",
    audited_value: null,
    ...surcharges,
  };
}

function carbone(surcharges: Partial<DonneeCarboneDetail> = {}): DonneeCarboneDetail {
  return {
    id: "c1",
    scope: 2,
    ghg_category: "market_based",
    tonnes_co2e: 1500,
    year: 2025,
    method: "RAPPORTEE",
    pcaf_data_quality: null,
    proof: preuve,
    raw_value: SENTINELLE,
    section: SENTINELLE,
    proof_text: SENTINELLE,
    value_year: 2025,
    confidence: null,
    review_status: null,
    audited_value: null,
    ...surcharges,
  };
}

describe("taxonomie", () => {
  it.each(Object.entries(CODES_CONNUS))("%s → une famille nommée de son pilier", (code, pilier) => {
    expect(pilierDuCode(code)).toBe(pilier);
    expect(familleDuCode(pilier as never, code)).not.toBe(FAMILLE_AUTRES);
  });

  it("chaque code connu est dans une seule famille", () => {
    for (const pilier of ["ENVIRONNEMENT", "SOCIAL", "GOUVERNANCE"] as const) {
      const codes = famillesDuPilier(pilier).flatMap((f) => f.codes);
      expect(new Set(codes).size).toBe(codes.length);
    }
  });

  it("un code inconnu tombe dans « Autres indicateurs », jamais perdu", () => {
    expect(familleDuCode("SOCIAL", "nouveau_code_2027")).toBe(FAMILLE_AUTRES);
    expect(pilierDuCode("nouveau_code_2027")).toBeNull();
    expect(famillesDuPilier("SOCIAL").at(-1)).toMatchObject({ slug: FAMILLE_AUTRES });
  });

  it("slugs de pilier", () => {
    expect(pilierDepuisSlug("environnement")).toBe("ENVIRONNEMENT");
    expect(pilierDepuisSlug("ENVIRONNEMENT")).toBeNull();
    expect(pilierDepuisSlug(undefined)).toBeNull();
  });
});

describe("MetriqueVue — liste blanche", () => {
  it("n’a que les clés prévues", () => {
    expect(Object.keys(vueIndicateur(indicateur())).sort()).toEqual([...CLES_METRIQUE_VUE].sort());
    expect(Object.keys(vueCarbone(carbone())).sort()).toEqual([...CLES_METRIQUE_VUE].sort());
  });

  it("ne recopie aucun texte d’extraction ni chemin de stockage", () => {
    const vues = metriquesDuRapport({ metrics: [indicateur()], carbon_data: [carbone()] });
    expect(JSON.stringify(vues)).not.toContain(SENTINELLE);
  });

  it("place une ligne carbone par scope et méthode", () => {
    expect(vueCarbone(carbone())).toMatchObject({
      cle: "scope_2_market_based",
      pilier: "ENVIRONNEMENT",
      famille: "emissions-ges",
      valeur: 1500,
      unite: "tCO2e",
      periode: 2025,
    });
    expect(vueCarbone(carbone({ scope: 1, ghg_category: null })).cle).toBe("scope_1");
  });

  it("garde deux lignes de même scope (catégories différentes) distinctes", () => {
    const vues = metriquesDuRapport({
      metrics: [],
      carbon_data: [
        carbone({ id: "a", scope: 3, ghg_category: "cat1" }),
        carbone({ id: "b", scope: 3, ghg_category: "cat11" }),
      ],
    });
    expect(vues.map((v) => v.id)).toEqual(["a", "b"]);
    expect(new Set(vues.map((v) => v.cle)).size).toBe(2);
  });

  it("libellé de preuve", () => {
    expect(libellePreuveVue({ document: "x", annee: 2025, pageDebut: 41, pageFin: 42 })).toBe(
      "Rapport 2025 — p. 41–42",
    );
    expect(libellePreuveVue({ document: "x", annee: 2025, pageDebut: 7, pageFin: 7 })).toBe(
      "Rapport 2025 — p. 7",
    );
  });
});
```

If `ProofBox` in the generated schema rejects the literal above at type-check, the `as never` cast already bypasses it — keep the cast; the point is that unknown content inside `proof_boxes` never leaks.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/esg/esg.test.ts`
Expected: FAIL — unresolved imports.

- [ ] **Step 3: Implement `taxonomie.ts`**

```ts
import type { Pillar } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Taxonomie de navigation de l'espace Entreprise (spec §2.1) : pilier → famille → codes
 * d'indicateurs (app/ingestion/cibles.py). Un regroupement d'affichage, pas une règle de calcul :
 * le score ne lit que config/weights/default.yaml. Un code inconnu ici reste visible, dans la
 * famille « Autres indicateurs » de son pilier. */
export type SlugPilier = "environnement" | "social" | "gouvernance";

export const PILIERS: readonly { slug: SlugPilier; pilier: Pillar }[] = [
  { slug: "environnement", pilier: "ENVIRONNEMENT" },
  { slug: "social", pilier: "SOCIAL" },
  { slug: "gouvernance", pilier: "GOUVERNANCE" },
];

export function pilierDepuisSlug(slug: string | undefined): Pillar | null {
  return PILIERS.find((p) => p.slug === slug)?.pilier ?? null;
}

export function slugPilier(pilier: Pillar): SlugPilier {
  return PILIERS.find((p) => p.pilier === pilier)?.slug ?? "environnement";
}

export interface Famille {
  slug: string;
  libelle: string;
  pilier: Pillar;
  codes: readonly string[];
}

export const FAMILLE_AUTRES = "autres";

/** Les scores auto-déclarés restent une famille à part : jamais mêlés au score calculé
 * (config/weights/default.yaml). */
const FAMILLES: readonly Famille[] = [
  {
    slug: "emissions-ges",
    libelle: "Émissions GES",
    pilier: "ENVIRONNEMENT",
    codes: ["scope_1", "scope_2", "scope_2_market_based", "scope_2_location_based", "scope_3"],
  },
  {
    slug: "intensite-carbone",
    libelle: "Intensité carbone",
    pilier: "ENVIRONNEMENT",
    codes: [
      "intensite_scope_1_2_marketbased",
      "intensite_scope_1_2_3_hors_cat11",
      "intensite_scope_1_2_3_total",
    ],
  },
  {
    slug: "energie-ressources",
    libelle: "Énergie & ressources",
    pilier: "ENVIRONNEMENT",
    codes: ["part_renouvelable_pourcentage", "dechets_valorises_pourcentage"],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "ENVIRONNEMENT",
    codes: ["score_environnement_declare"],
  },
  {
    slug: "effectifs-diversite",
    libelle: "Effectifs & diversité",
    pilier: "SOCIAL",
    codes: ["effectif_total", "femmes_effectif_pourcentage", "femmes_management_pourcentage"],
  },
  {
    slug: "sante-securite",
    libelle: "Santé & sécurité",
    pilier: "SOCIAL",
    codes: ["deces_professionnels", "taux_frequence_accidents"],
  },
  {
    slug: "formation",
    libelle: "Formation",
    pilier: "SOCIAL",
    codes: ["heures_formation_par_employe"],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "SOCIAL",
    codes: ["score_social_declare"],
  },
  {
    slug: "conseil",
    libelle: "Conseil",
    pilier: "GOUVERNANCE",
    codes: [
      "taille_conseil",
      "administrateurs_independants_pourcentage",
      "femmes_conseil_pourcentage",
    ],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "GOUVERNANCE",
    codes: ["score_gouvernance_declare"],
  },
];

export function famillesDuPilier(pilier: Pillar): Famille[] {
  return [
    ...FAMILLES.filter((f) => f.pilier === pilier),
    { slug: FAMILLE_AUTRES, libelle: "Autres indicateurs", pilier, codes: [] },
  ];
}

export function familleDuCode(pilier: Pillar, code: string): string {
  return FAMILLES.find((f) => f.pilier === pilier && f.codes.includes(code))?.slug ?? FAMILLE_AUTRES;
}

export function pilierDuCode(code: string): Pillar | null {
  return FAMILLES.find((f) => f.codes.includes(code))?.pilier ?? null;
}

export function libelleFamille(pilier: Pillar, slug: string | undefined): string | null {
  return famillesDuPilier(pilier).find((f) => f.slug === slug)?.libelle ?? null;
}
```

- [ ] **Step 4: Implement `vueMetrique.ts`**

```ts
import type {
  ConfidenceLevel,
  DataMethod,
  DonneeCarboneDetail,
  IndicateurESGDetail,
  MetricReviewStatus,
  Pillar,
  PreuveDocumentairePublic,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleIndicateur, libelleScope } from "@/shared/format/indicateurs";
import { familleDuCode } from "./taxonomie";

/** Ce qu'un composant de l'espace Entreprise peut afficher d'une valeur extraite (spec §4.1).
 * Liste blanche construite champ par champ — jamais de copie d'objet : un champ ajouté au schéma
 * par le serveur reste invisible tant qu'il n'est pas explicitement repris ici. `proof_text`,
 * `raw_value`, `section`, `proof_boxes` et le chemin de stockage de l'extrait ne sont jamais
 * repris. */
export interface PreuveVue {
  document: string;
  annee: number;
  pageDebut: number;
  pageFin: number;
}

export interface MetriqueVue {
  id: string;
  cle: string;
  libelle: string;
  pilier: Pillar;
  famille: string;
  valeur: number;
  unite: string;
  periode: number | null;
  methode: DataMethod;
  confiance: ConfidenceLevel | null;
  revue: MetricReviewStatus | null;
  valeurAuditee: number | null;
  preuve: PreuveVue;
}

export const CLES_METRIQUE_VUE = [
  "id",
  "cle",
  "libelle",
  "pilier",
  "famille",
  "valeur",
  "unite",
  "periode",
  "methode",
  "confiance",
  "revue",
  "valeurAuditee",
  "preuve",
] as const satisfies readonly (keyof MetriqueVue)[];

function vuePreuve(preuve: PreuveDocumentairePublic): PreuveVue {
  return {
    document: preuve.document_name,
    annee: preuve.year,
    pageDebut: preuve.page_start,
    pageFin: preuve.page_end,
  };
}

export function vueIndicateur(i: IndicateurESGDetail): MetriqueVue {
  return {
    id: i.id,
    cle: i.metric_code,
    libelle: libelleIndicateur(i.metric_code),
    pilier: i.pillar,
    famille: familleDuCode(i.pillar, i.metric_code),
    valeur: i.value,
    unite: i.unit,
    periode: i.value_year,
    methode: i.method,
    confiance: i.confidence,
    revue: i.review_status ?? null,
    valeurAuditee: i.audited_value ?? null,
    preuve: vuePreuve(i.proof),
  };
}

/** Une ligne carbone prend le code cible de son scope (`scope_2_market_based`…) ; une autre
 * catégorie (Scope 3 par catégorie) garde une clé distincte. */
function cleCarbone(c: DonneeCarboneDetail): string {
  return c.ghg_category ? `scope_${c.scope}_${c.ghg_category}` : `scope_${c.scope}`;
}

export function vueCarbone(c: DonneeCarboneDetail): MetriqueVue {
  return {
    id: c.id,
    cle: cleCarbone(c),
    libelle: `Émissions ${libelleScope(c.scope, c.ghg_category)}`,
    pilier: "ENVIRONNEMENT",
    famille: "emissions-ges",
    valeur: c.tonnes_co2e,
    unite: "tCO2e",
    periode: c.year,
    methode: c.method,
    confiance: c.confidence,
    revue: c.review_status ?? null,
    valeurAuditee: c.audited_value ?? null,
    preuve: vuePreuve(c.proof),
  };
}

export function metriquesDuRapport(
  rapport: Pick<RapportESGDetail, "metrics" | "carbon_data">,
): MetriqueVue[] {
  return [...rapport.carbon_data.map(vueCarbone), ...rapport.metrics.map(vueIndicateur)];
}

export function libellePreuveVue(preuve: PreuveVue): string {
  const pages =
    preuve.pageDebut === preuve.pageFin
      ? `p. ${preuve.pageDebut}`
      : `p. ${preuve.pageDebut}–${preuve.pageFin}`;
  return `Rapport ${preuve.annee} — ${pages}`;
}
```

- [ ] **Step 5: Run, full checks, commit**

Run: `npx vitest run src/features/company/esg` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run` → green.

```bash
git add frontend/src/features/company/esg
git commit -m "feat(company): taxonomie pilier → famille et liste blanche d'affichage des valeurs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Nested routes, declaration layout (L3) and overview

**Files:**
- Create: `frontend/src/features/company/test/renderCompany.tsx`
- Create: `frontend/src/features/company/declaration/StatutDeclaration.tsx`, `ScoreOfficiel.tsx`, `FormulaireCorrection.tsx`, `RailDeclaration.tsx`, `DeclarationLayout.tsx`, `OverviewPage.tsx`, `FilDeclaration.tsx`, `resume.ts`
- Modify: `frontend/src/features/company/routes.tsx`
- Modify: `frontend/src/features/company/components/CompanyDeclarationsPage.tsx` (badge → `StatutDeclaration`)
- Delete: `frontend/src/features/company/components/CompanyReportDetailPage.tsx`
- Move + adapt: `frontend/src/features/company/components/CompanyReportDetailPage.test.tsx` → `frontend/src/features/company/declaration/Declaration.test.tsx`

**Interfaces:**
- Consumes: `rapportQueryOptions`, `useActualisationSurNotification`, `companyKeys` (Task 6); `phaseDeclaration`, `PHASES_DECLARATION` (Task 5); `StatusBadge`, `PhaseProgress` (Task 2); `MasterDetailLayout`, `RouteError`, `HandleRoute` (Task 4); `metriquesDuRapport`, `PILIERS`, `pilierDuCode`, `famillesDuPilier` (Task 7).
- Produces:
  - `companyEspaceRoutes: RouteObject[]` (the tree under `/company`, without `RequireRole`/`AppShell`) — used by tests and by later tasks to add children.
  - `renderCompany(chemin: string): { router; queryClient }` test helper.
  - `StatutDeclaration({ rapport: { status; extraction_error } })`.
  - `resumePilier(metriques: MetriqueVue[], manquants: readonly string[], pilier: Pillar): { trouves: number; attendus: number }`.
  - Draft declarations still render the existing `DraftPanel`/`SubmitDialog` inside the overview in this task (replaced in Task 10).

- [ ] **Step 1: Create the test helper**

`frontend/src/features/company/test/renderCompany.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { Breadcrumbs } from "@/shared/layout/Breadcrumbs";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { companyEspaceRoutes } from "../routes";

/** Monte l'arbre de routes de l'espace Entreprise (sans garde de rôle ni AppShell, qui
 * demanderaient /auth/me) avec le fil d'Ariane, dans un routeur de données en mémoire. */
export function renderCompany(chemin: string) {
  const router = createMemoryRouter(
    [
      {
        element: (
          <>
            <Breadcrumbs />
            <Outlet />
          </>
        ),
        children: companyEspaceRoutes,
      },
    ],
    { initialEntries: [chemin] },
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ConfirmProvider>
        <RouterProvider router={router} />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
  return { router, queryClient };
}
```

- [ ] **Step 2: Move the old page test and write the new failing tests**

`git mv frontend/src/features/company/components/CompanyReportDetailPage.test.tsx frontend/src/features/company/declaration/Declaration.test.tsx`, then in that file:

1. Delete the import of `CompanyReportDetailPage`, `MemoryRouter`, `Route`, `Routes`, `QueryClient`, `QueryClientProvider`, `ConfirmProvider`; add `import { renderCompany } from "../test/renderCompany";`.
2. Replace the body of `renderPage()` with `return renderCompany(`/company/declarations/${ID}`);`. The fetch mock must also answer the unread-notification count: at the top of every `fetchMock.mockImplementation`, add
   `if (String(url).includes("/notifications")) return Response.json({ items: [], total: 0, page: 1, page_size: 1 });`
   (add a helper `function notifications(url: unknown) { … }` returning that `Response` or `null`, and call it first in every mock implementation to avoid repeating the literal).
3. Any assertion on the old stepper (`getByRole("listitem", { current: "step" })` with text "Préparation"/"Examen"/"Décision") becomes an assertion on the new phase list:
   `expect(screen.getByRole("list", { name: "Progression" }).querySelector("[aria-current='step']")).toHaveTextContent("<phase>")`, with `Préparation` → `Déposé`, `Soumission`/`Examen` → `En cours d’examen`, `Décision` → `Audité` (or the branch label for `REVISION_REQUESTED`: assert `screen.getByText("Correction demandée")`).
4. Delete assertions on the tables "Indicateurs ESG" / "Données carbone" for submitted reports (they move to L4 in Task 9); keep the negative assertion that a draft shows no values.

Then append these new tests to the same file:

```tsx
describe("Déclaration — niveau 3 (synthèse)", () => {
  function soumis(surcharges: Record<string, unknown> = {}) {
    return rapport({
      status: "VALIDATED",
      submitted_at: "2026-09-02T10:30:00Z",
      official_score: {
        global_score: 64.2,
        environmental_score: 58,
        social_score: 71,
        governance_score: 66,
        coverage_rate: 0.8,
        config_version: 2,
      },
      metrics: [
        {
          id: "m1",
          pillar: "GOUVERNANCE",
          metric_code: "taille_conseil",
          value: 12,
          unit: "count",
          method: "RAPPORTEE",
          proof: { id: "p", document_name: "r.pdf", year: 2025, total_pages: 9, page_start: 4, page_end: 4, excerpt_pdf_path: "x" },
          raw_value: null,
          section: null,
          proof_text: null,
          value_year: 2025,
          confidence: "ELEVE",
          review_status: "ACCEPTED",
          audited_value: null,
        },
      ],
      coverage: { total_targets: 3, found: 1, missing_codes: ["femmes_conseil_pourcentage", "scope_1"] },
      ...surcharges,
    });
  }

  it("fil d’Ariane, phase, score et un accès par pilier — aucune table", async () => {
    fetchMock.mockImplementation(async (url) => notifications(url) ?? Response.json(soumis()));
    renderCompany(`/company/declarations/${ID}`);

    const fil = await screen.findByRole("navigation", { name: "Fil d’Ariane" });
    expect(within(fil).getByRole("link", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(within(fil).getByRole("link", { name: "Mes déclarations" })).toBeInTheDocument();

    expect(await screen.findByText("Validé & publié")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Score officiel" })).toHaveTextContent("64,2");

    const rail = screen.getByRole("navigation", { name: "Sections de la déclaration" });
    expect(within(rail).getByRole("link", { name: /Gouvernance/ })).toHaveTextContent("1/2");
    expect(within(rail).getByRole("link", { name: /Environnement/ })).toHaveTextContent("0/1");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("déclaration introuvable : message contextualisé et retour à la liste", async () => {
    fetchMock.mockImplementation(async (url) =>
      notifications(url) ??
      Response.json(
        { error: { code: "not_found", message: "Rapport introuvable.", correlation_id: "abc" } },
        { status: 404 },
      ),
    );
    renderCompany(`/company/declarations/${ID}`);
    expect(await screen.findByText("Déclaration introuvable")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour à mes déclarations" })).toHaveAttribute(
      "href",
      "/company/declarations",
    );
  });

  it("anciennes adresses redirigées", async () => {
    fetchMock.mockImplementation(async (url) => notifications(url) ?? Response.json(soumis()));
    const { router } = renderCompany(`/company/rapports/${ID}`);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/company/declarations/${ID}`),
    );
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npx vitest run src/features/company/declaration/Declaration.test.tsx`
Expected: FAIL — `companyEspaceRoutes` not exported.

- [ ] **Step 4: Create the small declaration components**

`frontend/src/features/company/declaration/StatutDeclaration.tsx`:

```tsx
import { CheckCircle2, CircleAlert, FileText, Loader2, Lock, XCircle } from "lucide-react";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { phaseDeclaration } from "@/shared/format/phaseDeclaration";
import { StatusBadge } from "@/shared/ui/status-badge";

/** Badge de phase d'une déclaration (spec §5.1) — remplace libelleStatutRapportEntreprise dans
 * l'espace Entreprise. */
export function StatutDeclaration({
  rapport,
}: {
  rapport: { status: ReportStatus; extraction_error: string | null };
}) {
  const phase = phaseDeclaration(rapport);
  const icone =
    phase.branche !== null
      ? CircleAlert
      : [FileText, Loader2, Lock, phase.ton === "danger" ? XCircle : CheckCircle2][phase.index];
  return (
    <StatusBadge
      libelle={phase.libelle}
      ton={phase.ton}
      icone={icone}
      enCours={rapport.status === "EXTRACTING"}
    />
  );
}
```

`frontend/src/features/company/declaration/ScoreOfficiel.tsx`: move the `arrondi` and `ScoreOfficiel` functions from `CompanyReportDetailPage.tsx` (the block starting `function arrondi(valeur: number)` through the end of `ScoreOfficiel`) verbatim, add `export` to `ScoreOfficiel`, and keep its imports (`ScoreESGPublic` type, `Card*`).

`frontend/src/features/company/declaration/FormulaireCorrection.tsx`: move `FormulaireCorrection` verbatim from `CompanyReportDetailPage.tsx` with `export`, plus `const ANNEE_COURANTE = new Date().getFullYear();` and its imports (`zodResolver`, `useState`, `useForm`, `ApiError`, `Alert*`, `Button`, `Card*`, `FileDrop`, `Form*`, `Input`, `useSubmitCorrection` from `../api`, `CorrectionForm`/`correctionSchema` from `../schemas`). Task 11 moves it into a sheet.

`frontend/src/features/company/declaration/resume.ts`:

```ts
import type { Pillar } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import type { MetriqueVue } from "../esg/vueMetrique";
import { pilierDuCode } from "../esg/taxonomie";

/** Trouvés / attendus d'un pilier : les valeurs présentes, plus les codes que le serveur
 * déclare manquants (coverage.missing_codes) et que la taxonomie range dans ce pilier. */
export function resumePilier(
  metriques: readonly MetriqueVue[],
  manquants: readonly string[],
  pilier: Pillar,
) {
  const trouves = metriques.filter((m) => m.pilier === pilier).length;
  const absents = manquants.filter((code) => pilierDuCode(code) === pilier).length;
  return { trouves, attendus: trouves + absents };
}
```

`frontend/src/features/company/declaration/FilDeclaration.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { idDepuisSlug } from "@/shared/format/slug";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { rapportQueryOptions } from "../api";

/** Libellé du fil d'Ariane d'une déclaration — lu dans le cache déjà rempli par la page. */
export function FilDeclaration({ segment }: { segment: string }) {
  const { data } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  return <>{data ? titreDeclaration(data) : "Déclaration"}</>;
}
```

- [ ] **Step 5: Create the rail, layout and overview**

`frontend/src/features/company/declaration/RailDeclaration.tsx`:

```tsx
import { NavLink } from "react-router-dom";
import type {
  Pillar,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libellePilier } from "@/shared/format/indicateurs";
import { cn } from "@/shared/ui/cn";
import { PILIERS } from "../esg/taxonomie";
import { metriquesDuRapport } from "../esg/vueMetrique";
import { resumePilier } from "./resume";

function sousScore(rapport: RapportESGDetail, pilier: Pillar): number | null {
  const score = rapport.official_score;
  if (!score) return null;
  return {
    ENVIRONNEMENT: score.environmental_score,
    SOCIAL: score.social_score,
    GOUVERNANCE: score.governance_score,
  }[pilier];
}

const lien = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm",
    isActive ? "bg-secondary font-medium text-foreground" : "text-muted-foreground hover:bg-muted",
  );

/** Rail d'une déclaration soumise (spec §2.2) : synthèse, puis un lien par pilier avec son
 * sous-score (une fois validée) et ses indicateurs trouvés / attendus. */
export function RailDeclaration({ rapport }: { rapport: RapportESGDetail }) {
  const metriques = metriquesDuRapport(rapport);
  return (
    <ul className="space-y-1">
      <li>
        <NavLink to="." end className={lien}>
          Vue d’ensemble
        </NavLink>
      </li>
      {PILIERS.map(({ slug, pilier }) => {
        const { trouves, attendus } = resumePilier(metriques, rapport.coverage.missing_codes, pilier);
        const score = sousScore(rapport, pilier);
        return (
          <li key={slug}>
            <NavLink to={slug} className={lien}>
              <span>{libellePilier(pilier)}</span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {score !== null ? `${Math.round(score)}/100 · ` : ""}
                {trouves}/{attendus}
              </span>
            </NavLink>
          </li>
        );
      })}
    </ul>
  );
}
```

`frontend/src/features/company/declaration/DeclarationLayout.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Download, FileWarning } from "lucide-react";
import { Link, Outlet, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { PHASES_DECLARATION, phaseDeclaration } from "@/shared/format/phaseDeclaration";
import { idDepuisSlug } from "@/shared/format/slug";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { MasterDetailLayout } from "@/shared/layout/MasterDetailLayout";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { PhaseProgress } from "@/shared/ui/phase-progress";
import { Skeleton } from "@/shared/ui/skeleton";
import { rapportQueryOptions, useActualisationSurNotification } from "../api";
import { libelleExercice } from "../session/etat";
import { RailDeclaration } from "./RailDeclaration";
import { StatutDeclaration } from "./StatutDeclaration";

function Introuvable() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
        <FileWarning className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium text-foreground">Déclaration introuvable</p>
        <p className="text-sm text-muted-foreground">
          Elle a peut-être été abandonnée, ou le lien est incomplet.
        </p>
        <Button asChild variant="outline">
          <Link to="/company/declarations">Retour à mes déclarations</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

/** Niveau 3 (spec §2.2) : en-tête de la déclaration, sa phase, puis rail des piliers + détail.
 * Une seule requête pour tous les niveaux inférieurs (rapportQueryOptions). */
export function DeclarationLayout() {
  const { rapportId: segment = "", pilier } = useParams();
  const { data: rapport, isPending, error } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  useActualisationSurNotification();

  if (isPending) {
    return (
      <div className="space-y-6" aria-busy="true">
        <Skeleton className="h-14 w-2/3" />
        <Skeleton className="h-8 w-full max-w-xl" />
        <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
          <Skeleton className="h-48" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }
  if (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) {
      return <Introuvable />;
    }
    throw error; // RouteError (errorElement) affiche le message et la référence.
  }

  const phase = phaseDeclaration(rapport);
  const branche =
    phase.branche === null ? null : { libelle: phase.libelle, ton: phase.ton === "danger" ? "danger" as const : "attention" as const };

  return (
    <div className="space-y-6">
      <PageHeader
        title={titreDeclaration(rapport)}
        description={
          <>
            {libelleExercice(rapport.fiscal_year)} · version {rapport.version}
            {rapport.previous_report_id ? " (correction)" : ""}
            {rapport.original_filename ? ` · ${rapport.original_filename}` : ""}
          </>
        }
        action={
          <>
            <StatutDeclaration rapport={rapport} />
            {rapport.synthesis_available ? (
              <Button asChild variant="outline" size="sm">
                <a href={`/api/v1/company/rapports/${rapport.id}/synthese/fichier`}>
                  <Download aria-hidden="true" />
                  Synthèse PDF
                </a>
              </Button>
            ) : null}
          </>
        }
      />
      <PhaseProgress etapes={PHASES_DECLARATION} courante={phase.index} branche={branche} />
      {rapport.status === "DRAFT" ? (
        <Outlet />
      ) : (
        <MasterDetailLayout
          railLabel="Sections de la déclaration"
          detailActif={pilier !== undefined}
          rail={<RailDeclaration rapport={rapport} />}
        >
          <Outlet />
        </MasterDetailLayout>
      )}
    </div>
  );
}
```

`frontend/src/features/company/declaration/OverviewPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { libellePilier } from "@/shared/format/indicateurs";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Card, CardContent } from "@/shared/ui/card";
import { rapportQueryOptions, useReportChecklist } from "../api";
import { PILIERS } from "../esg/taxonomie";
import { metriquesDuRapport } from "../esg/vueMetrique";
import { DraftPanel } from "../session/DraftPanel";
import { etatBrouillon } from "../session/etat";
import { LockBanner } from "../session/LockBanner";
import { SubmitDialog } from "../session/SubmitDialog";
import { FormulaireCorrection } from "./FormulaireCorrection";
import { resumePilier } from "./resume";
import { ScoreOfficiel } from "./ScoreOfficiel";

const DECISIONS = ["VALIDATED", "REJECTED", "REVISION_REQUESTED"];

/** Niveau 3, vue d'ensemble (spec §2.2) : verrouillage, score, puis un accès par pilier — les
 * valeurs elles-mêmes sont au niveau 4. Le brouillon garde temporairement son panneau (tâche 10
 * le remplace par l'assistant). */
export function OverviewPage() {
  const { rapportId: segment = "" } = useParams();
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  const [soumissionOuverte, setSoumissionOuverte] = useState(false);
  const etat = rapport ? etatBrouillon(rapport) : null;
  const liste = useReportChecklist(
    rapport?.id ?? "",
    etat === "PRET" ? (rapport?.extraction_finished_at ?? null) : null,
  );
  if (!rapport) return null; // DeclarationLayout gère chargement et erreur.

  const metriques = metriquesDuRapport(rapport);
  return (
    <div className="space-y-6">
      {rapport.extraction_error && rapport.status === "EXTRACTION_FAILED" ? (
        <Alert variant="destructive">
          <AlertTitle>Échec de la lecture du fichier</AlertTitle>
          <AlertDescription>{libelleCauseExtraction(rapport.extraction_error)}</AlertDescription>
        </Alert>
      ) : null}
      {rapport.submitted_at ? (
        <LockBanner
          submittedAt={rapport.submitted_at}
          checksum={rapport.checksum_sha256}
          close={DECISIONS.includes(rapport.status)}
        />
      ) : null}
      {etat ? (
        <>
          <DraftPanel
            rapport={rapport}
            etat={etat}
            groupes={liste.data}
            chargementListe={liste.isPending}
            onSoumettre={() => setSoumissionOuverte(true)}
          />
          <SubmitDialog
            rapport={rapport}
            groupes={liste.data ?? []}
            open={soumissionOuverte}
            onOpenChange={setSoumissionOuverte}
          />
        </>
      ) : null}
      {rapport.status === "VALIDATED" && rapport.official_score ? (
        <ScoreOfficiel score={rapport.official_score} />
      ) : null}
      {rapport.declared_global_score !== null ? (
        <p className="text-sm text-muted-foreground">
          Score ESG global auto-déclaré dans le rapport :{" "}
          <strong className="text-foreground">{rapport.declared_global_score}</strong> — affiché
          séparément, il n’entre pas dans le score calculé.
        </p>
      ) : null}
      {rapport.status === "REVISION_REQUESTED" ? (
        <FormulaireCorrection rapportId={rapport.id} exercice={rapport.fiscal_year} />
      ) : null}
      {etat ? null : (
        <ul className="grid gap-4 sm:grid-cols-3">
          {PILIERS.map(({ slug, pilier }) => {
            const { trouves, attendus } = resumePilier(
              metriques,
              rapport.coverage.missing_codes,
              pilier,
            );
            return (
              <li key={slug}>
                <Card className="h-full py-4">
                  <CardContent className="px-4">
                    <Link
                      to={slug}
                      className="flex items-center justify-between gap-3 rounded-md focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span>
                        <span className="block font-semibold text-foreground">
                          {libellePilier(pilier)}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {trouves}/{attendus} indicateur(s) trouvé(s)
                        </span>
                      </span>
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                    </Link>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
      <Outlet />
    </div>
  );
}
```

Check `declared_global_score`'s existing display in the deleted page (around its `ValeursExtraites` header) and reuse its exact number formatting if it differs from the raw value above.

- [ ] **Step 6: Restructure `routes.tsx`**

Replace `frontend/src/features/company/routes.tsx` with:

```tsx
import { Navigate, type RouteObject, useParams } from "react-router-dom";
import type { HandleRoute } from "@/shared/layout/handle";
import { AppShell } from "@/shared/layout/AppShell";
import { RouteError } from "@/shared/layout/RouteError";
import { RequireRole } from "@/shared/RequireRole";
import { CompanyDashboardPage } from "./components/CompanyDashboardPage";
import { CompanyDeclarationsPage } from "./components/CompanyDeclarationsPage";
import { ProfilePage } from "./components/ProfilePage";
import { RegistrationStatusPage } from "./components/RegistrationStatusPage";
import { DeclarationLayout } from "./declaration/DeclarationLayout";
import { FilDeclaration } from "./declaration/FilDeclaration";
import { OverviewPage } from "./declaration/OverviewPage";

/** Anciennes adresses d'un rapport (avant la tâche 5.9) : liens d'e-mails et favoris restent bons. */
function AncienneDeclaration() {
  const { rapportId } = useParams<{ rapportId: string }>();
  return <Navigate to={`/company/declarations/${rapportId}`} replace />;
}

/** Arbre de l'espace Entreprise (spec §2) : chaque niveau est une route imbriquée qui déclare
 * son libellé de fil d'Ariane. Exporté sans garde ni AppShell pour les tests. */
export const companyEspaceRoutes: RouteObject[] = [
  {
    path: "/company",
    handle: { fil: "Tableau de bord" } satisfies HandleRoute,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <CompanyDashboardPage /> },
      {
        path: "declarations",
        handle: { fil: "Mes déclarations" } satisfies HandleRoute,
        children: [
          { index: true, element: <CompanyDeclarationsPage /> },
          {
            path: ":rapportId",
            element: <DeclarationLayout />,
            errorElement: <RouteError />,
            handle: {
              fil: (params) => <FilDeclaration segment={params.rapportId ?? ""} />,
            } satisfies HandleRoute,
            children: [{ element: <OverviewPage />, children: [{ index: true }] }],
          },
        ],
      },
      {
        path: "profile",
        element: <ProfilePage />,
        handle: { fil: "Profil entreprise" } satisfies HandleRoute,
      },
      // Adresses d'avant la tâche 5.9.
      { path: "rapports", element: <Navigate to="/company/declarations" replace /> },
      { path: "rapports/:rapportId", element: <AncienneDeclaration /> },
      { path: "deposer", element: <Navigate to="/company/declarations" replace /> },
      { path: "profil", element: <Navigate to="/company/profile" replace /> },
    ],
  },
];

export const companyRoutes: RouteObject[] = [
  // L'inscription elle-même vit dans features/registration (tâche 5.10).
  // Publique : suivi de la demande, avec le jeton reçu par e-mail (tâche 5.2).
  { path: "/inscription-entreprise/suivi", element: <RegistrationStatusPage /> },
  {
    element: (
      <RequireRole allowedRoles={["ENTERPRISE"]}>
        <AppShell />
      </RequireRole>
    ),
    children: companyEspaceRoutes,
  },
];
```

- [ ] **Step 7: Delete the old page, switch list badges**

`git rm frontend/src/features/company/components/CompanyReportDetailPage.tsx`.

In `CompanyDeclarationsPage.tsx`, replace the `StatutEntreprise` component body with `<StatutDeclaration rapport={rapport} />` (import from `../declaration/StatutDeclaration`) and drop the now-unused `Badge`/`libelleStatutRapportEntreprise`/`variantStatutRapportEntreprise` imports. Then run
`grep -rn "libelleStatutRapportEntreprise\|variantStatutRapportEntreprise" src`
— if `CompanyDashboardPage.tsx` or `session/presentation.ts` still use them, leave them (Task 10 revisits the dashboard); do not delete functions that still have callers.

- [ ] **Step 8: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.

```bash
git add -A frontend/src/features/company
git commit -m "feat(company): routes imbriquées et niveau Déclaration (synthèse, rail des piliers)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Pillar page (L4) and metric sheet (L5)

**Files:**
- Create: `frontend/src/features/company/declaration/PillarPage.tsx`, `frontend/src/features/company/declaration/MetricSheet.tsx`
- Modify: `frontend/src/features/company/routes.tsx` (add the `:pilier` subtree)
- Test: `frontend/src/features/company/declaration/Pilier.test.tsx`

**Interfaces:**
- Consumes: `rapportQueryOptions` (Task 6), `pilierDepuisSlug`, `famillesDuPilier`, `libelleFamille`, `metriquesDuRapport`, `libellePreuveVue`, `MetriqueVue` (Task 7), `DisclosureCard` (Task 2), `RouteSheet` (Task 1), `renderCompany` (Task 8).
- Produces: routes `:rapportId/:pilier`, `:rapportId/:pilier/:famille`, `:rapportId/:pilier/:famille/:code`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/features/company/declaration/Pilier.test.tsx`:

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCompany } from "../test/renderCompany";

const ID = "77777777-7777-7777-7777-777777777777";
const SENTINELLE = "SENTINELLE-NE-DOIT-PAS-FUIR";
const fetchMock = vi.fn<typeof fetch>();

const preuve = {
  id: "p",
  document_name: "rapport-2025.pdf",
  year: 2025,
  total_pages: 80,
  page_start: 41,
  page_end: 42,
  excerpt_pdf_path: SENTINELLE,
};

function rapport(surcharges: Record<string, unknown> = {}) {
  return {
    id: ID,
    company_id: ID,
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: "2026-09-02T08:00:00Z",
    status: "IN_AUDIT",
    source_file: "x.pdf",
    original_filename: "rapport-2025.pdf",
    fiscal_year: 2025,
    extraction_finished_at: "2026-09-01T09:00:00Z",
    extraction_error: null,
    extraction_attempts: 1,
    version: 1,
    previous_report_id: null,
    checksum_sha256: null,
    declared_global_score: null,
    declared_global_score_proof: null,
    official_score: null,
    synthesis_available: false,
    coverage: { total_targets: 0, found: 0, missing_codes: [] },
    metrics: [],
    carbon_data: [
      {
        id: "c1",
        scope: 1,
        ghg_category: null,
        tonnes_co2e: 1200,
        year: 2025,
        method: "RAPPORTEE",
        pcaf_data_quality: null,
        proof: preuve,
        raw_value: SENTINELLE,
        section: SENTINELLE,
        proof_text: SENTINELLE,
        value_year: 2025,
        confidence: "ELEVE",
        review_status: "OVERRIDDEN",
        audited_value: 1250,
      },
    ],
    ...surcharges,
  };
}

function servir(corps: Record<string, unknown>) {
  fetchMock.mockImplementation(async (url) =>
    String(url).includes("/notifications")
      ? Response.json({ items: [], total: 0, page: 1, page_size: 1 })
      : Response.json(corps),
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("Pilier (niveau 4) et indicateur (niveau 5)", () => {
  it("lien profond vers une famille : ouverte, fil complet, aucune fuite", async () => {
    servir(rapport());
    renderCompany(`/company/declarations/${ID}/environnement/emissions-ges`);

    const famille = await screen.findByRole("region", { name: "Émissions GES" });
    expect(within(famille).getByRole("link", { name: /Émissions Scope 1/ })).toBeInTheDocument();
    const fil = screen.getByRole("navigation", { name: "Fil d’Ariane" });
    expect(within(fil).getByText("Émissions GES")).toHaveAttribute("aria-current", "page");
    expect(within(fil).getByRole("link", { name: "Environnement" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(SENTINELLE);
  });

  it("familles repliées : résumé visible, valeurs masquées ; un clic ouvre la famille dans l’URL", async () => {
    servir(rapport());
    const user = userEvent.setup();
    const { router } = renderCompany(`/company/declarations/${ID}/environnement`);
    const bouton = await screen.findByRole("button", { name: /Émissions GES/ });
    expect(bouton).toHaveTextContent("1/5 trouvé(s)");
    expect(screen.queryByText(/Émissions Scope 1/)).not.toBeInTheDocument();
    await user.click(bouton);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        `/company/declarations/${ID}/environnement/emissions-ges`,
      ),
    );
  });

  it("le tiroir d’un indicateur : valeur, revue, preuve vers le PDF d’origine — sans texte extrait", async () => {
    servir(rapport());
    const user = userEvent.setup();
    const { router } = renderCompany(
      `/company/declarations/${ID}/environnement/emissions-ges/scope_1`,
    );
    const tiroir = await screen.findByRole("dialog", { name: "Émissions Scope 1" });
    expect(tiroir).toHaveTextContent("1 200 tCO₂e");
    expect(tiroir).toHaveTextContent("Corrigée");
    expect(tiroir).toHaveTextContent("1 250 tCO₂e");
    const lien = within(tiroir).getByRole("link", { name: /Rapport 2025 — p\. 41–42/ });
    expect(lien).toHaveAttribute("href", `/api/v1/company/rapports/${ID}/fichier#page=41`);
    expect(lien).toHaveAttribute("target", "_blank");
    expect(document.body).not.toHaveTextContent(SENTINELLE);

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        `/company/declarations/${ID}/environnement/emissions-ges`,
      ),
    );
  });

  it("aucune valeur extraite : chaque famille le dit (Review Focus 2)", async () => {
    servir(rapport({ carbon_data: [] }));
    renderCompany(`/company/declarations/${ID}/social`);
    expect(await screen.findByRole("button", { name: /Effectifs & diversité/ })).toHaveTextContent(
      "Aucun indicateur trouvé",
    );
    expect(screen.queryByRole("button", { name: /Autres indicateurs/ })).not.toBeInTheDocument();
  });

  it("UUID nu dans l’adresse (anciens e-mails) : même page (Review Focus 1)", async () => {
    servir(rapport());
    renderCompany(`/company/declarations/${ID}/environnement`);
    expect(await screen.findByRole("button", { name: /Émissions GES/ })).toBeInTheDocument();
  });

  it("pilier, famille ou indicateur inconnus : absence dite, pas de redirection", async () => {
    servir(rapport());
    renderCompany(`/company/declarations/${ID}/climat`);
    expect(await screen.findByText("Section introuvable")).toBeInTheDocument();
  });

  it("indicateur inconnu : tiroir « introuvable »", async () => {
    servir(rapport());
    renderCompany(`/company/declarations/${ID}/environnement/emissions-ges/scope_9`);
    expect(await screen.findByRole("dialog", { name: "Indicateur introuvable" })).toBeInTheDocument();
  });
});
```

(The last-but-one test uses `ID` without slug prefix: that is the bare-UUID case. Add one test with a slugged segment, e.g. `rapport-esg-fy2025-${ID}`, if `creerSlug` produces such prefixes — it does, see `CompanyDeclarationsPage`.)

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/declaration/Pilier.test.tsx`
Expected: FAIL — routes don't match (overview renders, regions not found).

- [ ] **Step 3: Implement `PillarPage`**

`frontend/src/features/company/declaration/PillarPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, useNavigate, useParams } from "react-router-dom";
import {
  formatValeur,
  libelleMethode,
  libellePilier,
} from "@/shared/format/indicateurs";
import { libelleStatutRevue } from "@/shared/format/revue";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent } from "@/shared/ui/card";
import { DisclosureCard } from "@/shared/ui/disclosure-card";
import { rapportQueryOptions } from "../api";
import { FAMILLE_AUTRES, type Famille, famillesDuPilier, pilierDepuisSlug } from "../esg/taxonomie";
import { type MetriqueVue, metriquesDuRapport } from "../esg/vueMetrique";

function resumeFamille(famille: Famille, lignes: MetriqueVue[]): string {
  if (lignes.length === 0) return "Aucun indicateur trouvé";
  const attendus = famille.slug === FAMILLE_AUTRES ? lignes.length : famille.codes.length;
  const trouves = new Set(lignes.map((m) => m.cle)).size;
  const enRevue = lignes.filter((m) => m.revue === "PENDING").length;
  const parties = [`${trouves}/${attendus} trouvé(s)`];
  if (enRevue > 0) parties.push(`${enRevue} en revue`);
  if (famille.slug === "emissions-ges") {
    const valeur = (cle: string) => lignes.find((m) => m.cle === cle)?.valeur;
    const scope1 = valeur("scope_1");
    const scope2 = valeur("scope_2_market_based") ?? valeur("scope_2");
    if (scope1 !== undefined && scope2 !== undefined) {
      parties.push(`Scopes 1 + 2 : ${formatValeur(scope1 + scope2, "tCO2e")}`);
    }
  }
  return parties.join(" · ");
}

export function SectionIntrouvable({ texte }: { texte: string }) {
  return (
    <Card>
      <CardContent className="space-y-2 py-6 text-center">
        <p className="font-medium text-foreground">Section introuvable</p>
        <p className="text-sm text-muted-foreground">{texte}</p>
        <Link to=".." relative="path" className="text-sm underline">
          Revenir à la déclaration
        </Link>
      </CardContent>
    </Card>
  );
}

/** Niveau 4 (spec §2.2) : un pilier, une carte repliable par famille. La famille ouverte est
 * dans l'URL (…/:pilier/:famille) ; un indicateur s'ouvre en tiroir (…/:famille/:code). */
export function PillarPage() {
  const { rapportId: segment = "", pilier: slug, famille: familleOuverte } = useParams();
  const navigate = useNavigate();
  const pilier = pilierDepuisSlug(slug);
  const { data: metriques } = useQuery({
    ...rapportQueryOptions(idDepuisSlug(segment)),
    select: metriquesDuRapport,
  });
  if (!pilier) return <SectionIntrouvable texte="Ce pilier n’existe pas." />;
  if (!metriques) return null;

  const base = `/company/declarations/${segment}/${slug}`;
  const familles = famillesDuPilier(pilier)
    .map((famille) => ({
      famille,
      lignes: metriques.filter((m) => m.pilier === pilier && m.famille === famille.slug),
    }))
    .filter(({ famille, lignes }) => famille.slug !== FAMILLE_AUTRES || lignes.length > 0);
  const familleInconnue =
    familleOuverte !== undefined && !familles.some(({ famille }) => famille.slug === familleOuverte);

  return (
    <section aria-labelledby="titre-pilier" className="space-y-4">
      <h2 id="titre-pilier" className="text-lg font-semibold text-foreground">
        {libellePilier(pilier)}
      </h2>
      {familleInconnue ? (
        <Alert>
          <AlertDescription>Cette famille d’indicateurs n’existe pas dans ce pilier.</AlertDescription>
        </Alert>
      ) : null}
      {familles.map(({ famille, lignes }) => (
        <DisclosureCard
          key={famille.slug}
          id={`famille-${famille.slug}`}
          titre={famille.libelle}
          resume={resumeFamille(famille, lignes)}
          ouvert={familleOuverte === famille.slug}
          onOuvertChange={(ouvert) =>
            navigate(ouvert ? `${base}/${famille.slug}` : base, { preventScrollReset: true })
          }
        >
          {lignes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune valeur de cette famille n’a été trouvée dans le rapport.
            </p>
          ) : (
            <ul className="divide-y">
              {lignes.map((m) => (
                <li key={m.id}>
                  <Link
                    to={`${base}/${famille.slug}/${m.cle}`}
                    preventScrollReset
                    className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="font-medium text-foreground">{m.libelle}</span>
                    <span className="flex items-center gap-2 tabular-nums">
                      {formatValeur(m.valeur, m.unite)}
                      {m.periode !== null ? (
                        <span className="text-muted-foreground">· {m.periode}</span>
                      ) : null}
                      <Badge variant="outline">{libelleMethode(m.methode)}</Badge>
                      {m.revue ? <Badge variant="secondary">{libelleStatutRevue(m.revue)}</Badge> : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </DisclosureCard>
      ))}
      <Outlet />
    </section>
  );
}
```

If the deep-link test shows `famille` as `undefined` inside `PillarPage` (React Router not exposing child params to the parent element in this version), replace the `useParams()` destructuring of `famille` with:
`const familleOuverte = useMatches().at(-1)?.params.famille;` (import `useMatches`). Re-run the test.

- [ ] **Step 4: Implement `MetricSheet`**

`frontend/src/features/company/declaration/MetricSheet.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useParams } from "react-router-dom";
import type { ConfidenceLevel } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { formatValeur, libelleMethode } from "@/shared/format/indicateurs";
import { libelleStatutRevue } from "@/shared/format/revue";
import { idDepuisSlug } from "@/shared/format/slug";
import { RouteSheet } from "@/shared/ui/route-sheet";
import { SheetBody, SheetFields, SheetSection } from "@/shared/ui/sheet";
import { rapportQueryOptions } from "../api";
import { libellePreuveVue, metriquesDuRapport } from "../esg/vueMetrique";

const CONFIANCE: Record<ConfidenceLevel, string> = {
  ELEVE: "Élevée",
  MOYEN: "Moyenne",
  FAIBLE: "Faible",
};

/** Niveau 5 (spec §2.2) : une valeur, sa qualité, sa revue et la page du rapport d'origine où
 * elle figure. Jamais le texte extrait (spec §4.1). */
export function MetricSheet() {
  const { rapportId: segment = "", pilier, famille, code } = useParams();
  const rapportId = idDepuisSlug(segment);
  const { data: metrique, isPending } = useQuery({
    ...rapportQueryOptions(rapportId),
    select: (rapport) =>
      metriquesDuRapport(rapport).find((m) => m.cle === code && m.famille === famille) ?? null,
  });
  if (isPending) return null;
  const retour = `/company/declarations/${segment}/${pilier}/${famille}`;

  if (!metrique) {
    return (
      <RouteSheet retour={retour} titre="Indicateur introuvable">
        <SheetBody>
          <p className="text-sm text-muted-foreground">
            Cet indicateur ne figure pas dans cette déclaration.
          </p>
        </SheetBody>
      </RouteSheet>
    );
  }
  return (
    <RouteSheet retour={retour} titre={metrique.libelle}>
      <SheetBody>
        <SheetSection titre="Valeur">
          <SheetFields
            champs={[
              { libelle: "Valeur lue", valeur: formatValeur(metrique.valeur, metrique.unite) },
              { libelle: "Période", valeur: metrique.periode },
              { libelle: "Méthode", valeur: libelleMethode(metrique.methode) },
              {
                libelle: "Confiance",
                valeur: metrique.confiance ? CONFIANCE[metrique.confiance] : null,
              },
            ]}
          />
        </SheetSection>
        <SheetSection titre="Revue de l’auditeur">
          <SheetFields
            champs={[
              {
                libelle: "Statut",
                valeur: metrique.revue ? libelleStatutRevue(metrique.revue) : "Pas encore revue",
              },
              {
                libelle: "Valeur retenue",
                valeur:
                  metrique.valeurAuditee !== null
                    ? formatValeur(metrique.valeurAuditee, metrique.unite)
                    : null,
              },
            ]}
          />
        </SheetSection>
        <SheetSection titre="Source">
          <a
            href={`/api/v1/company/rapports/${rapportId}/fichier#page=${metrique.preuve.pageDebut}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-foreground underline-offset-2 hover:underline"
          >
            {libellePreuveVue(metrique.preuve)}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        </SheetSection>
      </SheetBody>
    </RouteSheet>
  );
}
```

- [ ] **Step 5: Add the routes**

In `routes.tsx`, import `PillarPage`, `MetricSheet`, `pilierDepuisSlug`, `libelleFamille` and `libellePilier`, and add after the overview child of `:rapportId`:

```tsx
              {
                path: ":pilier",
                element: <PillarPage />,
                errorElement: <RouteError />,
                handle: {
                  fil: (params) => {
                    const pilier = pilierDepuisSlug(params.pilier);
                    return pilier ? libellePilier(pilier) : "Section";
                  },
                } satisfies HandleRoute,
                children: [
                  {
                    path: ":famille",
                    handle: {
                      fil: (params) => {
                        const pilier = pilierDepuisSlug(params.pilier);
                        return (pilier && libelleFamille(pilier, params.famille)) ?? "Famille";
                      },
                    } satisfies HandleRoute,
                    children: [{ path: ":code", element: <MetricSheet /> }],
                  },
                ],
              },
```

- [ ] **Step 6: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.

```bash
git add frontend/src/features/company
git commit -m "feat(company): niveau Pilier en familles repliables et tiroir d'indicateur

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: New-declaration and draft wizard

**Files:**
- Create: `frontend/src/features/company/wizard/etapes.ts`, `NewDeclarationWizard.tsx`, `DraftStepPage.tsx`, `DocumentStep.tsx`, `VerificationStep.tsx`
- Modify: `frontend/src/features/company/schemas.ts` (`ouvrirDeclarationSchema`: currency optional)
- Modify: `frontend/src/features/company/session/etat.ts` (add `etapeReprise`; remove `ETAPES`, `etapeCourante`)
- Modify: `frontend/src/features/company/declaration/DeclarationLayout.tsx`, `OverviewPage.tsx`, `routes.tsx`
- Modify: `frontend/src/features/company/components/CompanyDeclarationsPage.tsx`, `CompanyDashboardPage.tsx`
- Delete: `frontend/src/features/company/session/NewDeclarationDialog.tsx`, `DraftPanel.tsx`, `SubmitDialog.tsx`, `SessionStepper.tsx`
- Test: `frontend/src/features/company/wizard/Wizard.test.tsx`; update `declaration/Declaration.test.tsx`, `components/CompanyDeclarationsPage.test.tsx`, `components/CompanyDashboardPage.test.tsx`

**Interfaces:**
- Consumes: `WizardStepper`, `useConfirmationAbandon` (Task 3); `useOpenDeclaration`, `useAttachDraftFile`, `useSubmitDraft`, `useReportChecklist`, `useCompanyReports`, `rapportQueryOptions` (existing / Task 6); `CompletenessChecklist`, `separerDeclarations`, `etatBrouillon` (existing).
- Produces:
  - `ETAPES_DECLARATION: readonly EtapeWizard[]` = exercice, finances, document, verification.
  - `etapeReprise(rapport: RapportSession): "document" | "verification"` in `session/etat.ts`.
  - `corpsOuverture(valeurs: OuvrirDeclarationForm): ReportCreateRequest` in `schemas.ts`.
  - routes `declarations/nouvelle/:etape` (+ `declarations/nouvelle` → `exercice`) and `:rapportId/brouillon/:etape`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/features/company/wizard/Wizard.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCompany } from "../test/renderCompany";

const ID = "88888888-8888-8888-8888-888888888888";
const SHA = "b".repeat(64);
const fetchMock = vi.fn<typeof fetch>();

function brouillon(surcharges: Record<string, unknown> = {}) {
  return {
    id: ID,
    company_id: ID,
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: null,
    status: "DRAFT",
    source_file: null,
    original_filename: null,
    fiscal_year: 2025,
    extraction_finished_at: null,
    extraction_error: null,
    extraction_attempts: 0,
    version: 1,
    previous_report_id: null,
    checksum_sha256: null,
    metrics: [],
    carbon_data: [],
    declared_global_score: null,
    declared_global_score_proof: null,
    official_score: null,
    synthesis_available: false,
    coverage: { total_targets: 0, found: 0, missing_codes: [] },
    ...surcharges,
  };
}

function reponse(r: ReturnType<typeof brouillon>) {
  return {
    id: r.id,
    company_id: r.company_id,
    report_type: "RAPPORT_ESG",
    fiscal_year: r.fiscal_year,
    status: r.status,
    version: 1,
    previous_report_id: null,
    created_at: r.created_at,
    submitted_at: r.submitted_at,
    original_filename: r.original_filename,
    official_score: null,
    checksum_sha256: r.checksum_sha256,
    extraction_finished_at: r.extraction_finished_at,
    extraction_error: r.extraction_error,
  };
}

/** Un faux serveur : liste, détail, ouverture, soumission, liste de complétude. */
function serveur(initial: ReturnType<typeof brouillon> | null, liste: unknown[] = []) {
  let etat = initial;
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    const methode = init?.method ?? "GET";
    if (chemin.includes("/notifications")) return Response.json({ items: [], total: 0, page: 1, page_size: 1 });
    if (chemin.endsWith("/checklist")) return Response.json([{ group: "SOCIAL", expected: 6, found: 4 }]);
    if (methode === "POST" && chemin.endsWith("/reports")) {
      etat = brouillon();
      return Response.json(reponse(etat), { status: 201 });
    }
    if (methode === "POST" && chemin.endsWith("/submit") && etat) {
      etat = { ...etat, status: "AWAITING_ASSIGNMENT", submitted_at: "2026-09-02T10:30:00Z" };
      return Response.json(reponse(etat), { status: 202 });
    }
    if (chemin.endsWith("/company/rapports")) return Response.json(liste);
    return Response.json(etat);
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function appels(methode: string, suffixe: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => (init?.method ?? "GET") === methode && String(url).endsWith(suffixe),
  );
}

describe("Nouvelle déclaration — assistant", () => {
  it("étape par étape ; le brouillon n’est créé qu’en quittant l’étape 2", async () => {
    serveur(null);
    const user = userEvent.setup();
    const { router } = renderCompany("/company/declarations/nouvelle/exercice");

    expect(await screen.findByLabelText("Exercice fiscal")).toBeInTheDocument();
    expect(screen.queryByLabelText("Devise")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Suivant" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/company/declarations/nouvelle/finances"),
    );
    expect(appels("POST", "/reports")).toHaveLength(0);

    // Les montants n'apparaissent qu'une devise choisie.
    expect(screen.queryByLabelText("Chiffre d’affaires")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Devise"), "EUR");
    await user.type(screen.getByLabelText("Chiffre d’affaires"), "1000000");

    await user.click(screen.getByRole("button", { name: "Précédent" }));
    await user.click(await screen.findByRole("button", { name: "Suivant" }));
    expect(screen.getByLabelText("Chiffre d’affaires")).toHaveValue(1000000);

    await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() => expect(appels("POST", "/reports")).toHaveLength(1));
    const corps = JSON.parse(String(appels("POST", "/reports")[0][1]?.body));
    expect(corps).toMatchObject({ currency: "EUR", revenue: 1000000 });
    await waitFor(() =>
      expect(router.state.location.pathname).toMatch(/\/brouillon\/document$/),
    );
  });

  it("sans devise : aucun montant envoyé", async () => {
    serveur(null);
    const user = userEvent.setup();
    renderCompany("/company/declarations/nouvelle/finances");
    await user.click(await screen.findByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() => expect(appels("POST", "/reports")).toHaveLength(1));
    const corps = JSON.parse(String(appels("POST", "/reports")[0][1]?.body));
    expect(corps).not.toHaveProperty("revenue");
    expect(corps).not.toHaveProperty("currency");
  });

  it("une déclaration déjà en cours bloque aussi l’adresse directe", async () => {
    serveur(null, [brouillon()]);
    renderCompany("/company/declarations/nouvelle/exercice");
    expect(await screen.findByText(/Une seule déclaration à la fois/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Exercice fiscal")).not.toBeInTheDocument();
  });
});

describe("Brouillon — document puis vérification", () => {
  it("reprise : un brouillon prêt ouvre la vérification ; soumission puis reçu", async () => {
    serveur(
      brouillon({
        source_file: "x.pdf",
        original_filename: "rapport-2025.pdf",
        extraction_finished_at: "2026-09-01T09:00:00Z",
        checksum_sha256: SHA,
      }),
    );
    const user = userEvent.setup();
    const { router } = renderCompany(`/company/declarations/${ID}`);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/company/declarations/${ID}/brouillon/verification`),
    );
    expect(await screen.findByRole("region", { name: "Liste de complétude" })).toHaveTextContent("4/6");

    const soumettre = screen.getByRole("button", { name: "Soumettre la déclaration" });
    expect(soumettre).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /verrouillée/ }));
    await user.click(soumettre);
    const recu = await screen.findByRole("region", { name: "Reçu de soumission" });
    expect(recu).toHaveTextContent(SHA);
    expect(appels("POST", "/submit")).toHaveLength(1);
  });

  it("vérification demandée pendant l’analyse : renvoyée au document (Review Focus 3)", async () => {
    serveur(brouillon({ status: "EXTRACTING", source_file: "x.pdf" }));
    const { router } = renderCompany(`/company/declarations/${ID}/brouillon/verification`);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/company/declarations/${ID}/brouillon/document`),
    );
    expect(await screen.findByText(/en cours/)).toBeInTheDocument();
  });

  it("analyse en échec : cause dite, nouveau fichier possible", async () => {
    serveur(brouillon({ source_file: "x.pdf", extraction_error: "pdf_illisible" }));
    renderCompany(`/company/declarations/${ID}/brouillon/document`);
    expect(await screen.findByText("Le fichier n’a pas pu être lu")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyser ce fichier" })).toBeInTheDocument();
  });
});
```

(`extraction_error: "pdf_illisible"` must be a code that `libelleCauseExtraction` knows; open `src/shared/format/causeExtraction.ts` and use one of its keys.)

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/wizard/Wizard.test.tsx`
Expected: FAIL — routes `nouvelle/*` and `brouillon/*` do not exist.

- [ ] **Step 3: Schema and state helpers**

In `schemas.ts`, make the currency optional in `ouvrirDeclarationSchema`. Only that line changes. Don't add a `.transform`: it would split the form's input and output types (see the comment above `anneeReportingSchema`).

```ts
  // Facultative : sans devise, ni chiffre d'affaires ni valeur d'entreprise (spec §3.1).
  currency: z.enum(Currency).optional(),
```

Below the schema, add the payload builder the wizard uses (import `type ReportCreateRequest` from the generated schemas):

```ts
/** Corps de POST /reports : les montants ne partent qu'avec leur devise — un montant saisi puis
 * masqué (devise retirée) n'est jamais envoyé. */
export function corpsOuverture(valeurs: OuvrirDeclarationForm): ReportCreateRequest {
  const { currency, revenue, enterprise_value, ...base } = valeurs;
  return currency ? { ...base, currency, revenue, enterprise_value } : base;
}
```

In `session/etat.ts`: delete `ETAPES` and `etapeCourante` (and the now-unused `DECISIONS` constant if only used there), and add:

```ts
/** Étape où reprendre un brouillon (spec §3.1) : la vérification seulement une fois le fichier
 * analysé sans erreur ; sinon le document. */
export function etapeReprise(rapport: RapportSession): "document" | "verification" {
  return etatBrouillon(rapport) === "PRET" ? "verification" : "document";
}
```

Run `grep -rn "etapeCourante\|ETAPES\b" src` → only the files deleted in Step 6.

- [ ] **Step 4: Wizard components**

`frontend/src/features/company/wizard/etapes.ts`:

```ts
import type { EtapeWizard } from "@/shared/ui/wizard";

/** Les quatre étapes d'une déclaration (spec §3.1) : les deux premières avant que le brouillon
 * n'existe, les deux dernières sur le brouillon. */
export const ETAPES_DECLARATION: readonly EtapeWizard[] = [
  { id: "exercice", titre: "Exercice" },
  { id: "finances", titre: "Données financières" },
  { id: "document", titre: "Document" },
  { id: "verification", titre: "Vérification" },
];
```

`frontend/src/features/company/wizard/NewDeclarationWizard.tsx` — build it from `session/NewDeclarationDialog.tsx` (same `EXERCICES` list, same field components, labels and `montant()` helper), changing only the structure:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { creerSlug } from "@/shared/format/slug";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { PageHeader } from "@/shared/ui/page-header";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { useConfirmationAbandon, WizardStepper } from "@/shared/ui/wizard";
import { useCompanyReports, useOpenDeclaration } from "../api";
import {
  corpsOuverture,
  DEVISES,
  type OuvrirDeclarationForm,
  ouvrirDeclarationSchema,
  TYPES_RAPPORT,
} from "../schemas";
import { separerDeclarations } from "../session/etat";
import { ETAPES_DECLARATION } from "./etapes";

const ANNEE_COURANTE = new Date().getFullYear();
const EXERCICES = Array.from({ length: 6 }, (_, i) => ANNEE_COURANTE - i);
const CHAMPS = {
  exercice: ["fiscal_year", "report_type"],
  finances: ["currency", "revenue", "enterprise_value"],
} as const;

/** Étapes 1 et 2 d'une déclaration (spec §3.1) : rien n'existe côté serveur avant « Créer le
 * brouillon » ; un seul formulaire pour les deux étapes, validé étape par étape. */
export function NewDeclarationWizard() {
  const { etape = "exercice" } = useParams();
  const { data: rapports, isPending } = useCompanyReports();
  if (etape !== "exercice" && etape !== "finances") {
    return <Navigate to="/company/declarations/nouvelle/exercice" replace />;
  }
  if (isPending || !rapports) return <Skeleton className="h-64 w-full" />;
  const { sessionBloquante } = separerDeclarations(rapports);
  const exercicesExclus = rapports
    .filter((r) => r.status === "VALIDATED" && r.fiscal_year !== null)
    .map((r) => r.fiscal_year as number);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Nouvelle déclaration"
        description="Rien n’est transmis avant la soumission ; le brouillon reste modifiable jusque-là."
      />
      {sessionBloquante ? (
        <Alert role="note" className="bg-muted/50">
          <Info className="text-primary" aria-hidden="true" />
          <AlertDescription>
            <span className="font-medium text-foreground">Une seule déclaration à la fois.</span>{" "}
            Terminez la déclaration{" "}
            <Link
              className="underline"
              to={`/company/declarations/${creerSlug(titreDeclaration(sessionBloquante), sessionBloquante.id)}`}
            >
              {titreDeclaration(sessionBloquante)}
            </Link>{" "}
            avant d’en ouvrir une autre.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid gap-6 md:grid-cols-[14rem_minmax(0,1fr)]">
          <WizardStepper etapes={ETAPES_DECLARATION} courante={etape} />
          <Formulaire etape={etape} exercicesExclus={exercicesExclus} />
        </div>
      )}
    </div>
  );
}

function Formulaire({
  etape,
  exercicesExclus,
}: {
  etape: "exercice" | "finances";
  exercicesExclus: number[];
}) {
  const navigate = useNavigate();
  const ouvrir = useOpenDeclaration();
  const [erreur, setErreur] = useState<string | null>(null);
  const departAutorise = useRef(false);
  const form = useForm<OuvrirDeclarationForm>({
    resolver: zodResolver(ouvrirDeclarationSchema),
    defaultValues: {
      report_type: "RAPPORT_ESG",
      fiscal_year: EXERCICES.find((a) => !exercicesExclus.includes(a)) ?? ANNEE_COURANTE - 1,
    },
  });
  const devise = form.watch("currency");
  useConfirmationAbandon(
    (prochaine) =>
      !departAutorise.current &&
      form.formState.isDirty &&
      !prochaine.pathname.startsWith("/company/declarations/nouvelle"),
  );

  async function suivant() {
    if (await form.trigger([...CHAMPS.exercice])) navigate("/company/declarations/nouvelle/finances");
  }

  function creer(valeurs: OuvrirDeclarationForm) {
    // Entrée dans un champ de l'étape 1 : on avance, on ne crée rien.
    if (etape !== "finances") {
      void suivant();
      return;
    }
    setErreur(null);
    ouvrir.mutate(corpsOuverture(valeurs), {
      onSuccess: (brouillon) => {
        departAutorise.current = true;
        const titre = titreDeclaration({
          type: brouillon.report_type,
          fiscal_year: brouillon.fiscal_year,
          version: brouillon.version,
        });
        navigate(`/company/declarations/${creerSlug(titre, brouillon.id)}/brouillon/document`);
      },
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "La déclaration n’a pas été ouverte."),
    });
  }

  // …champ montant() : copié de NewDeclarationDialog.tsx.

  return (
    <Card>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(creer)} className="space-y-5" noValidate>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
            {etape === "exercice" ? (
              <>
                {/* FormField fiscal_year et report_type : copiés de NewDeclarationDialog.tsx
                    (même libellés « Exercice fiscal », « Type de rapport »). */}
                <div className="flex justify-end border-t pt-4">
                  <Button type="button" onClick={suivant}>
                    Suivant
                  </Button>
                </div>
              </>
            ) : (
              <>
                {/* FormField currency : comme dans NewDeclarationDialog.tsx, avec en premier
                    <option value="">Aucune donnée financière</option> et
                    onChange={(e) => field.onChange(e.target.value || undefined)}. */}
                {devise ? (
                  <>
                    {/* FormField revenue et enterprise_value (+ leur aide) : copiés de
                        NewDeclarationDialog.tsx. */}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Facultatif : le chiffre d’affaires et la valeur d’entreprise servent au calcul
                    PCAF une fois le rapport validé. Choisissez une devise pour les renseigner.
                  </p>
                )}
                <div className="flex justify-between gap-2 border-t pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate("/company/declarations/nouvelle/exercice")}
                  >
                    Précédent
                  </Button>
                  <Button type="submit" disabled={ouvrir.isPending}>
                    {ouvrir.isPending ? "Création…" : "Créer le brouillon"}
                  </Button>
                </div>
              </>
            )}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
```

The three `{/* … copiés de NewDeclarationDialog.tsx */}` blocks are verbatim moves of the `<FormField>` elements of that file (lines with `name="fiscal_year"`, `"report_type"`, `"currency"`, `"revenue"`, `"enterprise_value"`), with the single `currency` change described inline. Moving them is the instruction; do not leave the comments in the final code. `libelleTypeRapport`, `TYPES_RAPPORT`, `DEVISES`, `Input`, `Select`, `FormField…` are used by those blocks.

Important: the `Formulaire` component must not unmount between `exercice` and `finances` — it does not, because both URLs render the same route element and React keeps the instance (form values survive "Précédent", which the test checks).

`frontend/src/features/company/wizard/DocumentStep.tsx` — move `JoindreFichier` from `session/DraftPanel.tsx` verbatim, plus the analysis / failure messages:

```tsx
import { Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import type { RapportESGDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { etatBrouillon } from "../session/etat";
// + imports used by JoindreFichier (FileUp, useId, useState, SyntheticEvent, ApiError, FileDrop,
//   Label, useAttachDraftFile, fichierBrouillonSchema)

/** Étape 3 (spec §3.1) : joindre le PDF ; son analyse tourne en arrière-plan — on peut quitter
 * la page et revenir, la phase reste visible partout (tableau de bord, liste, en-tête). */
export function DocumentStep({ rapport }: { rapport: RapportESGDetail }) {
  const etat = etatBrouillon(rapport);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Document</CardTitle>
        <CardDescription>
          Joignez le PDF du rapport : sa lecture indique quels indicateurs attendus y figurent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {etat === "ANALYSE" ? (
          <div className="space-y-2" aria-live="polite">
            <p className="flex items-center gap-2 text-sm text-foreground">
              <Loader2 className="size-4 motion-safe:animate-spin" aria-hidden="true" />
              Lecture de « {rapport.original_filename ?? "votre fichier"} » en cours — vous pouvez
              quitter cette page, l’analyse continue.
            </p>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
              <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-pulse" />
            </div>
          </div>
        ) : null}
        {etat === "ECHEC" && rapport.extraction_error ? (
          <Alert variant="destructive">
            <AlertTitle>
              {rapport.extraction_error === "quota_llm_epuise"
                ? "Analyse momentanément impossible"
                : "Le fichier n’a pas pu être lu"}
            </AlertTitle>
            <AlertDescription>
              {libelleCauseExtraction(rapport.extraction_error)}. Joignez de nouveau le fichier.
            </AlertDescription>
          </Alert>
        ) : null}
        {etat !== "ANALYSE" ? (
          <JoindreFichier
            rapportId={rapport.id}
            libelle={etat === "SANS_FICHIER" ? "Rapport (PDF, 50 Mo au plus)" : "Remplacer le fichier"}
            bouton={etat === "SANS_FICHIER" ? "Joindre et analyser" : "Analyser ce fichier"}
          />
        ) : null}
        {etat === "PRET" ? (
          <div className="flex justify-end border-t pt-4">
            <Button asChild>
              <Link to="../verification" relative="path">
                Suivant
              </Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

// function JoindreFichier(…) — déplacée telle quelle depuis session/DraftPanel.tsx.
```

`frontend/src/features/company/wizard/VerificationStep.tsx` — confirmation + receipt, built from `session/SubmitDialog.tsx` (its `Ligne` helper and both `<dl>` blocks moved verbatim):

```tsx
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import type { RapportESGDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { ApiError } from "@/shared/api/errors";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useReportChecklist, useSubmitDraft } from "../api";
import { CompletenessChecklist } from "../session/CompletenessChecklist";
import { dateHeure, totaux } from "../session/etat";

// function Ligne(…) — déplacée telle quelle depuis session/SubmitDialog.tsx.

/** Étape 4 (spec §3.1) : liste de complétude (des comptes, jamais de valeurs), récapitulatif,
 * confirmation explicite, puis reçu affiché sur place. */
export function VerificationStep({ rapport }: { rapport: RapportESGDetail }) {
  const liste = useReportChecklist(rapport.id, rapport.extraction_finished_at);
  const soumettre = useSubmitDraft(rapport.id);
  const [confirme, setConfirme] = useState(false);
  const recu = soumettre.data;

  if (recu?.submitted_at) {
    return (
      <Card role="region" aria-label="Reçu de soumission">
        <CardHeader>
          <CardTitle>Reçu de soumission</CardTitle>
          <CardDescription>
            Votre rapport est transmis et verrouillé. Conservez ce reçu : l’empreinte identifie
            exactement le fichier soumis.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* <dl> du reçu : déplacé tel quel depuis SubmitDialog.tsx */}
          <Button asChild>
            <Link to="../.." relative="path">
              Terminer
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Déclaration déjà soumise, sans reçu à montrer (adresse retapée plus tard) : sa synthèse.
  if (rapport.submitted_at !== null) return <Navigate to="../.." relative="path" replace />;

  const groupes = liste.data ?? [];
  const total = totaux(groupes);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Vérification</CardTitle>
        <CardDescription>
          Une fois soumis, le rapport est verrouillé pendant l’examen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {liste.isPending ? <Skeleton className="h-40 w-full" /> : <CompletenessChecklist groupes={groupes} />}
        {/* <dl> de confirmation (Rapport, Fichier, Empreinte SHA-256, Complétude) : déplacé tel
            quel depuis SubmitDialog.tsx, avec `total` ci-dessus. */}
        {soumettre.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              {soumettre.error instanceof ApiError ? soumettre.error.message : "La soumission n’a pas abouti."}
            </AlertDescription>
          </Alert>
        ) : null}
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4"
            checked={confirme}
            onChange={(e) => setConfirme(e.target.checked)}
          />
          Je confirme ces informations : la déclaration sera verrouillée pendant l’examen.
        </label>
        <div className="flex justify-between gap-2 border-t pt-4">
          <Button asChild variant="outline">
            <Link to="../document" relative="path">
              Précédent
            </Link>
          </Button>
          <Button onClick={() => soumettre.mutate()} disabled={!confirme || soumettre.isPending}>
            {soumettre.isPending ? "Soumission…" : "Soumettre la déclaration"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/company/wizard/DraftStepPage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router-dom";
import { idDepuisSlug } from "@/shared/format/slug";
import { rapportQueryOptions } from "../api";
import { etatBrouillon } from "../session/etat";
import { DocumentStep } from "./DocumentStep";
import { VerificationStep } from "./VerificationStep";

/** Étapes 3–4, sur le brouillon (spec §3.1). La vérification n'est ouverte qu'à un fichier
 * analysé sans erreur ; une déclaration soumise sans reçu à afficher retourne à sa synthèse —
 * mais l'étape reste montée juste après la soumission, pour montrer le reçu. */
export function DraftStepPage() {
  const { rapportId: segment = "", etape } = useParams();
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  if (!rapport) return null;
  if (etape === "verification") {
    if (rapport.submitted_at === null && etatBrouillon(rapport) !== "PRET") {
      return <Navigate to="../document" relative="path" replace />;
    }
    return <VerificationStep rapport={rapport} />;
  }
  if (rapport.submitted_at !== null) return <Navigate to="../.." relative="path" replace />;
  return <DocumentStep rapport={rapport} />;
}
```

Note the receipt: after `submit`, the report query is invalidated and becomes `AWAITING_ASSIGNMENT`; `VerificationStep` keeps showing the receipt because its mutation state (`soumettre.data`) lives in the still-mounted component and the `verification` branch no longer redirects once `submitted_at` is set.

- [ ] **Step 5: Layout, overview, routes, list and dashboard**

1. `DeclarationLayout.tsx`: replace the whole `rapport.status === "DRAFT" ? <Outlet /> : <MasterDetailLayout …>` expression with a single `MasterDetailLayout` whose rail depends on the status:

```tsx
      <MasterDetailLayout
        railLabel={brouillon ? undefined : "Sections de la déclaration"}
        detailActif={!brouillon && pilier !== undefined}
        rail={
          brouillon ? (
            <WizardStepper etapes={ETAPES_DECLARATION} courante={etape ?? "document"} />
          ) : (
            <RailDeclaration rapport={rapport} />
          )
        }
      >
        <Outlet />
      </MasterDetailLayout>
```

   with `const brouillon = rapport.status === "DRAFT";` and `etape` read from `useParams()` next to `pilier` (import `WizardStepper`, `ETAPES_DECLARATION`). Keep `PhaseProgress` above for drafts too. **Why one wrapper:** when the draft is submitted, the report query flips to `AWAITING_ASSIGNMENT`. If the layout switched between two different wrapper elements, React would unmount the `<Outlet />` subtree and the receipt held in `VerificationStep`'s mutation state would vanish. With the same element type the step stays mounted and keeps showing the receipt; the wizard test "soumission puis reçu" guards this.

2. `OverviewPage.tsx`: remove the `DraftPanel`, `SubmitDialog`, `useState`, `useReportChecklist` code and imports; at the top, after `if (!rapport) return null;`, add
   `if (rapport.status === "DRAFT") return <Navigate to={`brouillon/${etapeReprise(rapport)}`} replace />;`
   (import `Navigate`, `etapeReprise`). Also drop the `etat ? null : …` guard around the pillar cards (drafts never reach this point now).

3. `routes.tsx`: under `declarations` children, before `":rapportId"`, add
   `{ path: "nouvelle", element: <Navigate to="exercice" replace /> },`
   `{ path: "nouvelle/:etape", element: <NewDeclarationWizard />, handle: { fil: "Nouvelle déclaration" } satisfies HandleRoute },`
   and under `":rapportId"` children add
   `{ path: "brouillon/:etape", element: <DraftStepPage />, handle: { fil: (p) => (p.etape === "verification" ? "Vérification" : "Document") } satisfies HandleRoute },`

4. `CompanyDeclarationsPage.tsx`: delete the `creation` state and `<NewDeclarationDialog …/>`; the header action becomes

```tsx
        sessionBloquante !== undefined || !rapports ? (
          <Button disabled aria-describedby={sessionBloquante ? "raison-blocage" : undefined}>
            <Plus />
            Nouvelle déclaration
          </Button>
        ) : (
          <Button asChild>
            <Link to="nouvelle/exercice">
              <Plus />
              Nouvelle déclaration
            </Link>
          </Button>
        )
```

   In the "En cours" cards replace `<SessionStepper rapport={rapport} />` with
   `<PhaseProgress etapes={PHASES_DECLARATION} courante={phaseDeclaration(rapport).index} />` and make the card link point to the draft step for drafts:
   `rapport.status === "DRAFT" ? `${base}/brouillon/${etapeReprise(rapport)}` : base` where `base` is the existing slug URL.

5. `CompanyDashboardPage.tsx` (`SessionActive`, near line 150): the action link becomes "Reprendre" to the same draft-step URL when the active report is a draft; otherwise keep "Voir la déclaration" to the overview. Replace its status badge with `StatutDeclaration`.

- [ ] **Step 6: Delete the replaced components and update tests**

`git rm frontend/src/features/company/session/NewDeclarationDialog.tsx frontend/src/features/company/session/DraftPanel.tsx frontend/src/features/company/session/SubmitDialog.tsx frontend/src/features/company/session/SessionStepper.tsx`

Update tests:
- `declaration/Declaration.test.tsx`: the draft tests ("affiche la liste de complétude… puis soumet et donne le reçu", attaching a file, etc.) move to `wizard/Wizard.test.tsx` — they are covered by the new tests above; delete the old draft cases that duplicate them and keep only assertions that are not covered (e.g. lock banner text after submission, extraction failure alert on `EXTRACTION_FAILED`).
- `components/CompanyDeclarationsPage.test.tsx`: the "Nouvelle déclaration" button is now a link to `nouvelle/exercice` (assert `href`), not a dialog; dialog-based tests move to `Wizard.test.tsx` (already covered). Stepper assertions use the `Progression` list as in Task 8 Step 2.
- `components/CompanyDashboardPage.test.tsx`: for a draft session, assert the "Reprendre" link points to `…/brouillon/document` (no file) or `…/brouillon/verification` (ready).
- `session/presentation.test.ts`: unchanged unless it imports deleted symbols.

- [ ] **Step 7: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.
Run: `grep -rn "NewDeclarationDialog\|DraftPanel\|SubmitDialog\|SessionStepper" src` → no results.

```bash
git add -A frontend/src/features/company
git commit -m "feat(company): assistant de déclaration en quatre étapes, reprise du brouillon

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Correction sheet

**Files:**
- Create: `frontend/src/features/company/declaration/CorrectionSheet.tsx`
- Delete: `frontend/src/features/company/declaration/FormulaireCorrection.tsx`
- Modify: `frontend/src/features/company/declaration/OverviewPage.tsx`, `DeclarationLayout.tsx`, `routes.tsx`
- Test: `frontend/src/features/company/declaration/Correction.test.tsx`

**Interfaces:**
- Consumes: `RouteSheet` (Task 1), `useSubmitCorrection`, `correctionSchema` (existing), `presentationSession` (existing `session/presentation.ts`).
- Produces: route `:rapportId/correction` (child of the overview route); header action "Corriger" when `REVISION_REQUESTED`.

- [ ] **Step 1: Write the failing test**

`frontend/src/features/company/declaration/Correction.test.tsx`:

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCompany } from "../test/renderCompany";

const ID = "99999999-9999-9999-9999-999999999999";
const fetchMock = vi.fn<typeof fetch>();
const PDF = new File(["%PDF-1.7"], "corrige.pdf", { type: "application/pdf" });

function rapport() {
  return {
    id: ID, company_id: ID, type: "RAPPORT_ESG", channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z", submitted_at: "2026-09-02T08:00:00Z",
    status: "REVISION_REQUESTED", source_file: "x.pdf", original_filename: "x.pdf",
    fiscal_year: 2025, extraction_finished_at: "2026-09-01T09:00:00Z", extraction_error: null,
    extraction_attempts: 1, version: 1, previous_report_id: null, checksum_sha256: null,
    metrics: [], carbon_data: [], declared_global_score: null, declared_global_score_proof: null,
    official_score: null, synthesis_available: false,
    coverage: { total_targets: 0, found: 0, missing_codes: [] },
  };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    if (chemin.includes("/notifications")) return Response.json({ items: [], total: 0, page: 1, page_size: 1 });
    if (init?.method === "POST" && chemin.endsWith("/corrections")) {
      return Response.json({ ...rapport(), id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", status: "DRAFT" }, { status: 201 });
    }
    return Response.json(rapport());
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("Correction demandée — tiroir en deux étapes", () => {
  it("depuis l’en-tête : demande, puis exercice et PDF ; envoi puis retour à la synthèse", async () => {
    const user = userEvent.setup();
    const { router } = renderCompany(`/company/declarations/${ID}`);
    await user.click(await screen.findByRole("link", { name: "Corriger" }));

    const tiroir = await screen.findByRole("dialog", { name: "Correction demandée" });
    expect(tiroir).toHaveTextContent("L’auditeur a demandé des précisions");
    expect(within(tiroir).queryByLabelText("Fichier PDF corrigé")).not.toBeInTheDocument();
    await user.click(within(tiroir).getByRole("button", { name: "Continuer" }));

    expect(within(tiroir).getByLabelText("Exercice")).toHaveValue(2025);
    await user.upload(within(tiroir).getByLabelText("Fichier PDF corrigé"), PDF);
    await user.click(within(tiroir).getByRole("button", { name: "Envoyer la correction" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/company/declarations/${ID}`));
    expect(await screen.findByText("Nouvelle version déposée")).toBeInTheDocument();
  });

  it("aucun formulaire de correction dans la synthèse elle-même", async () => {
    renderCompany(`/company/declarations/${ID}`);
    await screen.findByRole("link", { name: "Corriger" });
    expect(screen.queryByLabelText("Fichier PDF corrigé")).not.toBeInTheDocument();
  });
});
```

(If `FileDrop` exposes its input under a different accessible name than its `FormLabel`, use the same query the old `CompanyReportDetailPage` correction test used.)

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/declaration/Correction.test.tsx`
Expected: FAIL — no "Corriger" link.

- [ ] **Step 3: Implement `CorrectionSheet`**

`frontend/src/features/company/declaration/CorrectionSheet.tsx`: start from `FormulaireCorrection.tsx` (Task 8) and restructure:

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { FileDrop } from "@/shared/ui/file-drop";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { RouteSheet } from "@/shared/ui/route-sheet";
import { SheetBody, SheetFooter } from "@/shared/ui/sheet";
import { rapportQueryOptions, useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";
import { presentationSession } from "../session/presentation";

const ANNEE_COURANTE = new Date().getFullYear();

/** Correction demandée (spec §3.2) : 1) ce qui est demandé, 2) exercice + PDF corrigé. Une
 * nouvelle version liée ; l'original reste conservé tel quel. */
export function CorrectionSheet() {
  const { rapportId: segment = "" } = useParams();
  const navigate = useNavigate();
  const retour = `/company/declarations/${segment}`;
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  const [etape, setEtape] = useState<1 | 2>(1);
  const correction = useSubmitCorrection(rapport?.id ?? "");
  const [erreur, setErreur] = useState<string | null>(null);
  const form = useForm<CorrectionForm>({
    resolver: zodResolver(correctionSchema),
    defaultValues: { annee_reporting: rapport?.fiscal_year ?? ANNEE_COURANTE },
  });

  if (!rapport) return null;
  if (rapport.status !== "REVISION_REQUESTED") return <Navigate to={retour} replace />;

  function envoyer(valeurs: CorrectionForm) {
    setErreur(null);
    correction.mutate(valeurs, {
      onSuccess: () => navigate(retour, { state: { correctionEnvoyee: true } }),
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "Une erreur inattendue est survenue."),
    });
  }

  return (
    <RouteSheet
      retour={retour}
      titre="Correction demandée"
      description={`Étape ${etape} sur 2`}
      taille="large"
    >
      {etape === 1 ? (
        <>
          <SheetBody>
            <p className="text-sm text-foreground">
              {presentationSession("REVISION_REQUESTED").description}
            </p>
            <p className="text-sm text-muted-foreground">
              Déposez une nouvelle version du rapport. L’original reste conservé tel quel.
            </p>
          </SheetBody>
          <SheetFooter>
            <Button onClick={() => setEtape(2)}>Continuer</Button>
          </SheetFooter>
        </>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(envoyer)} className="flex min-h-0 flex-1 flex-col" noValidate>
            <SheetBody>
              {erreur ? (
                <Alert variant="destructive">
                  <AlertTitle>Dépôt impossible</AlertTitle>
                  <AlertDescription>{erreur}</AlertDescription>
                </Alert>
              ) : null}
              {/* FormField annee_reporting et fichier : déplacés tels quels depuis
                  FormulaireCorrection.tsx. */}
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="outline" onClick={() => setEtape(1)}>
                Précédent
              </Button>
              <Button type="submit" disabled={correction.isPending}>
                {correction.isPending ? "Envoi en cours…" : "Envoyer la correction"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      )}
    </RouteSheet>
  );
}
```

- [ ] **Step 4: Wire it up**

1. `routes.tsx`: the overview route children become `[{ index: true }, { path: "correction", element: <CorrectionSheet /> }]`.
2. `OverviewPage.tsx`: remove `FormulaireCorrection`; show the success alert when `useLocation().state?.correctionEnvoyee` is true:

```tsx
      {(location.state as { correctionEnvoyee?: boolean } | null)?.correctionEnvoyee ? (
        <Alert role="status" className="border-primary/20 bg-secondary/60">
          <AlertTitle>Nouvelle version déposée</AlertTitle>
          <AlertDescription>
            Votre correction a été envoyée et sera traitée comme un nouveau rapport.
          </AlertDescription>
        </Alert>
      ) : null}
```

3. `DeclarationLayout.tsx` header `action`: add, when `rapport.status === "REVISION_REQUESTED"`,

```tsx
              <Button asChild size="sm">
                <Link to={`/company/declarations/${segment}/correction`}>Corriger</Link>
              </Button>
```

4. `git rm frontend/src/features/company/declaration/FormulaireCorrection.tsx`.

- [ ] **Step 5: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.

```bash
git add -A frontend/src/features/company
git commit -m "feat(company): correction demandée dans un tiroir routé en deux étapes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Profile edit sheet

**Files:**
- Create: `frontend/src/features/company/components/ProfileEditSheet.tsx`
- Modify: `frontend/src/features/company/components/ProfilePage.tsx`, `frontend/src/features/company/routes.tsx`
- Test: update `frontend/src/features/company/components/ProfilePage.test.tsx`

**Interfaces:**
- Consumes: `RouteSheet` (Task 1), `useMyCompanyProfile`, `useUpdateMyCompanyProfile`, `modifierProfilEntrepriseSchema` (existing).
- Produces: route `/company/profile/fiche-publique`.

- [ ] **Step 1: Update the tests first**

In `ProfilePage.test.tsx`, switch rendering to `renderCompany("/company/profile")` (Task 8 helper; add the notifications answer to its fetch mock), and change the edit tests to:

```tsx
  it("la fiche se lit en résumé ; « Modifier » ouvre le tiroir routé", async () => {
    const user = userEvent.setup();
    const { router } = renderCompany("/company/profile");
    const fiche = await screen.findByRole("region", { name: "Fiche entreprise" });
    expect(within(fiche).queryByRole("textbox")).not.toBeInTheDocument();
    await user.click(within(fiche).getByRole("link", { name: "Modifier" }));
    expect(router.state.location.pathname).toBe("/company/profile/fiche-publique");
    expect(await screen.findByRole("dialog", { name: "Modifier la fiche publique" })).toBeInTheDocument();
  });

  it("le montant minimum n’apparaît qu’une fois l’option cochée", async () => {
    const user = userEvent.setup();
    renderCompany("/company/profile/fiche-publique");
    const tiroir = await screen.findByRole("dialog", { name: "Modifier la fiche publique" });
    expect(within(tiroir).queryByLabelText(/Montant minimum/)).not.toBeInTheDocument();
    await user.click(within(tiroir).getByLabelText(/montant minimum/i, { selector: "input[type=checkbox]" }));
    expect(within(tiroir).getByLabelText(/Montant minimum/)).toBeInTheDocument();
  });
```

Keep the existing save-path assertions (PATCH body with `null, null` when the option is off) but run them inside the sheet (`within(tiroir)`), and add: after a successful save the URL is back to `/company/profile`. Match the label texts to the current form's `FormLabel`s (read them in `ProfilePage.tsx` lines ~150–221 and use them verbatim).

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/components/ProfilePage.test.tsx`
Expected: FAIL — no "Modifier" link.

- [ ] **Step 3: Implement**

1. Create `ProfileEditSheet.tsx`: move from `ProfilePage.tsx` the form part of the "Fiche entreprise" component — the `useForm` setup, `imposeMinimum` watch, `onSubmit`, the server-error alert and the `<Form>…</Form>` block with its five `FormField`s — into:

```tsx
export function ProfileEditSheet() {
  const { data: entreprise } = useMyCompanyProfile();
  const navigate = useNavigate();
  if (!entreprise) return null;
  return (
    <RouteSheet retour="/company/profile" titre="Modifier la fiche publique" taille="large">
      <FormulaireFiche entreprise={entreprise} onEnregistre={() => navigate("/company/profile")} />
    </RouteSheet>
  );
}
```

   where `FormulaireFiche` is the moved code, with `onSubmit`'s `mutate` options gaining `onSuccess: onEnregistre`, the fields wrapped in `<SheetBody>` and the submit button moved into `<SheetFooter>` together with an "Annuler" `Button asChild` + `<Link to="/company/profile">`. The `<form>` gets `className="flex min-h-0 flex-1 flex-col"`.

2. In `ProfilePage.tsx`, the "Fiche entreprise" card keeps its header, badge and identity block, and replaces the form with a read-only `SheetFields`-style summary (reuse `SheetFields` from `@/shared/ui/sheet`):

```tsx
        <SheetFields
          champs={[
            { libelle: "Description", valeur: entreprise.description },
            { libelle: "Site officiel", valeur: entreprise.website },
            {
              libelle: "Montant minimum",
              valeur:
                entreprise.minimum_investment_amount != null
                  ? `${entreprise.minimum_investment_amount.toLocaleString("fr-FR")} ${entreprise.minimum_investment_currency ?? ""}`
                  : "Aucun",
            },
          ]}
        />
```

   plus a `CardAction` with `<Button asChild variant="outline" size="sm"><Link to="fiche-publique">Modifier</Link></Button>`, and the page renders `<Outlet />` at the end.

3. `routes.tsx`: the `profile` route gets `children: [{ path: "fiche-publique", element: <ProfileEditSheet /> }]`.

- [ ] **Step 4: Run, full checks, commit**

Run: `npx vitest run src/features/company` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.

```bash
git add -A frontend/src/features/company
git commit -m "feat(company): fiche publique modifiée dans un tiroir routé

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Company registration wizard

**Files:**
- Modify: `frontend/src/features/company/components/CompanyRegistrationPage.tsx`
- Test: update `frontend/src/features/company/components/CompanyRegistrationPage.test.tsx`

**Interfaces:**
- Consumes: `WizardStepper` (Task 3), existing `companyRegistrationFormSchema`, `useRegisterCompany`, `EmailVerificationStep`, `RegistrationConfirmation`.
- Produces: no new exports. Steps held in `useState` (spec §3.3).

- [ ] **Step 1: Update tests first**

In `CompanyRegistrationPage.test.tsx`, rewrite the shared fill helper to go through the steps, and add the Review Focus test:

```tsx
async function remplirEtape1(user: UserEvent) {
  await user.type(screen.getByLabelText("Nom de l’entreprise"), "Minière du Nord");
  // secteur, pays, identifiant fiscal : mêmes saisies qu'avant (garder le code existant du helper)
  await user.click(screen.getByRole("button", { name: "Suivant" }));
}

async function remplirEtape2(user: UserEvent) {
  await user.type(screen.getByLabelText("Nom & Prénom du responsable"), "Aïcha Ba");
  await user.type(screen.getByLabelText("E-mail professionnel"), "aicha@miniere.mr");
  await user.upload(screen.getByLabelText("Lettre de mandat signée (PDF)"), MANDAT);
  await user.click(screen.getByRole("button", { name: "Suivant" }));
}

it("trois étapes ; « Suivant » ne vérifie que l’étape affichée", async () => {
  const user = userEvent.setup();
  renderPage();
  expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent("Étape 1 sur 3");
  await user.click(screen.getByRole("button", { name: "Suivant" }));
  expect(await screen.findByText("Le nom de l’entreprise est requis.")).toBeInTheDocument();
  expect(screen.queryByText("Votre nom est requis.")).not.toBeInTheDocument();
});

it("erreur d’adresse trouvée à l’envoi : retour à l’étape Contact avec le message (Review Focus 4)", async () => {
  const user = userEvent.setup();
  renderPage();
  await remplirEtape1(user);
  await remplirEtape2(user);
  await user.type(screen.getByLabelText("Site web officiel"), "https://www.autre-groupe.mr");
  await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
  expect(await screen.findByLabelText("E-mail professionnel")).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent("Étape 2 sur 3");
  // Même message que l'ancien test « exige une adresse sur le domaine du site web » : reprendre
  // son assertion telle quelle ici.
});
```

Existing tests change as follows: every test that typed all fields on one page now calls `remplirEtape1`, `remplirEtape2`, then acts on step 3; "formulaire épuré : ni ISIN ni LEI visibles, mais repliés en facultatif" becomes "ISIN, LEI et site web sur l’étape 3, marqués facultatifs" (assert they are absent on step 1 and present on step 3); the existing "exige une adresse sur le domaine du site web" test is replaced by the Review Focus test above; country / tax-ID tests stay on step 1.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/features/company/components/CompanyRegistrationPage.test.tsx`
Expected: FAIL — no "Suivant" button.

- [ ] **Step 3: Implement**

In `CompanyRegistrationPage.tsx`:

1. Add the step model above the component:

```tsx
const ETAPES_INSCRIPTION = [
  { id: "entreprise", titre: "Entreprise" },
  { id: "contact", titre: "Contact & mandat" },
  { id: "identifiants", titre: "Identifiants (facultatifs)" },
] as const;
type EtapeInscription = (typeof ETAPES_INSCRIPTION)[number]["id"];

const CHAMPS_INSCRIPTION = {
  entreprise: ["company_name", "sector", "country", "tax_id"],
  contact: ["contact_name", "contact_email", "mandate_letter"],
  identifiants: ["lei", "isin", "website"],
} as const satisfies Record<EtapeInscription, readonly (keyof CompanyRegistrationForm)[]>;

/** Étape qui porte le premier champ en erreur — une règle croisée (adresse / site) n'est connue
 * qu'à l'envoi, l'utilisateur doit être ramené là où il peut corriger. */
function etapeDeLErreur(erreurs: Partial<Record<keyof CompanyRegistrationForm, unknown>>): EtapeInscription | null {
  for (const { id } of ETAPES_INSCRIPTION) {
    if (CHAMPS_INSCRIPTION[id].some((champ) => erreurs[champ])) return id;
  }
  return null;
}
```

2. In the component, add `const [etape, setEtape] = useState<EtapeInscription>("entreprise");`, remove `complementsOuverts` and the `Collapsible` (its three fields move to step 3 unchanged, each label suffixed by nothing — the step title already says "facultatifs").

3. Replace `form.handleSubmit(onSubmit)` with `form.handleSubmit(onSubmit, (erreurs) => { const cible = etapeDeLErreur(erreurs); if (cible) setEtape(cible); })`.

4. Render: `<WizardStepper etapes={ETAPES_INSCRIPTION} courante={etape} />` above the form, then only the current step's fields:
   - `entreprise`: company_name, sector, country, tax_id **and the honeypot `company_fax` field** (unchanged, still hidden from assistive tech);
   - `contact`: contact_name, contact_email, mandate_letter;
   - `identifiants`: lei, isin, website.
   Footer: "Précédent" (`type="button"`, hidden on step 1) and either "Suivant" (`type="button"`, `onClick={async () => { if (await form.trigger([...CHAMPS_INSCRIPTION[etape]])) setEtape(suivante) }}`) or, on step 3, the existing submit button "Envoyer la demande".
   Move each `FormField` block verbatim into its step; do not change labels, validation or the submit payload.

5. `EmailVerificationStep` and `RegistrationConfirmation` remain the post-submit screens as before.

- [ ] **Step 4: Run, full checks, commit**

Run: `npx vitest run src/features/company/components/CompanyRegistrationPage.test.tsx src/features/registration` → PASS.
Run: `npx biome check src && npx tsc -b && npx vitest run && npm run build` → green.

```bash
git add frontend/src/features/company/components/CompanyRegistrationPage.tsx frontend/src/features/company/components/CompanyRegistrationPage.test.tsx
git commit -m "feat(registration): inscription entreprise en assistant de trois étapes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Documentation and task tracking

**Files:**
- Modify: `FRONTEND-ARCHITECTURE.md`
- Modify: `docs/TASKS.md`

- [ ] **Step 1: `FRONTEND-ARCHITECTURE.md`**

Add a status paragraph after the existing dated status paragraphs (top of file):

```markdown
**Navigation hiérarchique au 2026-10-14 (espace Entreprise, pilote).** Les niveaux d'un espace
sont des routes imbriquées qui déclarent leur libellé de fil d'Ariane (`handle.fil`,
`shared/layout/handle.ts`) ; `AppShell` affiche le fil (`shared/layout/Breadcrumbs`). Les tiroirs
sont des routes (`shared/ui/route-sheet`), les saisies en plusieurs temps des assistants
(`shared/ui/wizard`). Espace Entreprise : Tableau de bord → Mes déclarations → Déclaration →
Pilier → Famille → Indicateur (tiroir). Les cinq autres espaces adopteront ce socle dans des specs
séparées. Spec : `docs/superpowers/specs/2026-10-14-frontend-hierarchical-navigation-design.md`.
```

Add a subsection `### 5.4 Navigation et formulaires` under §5 with the conventions of spec §3.4 and §2 (one bullet each):

```markdown
### 5.4 Navigation et formulaires

- Un niveau de la hiérarchie = une route imbriquée avec `handle.fil` ; jamais deux niveaux empilés
  sur une même page.
- Un tiroir de détail ou de modification est une route enfant (`RouteSheet`) : lien profond,
  Échap et retour navigateur ramènent au parent, le focus revient à l'élément d'origine.
- Dialogue = confirmation ou au plus 3 champs ; modification plus longue d'un objet = tiroir
  (`taille="large"`) ; plusieurs étapes ou appel serveur entre deux étapes = assistant.
- Un champ dépendant reste masqué tant qu'il ne s'applique pas et n'est pas validé masqué.
- Une section repliée montre toujours un résumé (`DisclosureCard`).
- Statut d'objet : `StatusBadge` (libellé + icône + ton) ; progression : `PhaseProgress`.
- Données affichées depuis une valeur extraite : par une vue en liste blanche
  (`features/company/esg/vueMetrique.ts`), jamais le DTO généré directement.
```

In §7, append:

```markdown
> Espace Entreprise (2026-10-14) : aucun extrait textuel n'est affiché ; la preuve ouvre le PDF
> d'origine de l'entreprise à la page citée. Le retrait de `proof_text`, `raw_value`, `section` et
> `proof_boxes` du schéma de réponse Entreprise est une PR backend séparée (spec §4.2) ; ce
> paragraphe sera alors restreint à l'espace Auditeur.
```

- [ ] **Step 2: `docs/TASKS.md`**

Append a new phase at the end of the file:

```markdown
## Phase 6: Hierarchical navigation — foundation + Company pilot

Spec: `docs/superpowers/specs/2026-10-14-frontend-hierarchical-navigation-design.md`; plan:
`docs/superpowers/plans/2026-10-14-frontend-hierarchical-navigation.md`. Branch
`feat/refonte-navigation-entreprise`.

- [x] 6.1 Shared primitives: sheet widths, routed sheet, disclosure card, status badge, phase progress, wizard stepper and leave confirmation
- [x] 6.2 Breadcrumbs from route handles, master-detail layout, route error view
- [x] 6.3 Company: four-phase status model, query-key factory, list polling while analysing, refresh on new notifications
- [x] 6.4 Company: pillar → family taxonomy and display allowlist (`MetriqueVue`), leak tests
- [x] 6.5 Company: nested declaration routes — overview, pillar page, metric sheet
- [x] 6.6 Company: four-step declaration wizard (replaces the dialog and draft panels)
- [x] 6.7 Company: correction and public-profile edits as routed sheets
- [x] 6.8 Company registration as a three-step wizard
- [ ] 6.9 Backend: drop `proof_text`, `raw_value`, `section`, `proof_boxes` from the company report schema (separate PR, spec §4.2)
- [ ] 6.10 Other spaces (admin, audit, investor, researcher, institution): one spec each on this foundation
```

Only tick 6.1–6.8 if Tasks 1–13 are actually committed and green.

- [ ] **Step 3: Final verification and commit**

Run (from `frontend/`): `npx biome check src && npx tsc -b && npx vitest run && npm run build`
Expected: all green; note the known pre-existing flake (`InstitutionDashboardPage` in full runs on Linux) if it shows up — rerun that file alone to confirm.

Manual check (Definition of Done §12): `npm run dev`, log in as an enterprise demo account, walk Tableau de bord → Mes déclarations → a validated declaration → Environnement → Émissions GES → Scope 1 sheet → Esc; new declaration wizard; correction; profile edit — at 375 px, 768 px and 1280 px widths, keyboard only.

```bash
git add FRONTEND-ARCHITECTURE.md docs/TASKS.md
git commit -m "docs(interface): conventions de navigation hiérarchique et suivi de la phase 6

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
