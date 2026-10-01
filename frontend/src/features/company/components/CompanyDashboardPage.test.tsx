import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { rapportListe } from "../session/fixtures";
import { CompanyDashboardPage } from "./CompanyDashboardPage";

const fetchMock = vi.fn<typeof fetch>();
const LEI = "5493001KJTIIGC8Y1R12";

function notification(id: string, type: string, resourceId: string | null) {
  return {
    id,
    type,
    message: "texte interne de la notification",
    read: false,
    sent_at: "2026-09-02T10:00:00Z",
    resource_id: resourceId,
  };
}

function profil(surcharges: Record<string, unknown> = {}) {
  return {
    id: "c1",
    name: "Atlas Industries",
    sector: "Industrie manufacturière",
    country: "MR",
    logo: null,
    description: null,
    website: null,
    active: true,
    status: "ACTIVE",
    minimum_investment_amount: null,
    minimum_investment_currency: null,
    published_at: null,
    isin: null,
    lei: LEI,
    ticker: null,
    ...surcharges,
  };
}

interface Donnees {
  rapports: unknown[];
  notifications?: unknown[];
  entreprise?: object;
  verification?: object;
  liste?: unknown[];
}

function servir({
  rapports,
  notifications = [],
  entreprise = profil(),
  verification,
  liste,
}: Donnees) {
  fetchMock.mockImplementation(async (url) => {
    const chemin = String(url);
    if (chemin.includes("/notifications")) {
      return Response.json({
        items: notifications,
        page: 1,
        page_size: 20,
        total: notifications.length,
        pages: 1,
      });
    }
    if (chemin.endsWith("/lei-verification")) {
      return Response.json(verification ?? { lei: LEI, result: "NOT_VERIFIABLE", detail: "" });
    }
    if (chemin.endsWith("/checklist")) return Response.json(liste ?? []);
    if (chemin.endsWith("/company/profil")) return Response.json(entreprise);
    return Response.json(rapports);
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CompanyDashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BROUILLON = rapportListe("brouillon", {
  fiscal_year: 2025,
  status: "DRAFT",
  submitted_at: null,
  created_at: "2026-09-01T08:00:00Z",
  official_global_score: null,
});

describe("Espace Entreprise — tableau de bord", () => {
  it("présente la session active avec l’identité de l’entreprise, et le dernier score officiel", async () => {
    servir({
      rapports: [rapportListe("valide"), BROUILLON],
      verification: { lei: LEI, result: "PASSED", detail: "Enregistrement ISSUED." },
      liste: [
        { group: "CARBON", expected: 5, found: 5 },
        { group: "SOCIAL", expected: 17, found: 13 },
      ],
    });
    renderPage();

    // En-tête : nom légal, puis secteur / LEI en badges ; « GLEIF Validé » sur contrôle réussi.
    expect(
      await screen.findByRole("heading", { level: 1, name: "Atlas Industries" }),
    ).toBeInTheDocument();
    const identite = screen.getByRole("list", { name: "Identité de l’entreprise" });
    expect(identite).toHaveTextContent("Secteur : Industrie manufacturière");
    expect(within(identite).getByText(LEI)).toBeInTheDocument();
    expect(await screen.findByText("GLEIF Validé")).toBeInTheDocument();

    const session = screen.getByRole("region", { name: "Session active" });
    expect(within(session).getByRole("heading", { name: "FY2025" })).toBeInTheDocument();
    expect(within(session).getByText("Brouillon ouvert le 01/09/2026")).toBeInTheDocument();
    expect(within(session).getByText("Statut : Brouillon")).toBeInTheDocument();
    expect(await within(session).findByText("18/22 indicateurs détectés")).toBeInTheDocument();
    expect(within(session).getByRole("link", { name: /Voir le suivi/ })).toHaveAttribute(
      "href",
      "/company/declarations",
    );

    const score = screen.getByRole("region", { name: "Dernier score officiel" });
    expect(within(score).getByRole("heading", { name: "FY2024" })).toBeInTheDocument();
    expect(score).toHaveTextContent("74,5/100");
    expect(score).toHaveTextContent("Taux de couverture : 88 %");
    // Deux cartes, pas de tableau ni de liste de fichiers.
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("ne garde dans l’activité que la transmission et la publication du score", async () => {
    servir({
      rapports: [rapportListe("valide"), rapportListe("autre", { fiscal_year: 2025 })],
      notifications: [
        notification("n1", "RAPPORT_VALIDE", "valide"),
        notification("n2", "RAPPORT_AFFECTE_ENTREPRISE", "autre"),
        notification("n3", "RAPPORT_AVIS_RENDU_ENTREPRISE", "autre"),
        notification("n4", "RAPPORT_ANALYSE_TERMINEE", "autre"),
        notification("n5", "RAPPORT_DEPOSE", "autre"),
      ],
    });
    renderPage();

    const fil = await screen.findByRole("list", { name: "Activité récente" });
    const lignes = within(fil).getAllByRole("listitem");
    expect(lignes).toHaveLength(2);
    expect(lignes[0]).toHaveTextContent("Score officiel publié pour l’exercice FY2024.");
    expect(lignes[1]).toHaveTextContent("Rapport FY2025 transmis avec succès pour audit.");
    expect(fil).not.toHaveTextContent("texte interne");
  });

  it.each([
    ["EXTRACTING", null],
    ["AWAITING_ASSIGNMENT", "2026-09-02T10:00:00Z"],
    ["IN_AUDIT", "2026-09-02T10:00:00Z"],
    ["PENDING_DECISION", "2026-09-02T10:00:00Z"],
  ])("regroupe %s sous « En cours d’examen », sans jargon interne", async (statut, soumis) => {
    servir({
      rapports: [
        rapportListe("session", {
          fiscal_year: 2025,
          status: statut,
          submitted_at: soumis,
          extraction_finished_at: null,
          official_global_score: null,
        }),
      ],
    });
    renderPage();

    const session = await screen.findByRole("region", { name: "Session active" });
    expect(within(session).getByText("Statut : En cours d'examen")).toBeInTheDocument();
    for (const jargon of [
      /Analyse du fichier/,
      /affecté à un auditeur/i,
      /décision finale/i,
      /extraction/i,
    ]) {
      expect(document.body.textContent).not.toMatch(jargon);
    }
  });

  it("sans LEI ni déclaration ni score : ni identifiant inventé, ni appel à la GLEIF", async () => {
    servir({ rapports: [], entreprise: profil({ lei: null }) });
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Atlas Industries" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/LEI :/)).not.toBeInTheDocument();
    const session = screen.getByRole("region", { name: "Session active" });
    expect(within(session).getByText("Aucune déclaration en cours.")).toBeInTheDocument();
    expect(screen.getByText("Aucun score officiel publié")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Activité récente" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/lei-verification"))).toBe(
      false,
    );
  });

  it("n’affiche jamais le score de l’exercice en cours, mais le dernier exercice antérieur validé", async () => {
    servir({
      rapports: [
        rapportListe("v2024", { fiscal_year: 2024, official_global_score: 61.2 }),
        rapportListe("v2026", { fiscal_year: 2026, official_global_score: 66.7 }),
        rapportListe("enCours", {
          fiscal_year: 2025,
          type: "RAPPORT_ANNUEL",
          status: "IN_AUDIT",
          created_at: "2026-09-20T08:00:00Z",
          official_global_score: null,
        }),
      ],
    });
    renderPage();

    const score = await screen.findByRole("region", { name: "Dernier score officiel" });
    expect(within(score).getByRole("heading", { name: "FY2024" })).toBeInTheDocument();
    expect(score).toHaveTextContent("61,2/100");
    expect(score).not.toHaveTextContent("66,7");
  });
});
