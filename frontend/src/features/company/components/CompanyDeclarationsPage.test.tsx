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

describe("Espace Entreprise — Mes déclarations", () => {
  it("sépare les déclarations en cours de l’historique, avec score, empreinte et synthèse", async () => {
    fetchMock.mockImplementation(async () => Response.json(RAPPORTS));
    renderPage();

    const enCours = await screen.findByRole("region", { name: "En cours" });
    expect(within(enCours).getByText("FY2025")).toBeInTheDocument();
    expect(within(enCours).getByText("FY2023")).toBeInTheDocument();
    expect(within(enCours).getByText("En cours d'examen 🔒")).toBeInTheDocument();
    expect(within(enCours).getAllByRole("list", { name: "Étapes de la déclaration" })).toHaveLength(
      2,
    );

    const historique = screen.getByRole("table");
    const lignes = within(historique).getAllByRole("row").slice(1);
    expect(lignes).toHaveLength(2);
    expect(lignes[0]).toHaveTextContent("FY2024");
    expect(lignes[0]).toHaveTextContent("74,5/100");
    expect(lignes[0]).toHaveTextContent("couverture 88 %");
    expect(within(lignes[0] as HTMLElement).getByTitle(SHA)).toBeInTheDocument();
    expect(within(lignes[0] as HTMLElement).getByRole("link", { name: "PDF" })).toHaveAttribute(
      "href",
      "/api/v1/company/rapports/valide/synthese/fichier",
    );
    expect(lignes[1]).toHaveTextContent("FY2023");
  });

  it("ouvre un exercice avec ses données financières depuis la modale, puis mène au brouillon", async () => {
    fetchMock.mockImplementation(async (_url, init) =>
      init?.method === "POST"
        ? Response.json({ id: "nouveau" }, { status: 201 })
        : Response.json([]),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Nouvelle déclaration" }));
    const modale = await screen.findByRole("dialog");
    const annee = new Date().getFullYear() - 2;
    await user.selectOptions(within(modale).getByLabelText("Exercice fiscal"), String(annee));
    await user.selectOptions(within(modale).getByLabelText("Devise"), "MRU");
    await user.type(within(modale).getByLabelText("Chiffre d’affaires"), "820000000");
    await user.type(within(modale).getByLabelText("Valeur d’entreprise (EVIC)"), "-5");
    await user.click(within(modale).getByRole("button", { name: "Ouvrir la déclaration" }));
    expect(await within(modale).findByText("Le montant doit être positif.")).toBeInTheDocument();

    await user.clear(within(modale).getByLabelText("Valeur d’entreprise (EVIC)"));
    await user.type(within(modale).getByLabelText("Valeur d’entreprise (EVIC)"), "1450000000");
    await user.click(within(modale).getByRole("button", { name: "Ouvrir la déclaration" }));

    expect(await screen.findByRole("heading", { name: "Page du brouillon" })).toBeInTheDocument();
    const envoi = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(envoi?.[0]).toBe("/api/v1/reports");
    expect(JSON.parse(envoi?.[1]?.body as string)).toEqual({
      report_type: "RAPPORT_ESG",
      fiscal_year: annee,
      currency: "MRU",
      revenue: 820000000,
      enterprise_value: 1450000000,
    });
  });
});
