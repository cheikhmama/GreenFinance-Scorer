import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCompany } from "../test/renderCompany";

const ID = "99999999-9999-9999-9999-999999999999";
const fetchMock = vi.fn<typeof fetch>();
const PDF = new File(["%PDF-1.7"], "corrige.pdf", { type: "application/pdf" });

function rapport() {
  return {
    id: ID,
    company_id: ID,
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-09-01T08:00:00Z",
    submitted_at: "2026-09-02T08:00:00Z",
    status: "REVISION_REQUESTED",
    source_file: "x.pdf",
    original_filename: "x.pdf",
    fiscal_year: 2025,
    extraction_finished_at: "2026-09-01T09:00:00Z",
    extraction_error: null,
    extraction_attempts: 1,
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
  };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    if (chemin.includes("/notifications"))
      return Response.json({ items: [], total: 0, page: 1, page_size: 1 });
    if (init?.method === "POST" && chemin.endsWith("/corrections")) {
      return Response.json(
        { ...rapport(), id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", status: "DRAFT" },
        { status: 201 },
      );
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
    expect(tiroir).toHaveTextContent("L'auditeur a demandé des précisions");
    expect(within(tiroir).queryByLabelText("Fichier PDF corrigé")).not.toBeInTheDocument();
    await user.click(within(tiroir).getByRole("button", { name: "Continuer" }));

    expect(within(tiroir).getByLabelText("Exercice")).toHaveValue(2025);
    await user.upload(within(tiroir).getByLabelText("Fichier PDF corrigé"), PDF);
    await user.click(within(tiroir).getByRole("button", { name: "Envoyer la correction" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(`/company/declarations/${ID}`));
    expect(await screen.findByText("Nouvelle version déposée")).toBeInTheDocument();

    const envoi = fetchMock.mock.calls.filter(
      ([url, init]) => init?.method === "POST" && String(url).endsWith("/corrections"),
    );
    expect(envoi).toHaveLength(1);
    const corps = envoi[0][1]?.body as FormData;
    expect(corps.get("annee_reporting")).toBe("2025");
    expect((corps.get("fichier") as File).name).toBe("corrige.pdf");
  });

  it("lien direct (cache froid) : l’exercice proposé est celui de la déclaration", async () => {
    const user = userEvent.setup();
    renderCompany(`/company/declarations/${ID}/correction`);
    const tiroir = await screen.findByRole("dialog", { name: "Correction demandée" });
    await user.click(within(tiroir).getByRole("button", { name: "Continuer" }));
    expect(within(tiroir).getByLabelText("Exercice")).toHaveValue(2025);
  });

  it("la progression reste à « En cours d’examen » avec la branche « Correction demandée »", async () => {
    renderCompany(`/company/declarations/${ID}`);
    await screen.findByRole("link", { name: "Corriger" });
    const progression = screen.getByRole("list", { name: "Progression" });
    expect(progression.querySelector("[aria-current='step']")).toHaveTextContent(
      "En cours d’examen",
    );
    expect(progression.parentElement).toHaveTextContent("Correction demandée");
  });

  it("aucun formulaire de correction dans la synthèse elle-même", async () => {
    renderCompany(`/company/declarations/${ID}`);
    await screen.findByRole("link", { name: "Corriger" });
    expect(screen.queryByLabelText("Fichier PDF corrigé")).not.toBeInTheDocument();
  });
});
