import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuditReviewPage } from "./AuditReviewPage";
import { prochaineARevoir, type ValeurARevoir } from "./valeurs";

// pdf.js n'a pas de canvas sous jsdom : le visualiseur est remplacé par un témoin de ses props.
vi.mock("./PdfPageViewer", () => ({
  PdfPageViewer: ({ url, boites }: { url: string; boites: unknown[] }) => (
    <div data-testid="visualiseur" data-url={url} data-boites={boites.length} />
  ),
}));

const ID = "88888888-8888-8888-8888-888888888888";
const fetchMock = vi.fn<typeof fetch>();

function preuve(id: string) {
  return {
    id,
    document_name: "rapport.pdf",
    year: 2025,
    total_pages: 40,
    page_start: 12,
    page_end: 12,
    excerpt_pdf_path: "x.pdf",
  };
}

function indicateur(id: string, code: string, pillar: string, value: number) {
  return {
    id,
    metric_code: code,
    pillar,
    value,
    unit: "%",
    raw_value: `${value} %`,
    proof_text: `${code} : ${value} %`,
    section: null,
    value_year: 2025,
    confidence: "HIGH",
    proof: preuve(`p-${id}`),
    proof_boxes: [{ page: 12, x0: 0.1, y0: 0.2, x1: 0.3, y1: 0.25 }],
    review_status: "PENDING",
    audited_value: null,
  };
}

function dossierInitial() {
  return {
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
    metrics: [
      indicateur("m1", "Femmes dans l’effectif", "SOCIAL", 30),
      indicateur("m2", "Énergie renouvelable", "ENVIRONNEMENT", 40),
    ],
    carbon_data: [],
    coverage: { total_targets: 2, found: 2, missing_codes: [] },
  };
}

let dossier = dossierInitial();
const PRE_SCORE = {
  computable: true,
  global_score: 61.5,
  environmental_score: 70,
  social_score: 55,
  governance_score: null,
  coverage_rate: 0.8,
};

function envois(suffixe: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) => init?.method === "POST" && String(url).endsWith(suffixe),
  );
}

