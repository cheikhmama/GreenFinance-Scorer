import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { CompanyReportDetailPage } from "./CompanyReportDetailPage";

const ID = "77777777-7777-7777-7777-777777777777";
const SHA = "a".repeat(64);
const fetchMock = vi.fn<typeof fetch>();

function rapport(surcharges: Record<string, unknown> = {}) {
  return {
    id: ID,
    company_id: ID,
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: null,
    status: "DRAFT",
    source_file: "rapports/x.pdf",
    original_filename: "rapport-2025.pdf",
    fiscal_year: 2025,
    extraction_finished_at: "2026-09-01T09:00:00Z",
    extraction_error: null,
    extraction_attempts: 0,
    version: 1,
    previous_report_id: null,
    checksum_sha256: SHA,
    metrics: [],
    carbon_data: [],
    declared_global_score: null,
    declared_global_score_proof: null,
    official_score: null,
    coverage: { total_targets: 0, found: 0, missing_codes: [] },
    ...surcharges,
  };
}

const LISTE = [
  { group: "CARBON", expected: 5, found: 3 },
  { group: "ENVIRONNEMENT", expected: 5, found: 2 },
  { group: "SOCIAL", expected: 6, found: 6 },
  { group: "GOUVERNANCE", expected: 3, found: 1 },
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
      <ConfirmProvider>
        <MemoryRouter initialEntries={[`/company/declarations/${ID}`]}>
          <Routes>
            <Route path="/company/declarations/:rapportId" element={<CompanyReportDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

function appels(methode: string, suffixe: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => (init?.method ?? "GET") === methode && String(url).endsWith(suffixe),
  );
}

describe("Espace Entreprise — préparer, soumettre et verrouiller une déclaration", () => {
  it("affiche la liste de complétude sans valeurs, puis soumet et donne le reçu", async () => {
    let etat = rapport();
    fetchMock.mockImplementation(async (url, init) => {
      const chemin = String(url);
      if (chemin.endsWith("/checklist")) return Response.json(LISTE);
      if (init?.method === "POST" && chemin.endsWith("/submit")) {
        etat = rapport({ status: "AWAITING_ASSIGNMENT", submitted_at: "2026-09-02T10:30:00Z" });
        return Response.json({
          id: ID,
          company_id: ID,
          report_type: "RAPPORT_ESG",
          fiscal_year: 2025,
          status: "AWAITING_ASSIGNMENT",
          version: 1,
          previous_report_id: null,
          created_at: etat.created_at,
          submitted_at: etat.submitted_at,
          original_filename: "rapport-2025.pdf",
          official_score: null,
          checksum_sha256: SHA,
          extraction_finished_at: etat.extraction_finished_at,
          extraction_error: null,
        });
      }
      return Response.json(etat);
    });
    const user = userEvent.setup();
    renderPage();

    const liste = await screen.findByRole("region", { name: "Liste de complétude" });
    expect(liste).toHaveTextContent("Indicateurs détectés : 12/19");
    expect(within(liste).getByText("Émissions carbone")).toBeInTheDocument();
    expect(within(liste).getByText("3 / 5 trouvé(s)")).toBeInTheDocument();
    expect(within(liste).getByText("· 3 manquant(s)")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Préparation");
    expect(screen.queryByText("Indicateurs ESG")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Déclaration verrouillée" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Soumettre" }));
    const dialogue = await screen.findByRole("dialog");
    expect(dialogue).toHaveTextContent(SHA);
    expect(dialogue).toHaveTextContent("12 indicateur(s) trouvé(s) sur 19");
    await user.click(within(dialogue).getByRole("button", { name: "Confirmer la soumission" }));

    expect(await within(dialogue).findByText("Reçu de soumission")).toBeInTheDocument();
    expect(dialogue).toHaveTextContent(SHA);
    expect(dialogue).toHaveTextContent("rapport-2025.pdf");
    expect(appels("POST", "/submit")).toHaveLength(1);
    expect(appels("POST", "/submit")[0]?.[0]).toBe(`/api/v1/reports/${ID}/submit`);

    await user.click(within(dialogue).getByRole("button", { name: "Terminer" }));
    const bandeau = await screen.findByRole("region", { name: "Déclaration verrouillée" });
    expect(bandeau).toHaveTextContent(/Soumis le 2 septembre 2026 à \d{2}:30 — lecture seule/);
    expect(bandeau).toHaveTextContent(SHA);
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Examen");
    expect(screen.queryByRole("button", { name: "Soumettre" })).not.toBeInTheDocument();
    expect(screen.getByText("En cours d'examen")).toBeInTheDocument();
  });

  it("joint le PDF d’un brouillon vide et suit l’analyse sans le verrouiller", async () => {
    let etat = rapport({
      source_file: null,
      original_filename: null,
      extraction_finished_at: null,
      checksum_sha256: null,
    });
    fetchMock.mockImplementation(async (url, init) => {
      if (init?.method === "POST" && String(url).endsWith("/file")) {
        etat = rapport({ status: "EXTRACTING", extraction_finished_at: null });
        return Response.json({ ...etat, report_type: "RAPPORT_ESG", official_score: null });
      }
      return Response.json(etat);
    });
    const user = userEvent.setup();
    renderPage();

    const champ = await screen.findByLabelText("Rapport (PDF, 50 Mo au plus)");
    await user.click(screen.getByRole("button", { name: "Joindre et analyser" }));
    expect(screen.getByText("Un fichier PDF est requis.")).toBeInTheDocument();
    expect(appels("POST", "/file")).toHaveLength(0);

    await user.upload(
      champ,
      new File(["%PDF-1.7"], "rapport-2025.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Joindre et analyser" }));

    expect(await screen.findByText(/Lecture de « rapport-2025.pdf » en cours/)).toBeInTheDocument();
    const envoi = appels("POST", "/file")[0];
    expect(envoi?.[0]).toBe(`/api/v1/reports/${ID}/file`);
    const corps = envoi?.[1]?.body;
    expect(corps).toBeInstanceOf(FormData);
    expect(((corps as FormData).get("file") as File).name).toBe("rapport-2025.pdf");
    expect(screen.getByText("En cours d'examen")).toBeInTheDocument();
    expect(screen.queryByText(/Analyse du fichier/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Soumettre" })).not.toBeInTheDocument();
  });

  it("signale un échec d’analyse et propose de joindre à nouveau le fichier", async () => {
    fetchMock.mockImplementation(async () =>
      Response.json(rapport({ extraction_error: "docling_conversion_echouee" })),
    );
    renderPage();

    expect(await screen.findByText("Le fichier n’a pas pu être lu")).toBeInTheDocument();
    expect(screen.getByLabelText("Remplacer le fichier")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Soumettre" })).not.toBeInTheDocument();
    await waitFor(() => expect(appels("GET", "/checklist")).toHaveLength(0));
  });
});

const PREUVE = {
  id: "p1",
  document_name: "rapport-2025.pdf",
  year: 2025,
  total_pages: 80,
  page_start: 44,
  page_end: 44,
  excerpt_pdf_path: "",
};

const SOUMIS = {
  submitted_at: "2026-09-02T08:30:00Z",
  metrics: [
    {
      id: "m1",
      pillar: "ENVIRONNEMENT",
      metric_code: "consommation_eau_m3",
      value: 125400,
      unit: "m3",
      method: "RAPPORTEE",
      proof: PREUVE,
      raw_value: null,
      section: null,
      proof_text: null,
      value_year: 2025,
      confidence: null,
    },
    {
      id: "m2",
      pillar: "GOUVERNANCE",
      metric_code: "femmes_conseil_pourcentage",
      value: 33.3,
      unit: "%",
      method: "CALCULEE",
      proof: { ...PREUVE, page_start: 58, page_end: 59 },
      raw_value: null,
      section: null,
      proof_text: null,
      value_year: 2025,
      confidence: null,
    },
  ],
  carbon_data: [
    {
      id: "c1",
      scope: 1,
      ghg_category: null,
      tonnes_co2e: 18450.2,
      year: 2025,
      method: "ESTIMEE",
      pcaf_data_quality: 2,
      proof: PREUVE,
      raw_value: null,
      section: null,
      proof_text: null,
      value_year: 2025,
      confidence: null,
    },
  ],
};

describe("Espace Entreprise — déclaration soumise ou décidée", () => {
  it("validée : score officiel par pilier, synthèse PDF, examen dit terminé", async () => {
    fetchMock.mockImplementation(async () =>
      Response.json(
        rapport({
          ...SOUMIS,
          status: "VALIDATED",
          synthesis_available: true,
          official_score: {
            global_score: 71.4,
            environmental_score: 68.2,
            social_score: 74.9,
            governance_score: 72,
            coverage_rate: 0.86,
            config_version: 3,
          },
        }),
      ),
    );
    renderPage();

    const score = await screen.findByRole("region", { name: "Score officiel" });
    expect(score).toHaveTextContent("71,4/100");
    expect(score).toHaveTextContent("couverture 86 %");
    expect(within(score).getByRole("progressbar", { name: "Social" })).toHaveAttribute(
      "aria-valuenow",
      "74.9",
    );
    expect(screen.getByRole("link", { name: /Synthèse PDF/ })).toHaveAttribute(
      "href",
      `/api/v1/company/rapports/${ID}/synthese/fichier`,
    );
    expect(screen.getByRole("region", { name: "Déclaration verrouillée" })).toHaveTextContent(
      "L’examen est terminé",
    );
  });

  it("valeurs extraites : libellés lisibles, nombres au format français, page source", async () => {
    fetchMock.mockImplementation(async () =>
      Response.json(rapport({ ...SOUMIS, status: "IN_AUDIT" })),
    );
    renderPage();

    const [indicateurs, carbone] = await screen.findAllByRole("table");
    const ligneEau = within(indicateurs).getByRole("row", { name: /consommation/i });
    expect(ligneEau).toHaveTextContent("Environnement");
    expect(ligneEau).toHaveTextContent("125 400 m³");
    expect(ligneEau).toHaveTextContent("Publiée");
    expect(ligneEau).toHaveTextContent("p. 44");
    const ligneConseil = within(indicateurs).getByRole("row", {
      name: /Part de femmes au conseil/,
    });
    expect(ligneConseil).toHaveTextContent("33,3 %");
    expect(ligneConseil).toHaveTextContent("p. 58–59");
    expect(carbone).toHaveTextContent("18 450,2 tCO₂e");
    expect(document.body.textContent).not.toMatch(/RAPPORTEE|ENVIRONNEMENT|femmes_conseil/);
    expect(screen.getByRole("region", { name: "Déclaration verrouillée" })).toHaveTextContent(
      "pendant l’examen",
    );
    expect(screen.queryByRole("region", { name: "Score officiel" })).not.toBeInTheDocument();
  });

  it("correction demandée : l’exercice proposé est celui de la déclaration", async () => {
    fetchMock.mockImplementation(async () =>
      Response.json(rapport({ ...SOUMIS, status: "REVISION_REQUESTED", fiscal_year: 2023 })),
    );
    renderPage();

    expect(await screen.findByLabelText("Exercice")).toHaveValue(2023);
    expect(screen.getByLabelText("Fichier PDF corrigé")).toBeInTheDocument();
  });
});
