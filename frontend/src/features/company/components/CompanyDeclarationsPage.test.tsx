import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { rapportListe } from "../session/fixtures";
import { CompanyDeclarationsPage } from "./CompanyDeclarationsPage";

const fetchMock = vi.fn<typeof fetch>();
const SHA = "f".repeat(64);

const RAPPORTS = [
  rapportListe("valide"),
  rapportListe("brouillon", {
    fiscal_year: 2025,
    status: "DRAFT",
    submitted_at: null,
    created_at: "2026-09-01T08:00:00Z",
    official_global_score: null,
    synthesis_available: false,
  }),
  // Version remplacée par une correction : historique, pas « en cours ».
  rapportListe("ancienne", {
    fiscal_year: 2023,
    status: "REVISION_REQUESTED",
    official_global_score: null,
    synthesis_available: false,
  }),
  rapportListe("correction", {
    fiscal_year: 2023,
    status: "IN_AUDIT",
    version: 2,
    previous_report_id: "ancienne",
    official_global_score: null,
    synthesis_available: false,
  }),
];

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
      <MemoryRouter initialEntries={["/company/declarations"]}>
        <Routes>
          <Route path="/company/declarations" element={<CompanyDeclarationsPage />} />
          <Route path="/company/declarations/:rapportId" element={<h1>Page du brouillon</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const PROFIL = {
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
  lei: null,
  ticker: null,
};

describe("Espace Entreprise — Mes déclarations", () => {
  it("une seule session en cours, l’historique avec score, empreinte et synthèse", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith("/company/profil") ? Response.json(PROFIL) : Response.json(RAPPORTS),
    );
    renderPage();

    // Données héritées : deux déclarations actives ; seule la plus récente est montrée.
    const enCours = await screen.findByRole("region", { name: "En cours" });
    expect(within(enCours).getByText("FY2025")).toBeInTheDocument();
    expect(within(enCours).queryByText("FY2023")).not.toBeInTheDocument();
    // Le badge de phase et l’étape « Déposé » de la progression.
    expect(within(enCours).getAllByText("Déposé")).toHaveLength(2);
    expect(within(enCours).getAllByRole("list", { name: "Progression" })).toHaveLength(1);

    // Une déclaration est active : pas d’ouverture d’une autre, et la raison est dite.
    expect(screen.getByRole("button", { name: "Nouvelle déclaration" })).toBeDisabled();
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent("Une seule déclaration à la fois.");
    expect(note).toHaveTextContent("Terminez la déclaration Rapport ESG — Exercice 2025");
    // Aucun code technique à l’écran : titres lisibles.
    expect(document.body.textContent).not.toMatch(/RAPPORT_ESG|· v1/);
    expect(within(enCours).getByText("Rapport ESG — Exercice 2025")).toBeInTheDocument();
    // La page commence par son propre titre, sans en-tête d’identité.
    expect(screen.getByRole("heading", { level: 1, name: "Mes déclarations" })).toBeInTheDocument();
    expect(screen.queryByText("Atlas Industries")).not.toBeInTheDocument();

    const historique = screen.getByRole("table");
    const lignes = within(historique).getAllByRole("row").slice(1);
    expect(lignes).toHaveLength(2);
    expect(lignes[0]).toHaveTextContent("FY2024");
    expect(lignes[0]).toHaveTextContent("Validé & publié");
    expect(lignes[0]).toHaveTextContent("74,5/100");

    // Le filtre « Statut » parle le même vocabulaire de phases que le badge.
    const filtreStatut = screen
      .getAllByRole("button", { name: "Statut" })
      .find((bouton) => bouton.hasAttribute("aria-haspopup"));
    await userEvent.setup().click(filtreStatut as HTMLElement);
    expect(screen.getByRole("checkbox", { name: "Validé & publié" })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Validé" })).not.toBeInTheDocument();
    await userEvent.setup().keyboard("{Escape}");

    // Couverture, empreinte et synthèse vivent dans le tiroir de la ligne.
    await userEvent
      .setup()
      .click(
        within(lignes[0] as HTMLElement).getByRole("button", { name: /Voir le détail de FY2024/ }),
      );
    const tiroir = await screen.findByRole("dialog");
    expect(tiroir).toHaveTextContent("Validé & publié");
    expect(tiroir).toHaveTextContent("Couverture88 %");
    // Empreinte tronquée : 8 premiers et 4 derniers caractères, complète au survol.
    expect(within(tiroir).getByTitle(SHA)).toHaveTextContent("ffffffff…ffff");
    expect(within(tiroir).getByRole("link", { name: "PDF" })).toHaveAttribute(
      "href",
      "/api/v1/company/rapports/valide/synthese/fichier",
    );
    expect(lignes[1]).toHaveTextContent("FY2023");
  });

  it("n’affiche jamais en cours un exercice déjà validé, et ne le propose plus", async () => {
    fetchMock.mockImplementation(async () =>
      Response.json([
        rapportListe("valide2025", { fiscal_year: 2025 }),
        // Donnée héritée d'avant la règle : un brouillon du même exercice.
        rapportListe("doublon", {
          fiscal_year: 2025,
          type: "RAPPORT_ANNUEL",
          status: "DRAFT",
          submitted_at: null,
          created_at: "2026-09-20T08:00:00Z",
          official_global_score: null,
        }),
      ]),
    );
    renderPage();

    const enCours = await screen.findByRole("region", { name: "En cours" });
    expect(within(enCours).queryByText("FY2025")).not.toBeInTheDocument();
    expect(within(enCours).getByText(/Aucune déclaration en cours/)).toBeInTheDocument();
    expect(screen.getAllByText("FY2025")).toHaveLength(1);
    // Le serveur compte encore ce brouillon hérité : ouverture bloquée, et dite.
    expect(screen.getByRole("button", { name: "Nouvelle déclaration" })).toBeDisabled();
  });

  it("« Nouvelle déclaration » est un lien vers l’assistant quand rien n’est en cours", async () => {
    fetchMock.mockImplementation(async () => Response.json([rapportListe("valide")]));
    renderPage();

    const lien = await screen.findByRole("link", { name: "Nouvelle déclaration" });
    expect(lien).toHaveAttribute("href", "/company/declarations/nouvelle/exercice");
  });

  it("le lien d’une déclaration en cours reprend le brouillon analysé à la vérification", async () => {
    fetchMock.mockImplementation(async () => Response.json(RAPPORTS));
    renderPage();

    const enCours = await screen.findByRole("region", { name: "En cours" });
    expect(within(enCours).getByRole("link", { name: "Ouvrir" })).toHaveAttribute(
      "href",
      "/company/declarations/rapport-esg-exercice-2025-brouillon/brouillon/verification",
    );
  });
});
