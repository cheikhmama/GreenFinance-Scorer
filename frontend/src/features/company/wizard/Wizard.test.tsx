import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { renderCompany } from "../test/renderCompany";

const ID = "88888888-8888-8888-8888-888888888888";
const SHA = "b".repeat(64);
const fetchMock = vi.fn<typeof fetch>();

type Rapport = Record<string, unknown>;

function brouillon(surcharges: Rapport = {}): Rapport {
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

function reponse(r: Rapport) {
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
function serveur(initial: Rapport | null, liste: unknown[] = []) {
  let etat = initial;
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    const methode = init?.method ?? "GET";
    if (chemin.includes("/notifications"))
      return Response.json({ items: [], total: 0, page: 1, page_size: 1 });
    if (chemin.endsWith("/checklist"))
      return Response.json([{ group: "SOCIAL", expected: 6, found: 4 }]);
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
    await user.selectOptions(await screen.findByLabelText("Devise"), "EUR");
    await user.type(screen.getByLabelText("Chiffre d’affaires"), "1000000");

    await user.click(screen.getByRole("button", { name: "Précédent" }));
    await user.click(await screen.findByRole("button", { name: "Suivant" }));
    expect(await screen.findByLabelText("Chiffre d’affaires")).toHaveValue(1000000);

    await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() => expect(appels("POST", "/reports")).toHaveLength(1));
    const corps = JSON.parse(String(appels("POST", "/reports")[0][1]?.body));
    expect(corps).toMatchObject({ currency: "EUR", revenue: 1000000 });
    await waitFor(() => expect(router.state.location.pathname).toMatch(/\/brouillon\/document$/));
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

  it("ne propose plus un exercice validé ; un montant négatif est refusé", async () => {
    serveur(null, [
      {
        id: "valide",
        status: "VALIDATED",
        fiscal_year: new Date().getFullYear() - 1,
        previous_report_id: null,
        created_at: "2026-01-10T08:00:00Z",
        type: "RAPPORT_ESG",
        version: 1,
      },
    ]);
    const user = userEvent.setup();
    renderCompany("/company/declarations/nouvelle/exercice");
    const exercice = await screen.findByLabelText("Exercice fiscal");
    expect(
      within(exercice).queryByRole("option", { name: `FY${new Date().getFullYear() - 1}` }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Suivant" }));
    await user.selectOptions(await screen.findByLabelText("Devise"), "MRU");
    await user.type(await screen.findByLabelText("Valeur d’entreprise (EVIC)"), "-5");
    await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    expect(await screen.findByText("Le montant doit être positif.")).toBeInTheDocument();
    expect(appels("POST", "/reports")).toHaveLength(0);
  });

  it("devise retirée après saisie d’un montant invalide : création sans montant", async () => {
    serveur(null);
    const user = userEvent.setup();
    renderCompany("/company/declarations/nouvelle/finances");
    await user.selectOptions(await screen.findByLabelText("Devise"), "EUR");
    await user.type(await screen.findByLabelText("Valeur d’entreprise (EVIC)"), "-5");
    await user.selectOptions(screen.getByLabelText("Devise"), "");
    await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() => expect(appels("POST", "/reports")).toHaveLength(1));
    const corps = JSON.parse(String(appels("POST", "/reports")[0][1]?.body));
    expect(corps).not.toHaveProperty("revenue");
    expect(corps).not.toHaveProperty("enterprise_value");
    expect(corps).not.toHaveProperty("currency");
  });

  it("saisie modifiée : quitter l’assistant demande confirmation ; Suivant et la création non", async () => {
    serveur(null);
    const user = userEvent.setup();
    const { router } = renderCompany("/company/declarations/nouvelle/exercice");
    await user.selectOptions(await screen.findByLabelText("Type de rapport"), "RAPPORT_ANNUEL");
    // (b) exercice -> finances : jamais de confirmation.
    await user.click(screen.getByRole("button", { name: "Suivant" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/company/declarations/nouvelle/finances"),
    );
    expect(screen.queryByText("Abandonner la saisie ?")).not.toBeInTheDocument();
    // (a) sortie vers une route extérieure : confirmation, puis reste sur place.
    void router.navigate("/company/declarations");
    expect(await screen.findByText("Abandonner la saisie ?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Continuer la saisie" }));
    expect(router.state.location.pathname).toBe("/company/declarations/nouvelle/finances");
    // (c) création réussie : pas de confirmation.
    await user.click(screen.getByRole("button", { name: "Créer le brouillon" }));
    await waitFor(() => expect(router.state.location.pathname).toMatch(/\/brouillon\/document$/));
    expect(screen.queryByText("Abandonner la saisie ?")).not.toBeInTheDocument();
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
      expect(router.state.location.pathname).toBe(
        `/company/declarations/${ID}/brouillon/verification`,
      ),
    );
    expect(await screen.findByRole("region", { name: "Liste de complétude" })).toHaveTextContent(
      "4/6",
    );

    const soumettre = screen.getByRole("button", { name: "Soumettre la déclaration" });
    expect(soumettre).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /verrouillée/ }));
    await user.click(soumettre);
    const recu = await screen.findByRole("region", { name: "Reçu de soumission" });
    expect(recu).toHaveTextContent(SHA);
    expect(appels("POST", "/submit")).toHaveLength(1);
    // Le statut bascule (rail des piliers) : le reçu reste le même élément, monté.
    await screen.findByRole("navigation", { name: "Sections de la déclaration" });
    expect(recu).toBeInTheDocument();
  });

  it("vérification demandée pendant l’analyse : renvoyée au document (Review Focus 3)", async () => {
    serveur(brouillon({ status: "EXTRACTING", source_file: "x.pdf" }));
    const { router } = renderCompany(`/company/declarations/${ID}/brouillon/verification`);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/company/declarations/${ID}/brouillon/document`),
    );
    expect(await screen.findByText(/Lecture de .* en cours/)).toBeInTheDocument();
  });

  it("analyse en échec : cause dite, nouveau fichier possible", async () => {
    serveur(brouillon({ source_file: "x.pdf", extraction_error: "docling_conversion_echouee" }));
    renderCompany(`/company/declarations/${ID}/brouillon/document`);
    expect(await screen.findByText("Le fichier n’a pas pu être lu")).toBeInTheDocument();
    expect(
      screen.getByText(
        `${libelleCauseExtraction("docling_conversion_echouee")}. Joignez de nouveau le fichier.`,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyser ce fichier" })).toBeInTheDocument();
  });
});
