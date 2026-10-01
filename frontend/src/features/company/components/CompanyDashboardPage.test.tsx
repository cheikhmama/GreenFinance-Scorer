import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { rapportListe } from "../session/fixtures";
import { CompanyDashboardPage } from "./CompanyDashboardPage";

const fetchMock = vi.fn<typeof fetch>();

function notification(id: string, type: string, message: string) {
  return { id, type, message, read: false, sent_at: "2026-09-02T10:00:00Z", resource_id: null };
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

describe("Espace Entreprise — tableau de bord", () => {
  it("résume la session active, le dernier score officiel et les jalons sans étapes internes", async () => {
    fetchMock.mockImplementation(async (url) => {
      const chemin = String(url);
      if (chemin.includes("/notifications")) {
        return Response.json({
          items: [
            notification("n1", "RAPPORT_VALIDE", "RAPPORT_ESG (2024) : validé."),
            notification("n2", "RAPPORT_AFFECTE_ENTREPRISE", "Un auditeur examine votre rapport."),
            notification("n3", "RAPPORT_DEPOSE", "Votre rapport a été soumis."),
          ],
          page: 1,
          page_size: 20,
          total: 3,
          pages: 1,
        });
      }
      if (chemin.endsWith("/checklist")) {
        return Response.json([
          { group: "CARBON", expected: 5, found: 5 },
          { group: "SOCIAL", expected: 17, found: 13 },
        ]);
      }
      return Response.json([
        rapportListe("valide"),
        rapportListe("brouillon", {
          fiscal_year: 2025,
          status: "DRAFT",
          submitted_at: null,
          created_at: "2026-09-01T08:00:00Z",
          official_global_score: null,
        }),
      ]);
    });
    renderPage();

    const session = await screen.findByRole("region", { name: "Session active" });
    expect(within(session).getByText("FY2025")).toBeInTheDocument();
    expect(within(session).getByText("Brouillon")).toBeInTheDocument();
    expect(
      within(session).getByText(
        "Brouillon en cours de préparation. Remplissez la déclaration et soumettez-la pour examen.",
      ),
    ).toBeInTheDocument();
    expect(await within(session).findByText("18/22 indicateurs détectés")).toBeInTheDocument();
    expect(
      within(session).getByRole("link", { name: /Accéder à ma déclaration en cours/ }),
    ).toHaveAttribute("href", "/company/declarations");

    const score = screen.getByRole("region", { name: "Dernier score officiel" });
    expect(score).toHaveTextContent("74,5/100");
    expect(score).toHaveTextContent("Taux de couverture : 88 %");
    expect(within(score).getByTitle("a".repeat(64))).toBeInTheDocument();

    const fil = await screen.findByRole("list", { name: "Activité récente" });
    expect(within(fil).getByText("Score officiel publié")).toBeInTheDocument();
    expect(within(fil).getByText("Rapport transmis")).toBeInTheDocument();
    expect(within(fil).queryByText(/auditeur/)).not.toBeInTheDocument();
  });

  it.each([
    [
      "EXTRACTING",
      null,
      "En cours d'examen",
      "Votre rapport a été transmis et est en cours d'examen par l'équipe d'audit.",
    ],
    [
      "IN_AUDIT",
      "2026-09-02T10:00:00Z",
      "En cours d'examen",
      "Votre rapport a été transmis et est en cours d'examen par l'équipe d'audit.",
    ],
    [
      "REVISION_REQUESTED",
      "2026-09-02T10:00:00Z",
      "Correction demandée",
      "L'auditeur a demandé des précisions ou corrections sur votre rapport.",
    ],
  ])(
    "présente une session %s sans nommer d’étape interne",
    async (statut, soumis, badge, texte) => {
      fetchMock.mockImplementation(async (url) =>
        String(url).includes("/notifications")
          ? Response.json({ items: [], page: 1, page_size: 20, total: 0, pages: 0 })
          : Response.json([
              rapportListe("session", {
                fiscal_year: 2025,
                status: statut,
                submitted_at: soumis,
                extraction_finished_at: null,
                official_global_score: null,
              }),
            ]),
      );
      renderPage();

      const session = await screen.findByRole("region", { name: "Session active" });
      expect(within(session).getByText("FY2025")).toBeInTheDocument();
      expect(within(session).getByText(badge)).toBeInTheDocument();
      expect(within(session).getByText(texte)).toBeInTheDocument();
      expect(session).not.toHaveTextContent("Analyse du fichier");
      expect(
        within(session).getByRole("link", { name: /Accéder à ma déclaration en cours/ }),
      ).toHaveAttribute("href", "/company/declarations");
    },
  );

  it("n’affiche jamais le score de l’exercice en cours d’examen, mais le dernier exercice antérieur validé", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).includes("/notifications")
        ? Response.json({ items: [], page: 1, page_size: 20, total: 0, pages: 0 })
        : Response.json([
            rapportListe("v2023", { fiscal_year: 2023, official_global_score: 61.2 }),
            rapportListe("v2025", { fiscal_year: 2025, official_global_score: 66.7 }),
            rapportListe("enCours", {
              fiscal_year: 2025,
              type: "RAPPORT_ANNUEL",
              status: "IN_AUDIT",
              created_at: "2026-09-20T08:00:00Z",
              official_global_score: null,
            }),
          ]),
    );
    renderPage();

    const session = await screen.findByRole("region", { name: "Session active" });
    expect(within(session).getByText("FY2025")).toBeInTheDocument();
    const score = screen.getByRole("region", { name: "Dernier score officiel" });
    expect(score).toHaveTextContent("FY2023");
    expect(score).toHaveTextContent("61,2/100");
    expect(score).not.toHaveTextContent("66,7");
  });

  it("sans déclaration ni score, invite à en ouvrir une", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).includes("/notifications")
        ? Response.json({ items: [], page: 1, page_size: 20, total: 0, pages: 0 })
        : Response.json([]),
    );
    renderPage();

    expect(await screen.findByText("Aucune déclaration en cours.")).toBeInTheDocument();
    expect(screen.getByText("Aucun score officiel publié")).toBeInTheDocument();
    expect(await screen.findByText("Aucun jalon pour l’instant.")).toBeInTheDocument();
  });
});
