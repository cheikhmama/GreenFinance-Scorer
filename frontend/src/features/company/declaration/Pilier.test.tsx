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

  it("segment avec préfixe lisible (rapport-esg-fy2025-UUID) : même page", async () => {
    servir(rapport());
    renderCompany(`/company/declarations/rapport-esg-fy2025-${ID}/environnement`);
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
    expect(
      await screen.findByRole("dialog", { name: "Indicateur introuvable" }),
    ).toBeInTheDocument();
  });
});