beforeEach(() => {
  dossier = dossierInitial();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    if (init?.method === "POST" && chemin.endsWith("/reviews")) {
      const corps = JSON.parse(init.body as string);
      dossier = {
        ...dossier,
        metrics: dossier.metrics.map((m) =>
          m.id === corps.metric_id
            ? { ...m, review_status: corps.decision, audited_value: corps.new_value ?? null }
            : m,
        ),
      };
      return Response.json({}, { status: 201 });
    }
    if (init?.method === "POST" && chemin.endsWith("/avis")) {
      dossier = { ...dossier, status: "PENDING_DECISION" };
      return new Response(null, { status: 204 });
    }
    if (chemin.endsWith("/reviews")) return Response.json([]);
    if (chemin.endsWith("/pre-score")) return Response.json(PRE_SCORE);
    return Response.json(dossier);
  });
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
          <Route path="/audit/rapports/:rapportId" element={<AuditReviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function valeurCourante() {
  return within(screen.getByRole("complementary", { name: "Détail de la valeur" })).getByRole(
    "heading",
    { level: 2 },
  );
}

describe("Espace de revue de l’Auditeur — trois volets", () => {
  it("affiche la liste, la page-preuve avec ses boîtes et le détail de la valeur", async () => {
    renderPage();

    expect(await screen.findByText("0 / 2 valeur(s) revue(s)")).toBeInTheDocument();
    const liste = screen.getByRole("navigation", { name: "Valeurs à revoir" });
    // Ordre de revue : environnement avant social.
    const libelles = within(liste)
      .getAllByRole("button")
      .map((b) => b.textContent);
    expect(libelles[0]).toContain("Énergie renouvelable");
    expect(valeurCourante()).toHaveTextContent("Énergie renouvelable");
    const visualiseur = screen.getByTestId("visualiseur");
    expect(visualiseur).toHaveAttribute(
      "data-url",
      `/api/v1/audit/rapports/${ID}/preuves/p-m2/fichier`,
    );
    expect(visualiseur).toHaveAttribute("data-boites", "1");
  });

  it("J / K naviguent, A accepte puis passe à la valeur suivante à revoir", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("0 / 2 valeur(s) revue(s)");

    await user.keyboard("j");
    expect(valeurCourante()).toHaveTextContent("Femmes dans l’effectif");
    await user.keyboard("k");
    expect(valeurCourante()).toHaveTextContent("Énergie renouvelable");

    await user.keyboard("a");
    await waitFor(() => expect(valeurCourante()).toHaveTextContent("Femmes dans l’effectif"));
    expect(JSON.parse(envois("/reviews")[0]?.[1]?.body as string)).toEqual({
      metric_id: "m2",
      decision: "ACCEPTED",
    });
    expect(await screen.findByText("1 / 2 valeur(s) revue(s)")).toBeInTheDocument();
  });

  it("E ouvre la correction ; taper dans le champ ne déclenche aucun raccourci", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("0 / 2 valeur(s) revue(s)");

    await user.keyboard("e");
    const champ = screen.getByLabelText("Valeur corrigée (%)");
    expect(champ).toHaveFocus();
    await user.clear(champ);
    await user.type(champ, "41,5 jka");
    expect(envois("/reviews")).toHaveLength(0);

    await user.clear(champ);
    await user.type(champ, "41,5");
    await user.selectOptions(screen.getByLabelText("Motif"), "UNIT_ERROR");
    await user.click(screen.getByRole("button", { name: "Enregistrer la correction" }));

    await waitFor(() => expect(envois("/reviews")).toHaveLength(1));
    expect(JSON.parse(envois("/reviews")[0]?.[1]?.body as string)).toEqual({
      metric_id: "m2",
      decision: "OVERRIDDEN",
      new_value: 41.5,
      reason: "UNIT_ERROR",
    });
  });

  it("l’avis n’est possible qu’une fois tout revu ; le pré-score n’apparaît qu’après", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("0 / 2 valeur(s) revue(s)");

    const rendre = screen.getByRole("button", { name: "Rendre l’avis" });
    expect(rendre).toBeDisabled();
    expect(screen.queryByRole("region", { name: "Pré-score" })).not.toBeInTheDocument();

    await user.keyboard("a");
    await screen.findByText("1 / 2 valeur(s) revue(s)");
    await user.keyboard("n");
    await user.click(screen.getByRole("button", { name: "Confirmer : non trouvée" }));
    await screen.findByText("2 / 2 valeur(s) revue(s)");
    expect(JSON.parse(envois("/reviews")[1]?.[1]?.body as string)).toMatchObject({
      decision: "NOT_FOUND",
      reason: "NOT_IN_SOURCE",
    });

    await user.click(screen.getByRole("button", { name: "Rendre l’avis" }));
    const dialogue = await screen.findByRole("dialog");
    await user.selectOptions(within(dialogue).getByLabelText("Décision"), "UNFAVORABLE");
    await user.click(within(dialogue).getByRole("button", { name: "Envoyer l’avis" }));
    await waitFor(() =>
      expect(within(dialogue).getByLabelText("Commentaire")).toHaveAttribute(
        "aria-invalid",
        "true",
      ),
    );
    expect(envois("/avis")).toHaveLength(0);

    await user.type(within(dialogue).getByLabelText("Commentaire"), "Valeur sociale introuvable.");
    await user.click(within(dialogue).getByRole("button", { name: "Envoyer l’avis" }));

    expect(await screen.findByText("Avis déjà rendu")).toBeInTheDocument();
    expect(JSON.parse(envois("/avis")[0]?.[1]?.body as string)).toEqual({
      decision: "UNFAVORABLE",
      comment: "Valeur sociale introuvable.",
    });
    expect(await screen.findByRole("region", { name: "Pré-score" })).toHaveTextContent(
      "61,5 / 100",
    );
    expect(screen.queryByRole("button", { name: "Rendre l’avis" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Accepter/ })).not.toBeInTheDocument();
  });
});

describe("prochaineARevoir", () => {
  const v = (statut: ValeurARevoir["statut"]) => ({ statut }) as ValeurARevoir;

  it("boucle jusqu’à la prochaine valeur à revoir, ou reste sur place s’il n’y en a plus", () => {
    expect(prochaineARevoir([v("PENDING"), v("ACCEPTED"), v("ACCEPTED")], 1)).toBe(0);
    expect(prochaineARevoir([v("ACCEPTED"), v("ACCEPTED"), v("PENDING")], 0)).toBe(2);
    expect(prochaineARevoir([v("ACCEPTED"), v("ACCEPTED")], 1)).toBe(1);
  });
});
