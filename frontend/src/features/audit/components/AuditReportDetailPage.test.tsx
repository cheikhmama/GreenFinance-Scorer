import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuditReportDetailPage } from "./AuditReportDetailPage";

const ID = "88888888-8888-8888-8888-888888888888";
const fetchMock = vi.fn<typeof fetch>();

const DOSSIER = {
  id: ID,
  company_id: ID,
  type: "RAPPORT_ESG",
  channel: "ENTREPRISE",
  created_at: "2026-09-01T00:00:00",
  submitted_at: "2026-09-01T00:00:00",
  status: "IN_AUDIT",
  fiscal_year: 2025,
  declared_global_score: null,
  declared_global_score_proof: null,
  official_score: null,
  metrics: [],
  carbon_data: [],
  coverage: { total_targets: 0, found: 0, missing_codes: [] },
};

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
      <MemoryRouter initialEntries={[`/audit/rapports/${ID}`]}>
        <Routes>
          <Route path="/audit/rapports/:rapportId" element={<AuditReportDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Espace Auditeur — rendre un avis sur un dossier", () => {
  it("exige un commentaire pour un avis défavorable, puis transmet l’avis", async () => {
    fetchMock.mockImplementation(async (_url, init) =>
      init?.method === "POST" ? new Response(null, { status: 204 }) : Response.json(DOSSIER),
    );
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Dossier RAPPORT_ESG — 2025")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Décision"), "UNFAVORABLE");
    await user.click(screen.getByRole("button", { name: "Envoyer l'avis" }));

    // Le même texte figure dans la description de la carte : vérifier le champ lui-même.
    await waitFor(() =>
      expect(screen.getByLabelText("Commentaire")).toHaveAttribute("aria-invalid", "true"),
    );
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);

    await user.type(screen.getByLabelText("Commentaire"), "Scope 3 sans preuve.");
    await user.click(screen.getByRole("button", { name: "Envoyer l'avis" }));

    expect(await screen.findByText("Avis transmis")).toBeInTheDocument();
    const envoi = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(envoi?.[0]).toBe(`/api/v1/audit/rapports/${ID}/avis`);
    expect(JSON.parse(envoi?.[1]?.body as string)).toEqual({
      decision: "UNFAVORABLE",
      comment: "Scope 3 sans preuve.",
    });
  });

  it("n’offre plus le formulaire une fois l’avis rendu", async () => {
    fetchMock.mockResolvedValue(Response.json({ ...DOSSIER, status: "PENDING_DECISION" }));
    renderPage();

    expect(await screen.findByText("Avis déjà rendu")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Envoyer l'avis" })).not.toBeInTheDocument();
  });
});
