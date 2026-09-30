import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { CrossValidationPage } from "./CrossValidationPage";

const ID = "77777777-7777-7777-7777-777777777777";
const fetchMock = vi.fn<typeof fetch>();
const JEU = {
  id: ID,
  name: "Kaggle ESG",
  source_url: "https://www.kaggle.com/x",
  licence: "CC BY 4.0",
  scale_min: 0,
  scale_max: 1000,
  higher_is_better: true,
  created_at: "2026-10-01T00:00:00",
  row_count: 3,
};
const RAPPORT = {
  dataset: JEU,
  matched: 3,
  unmatched: 1,
  agreement: [
    { score: "GLOBAL", pairs: 3, spearman: 1, mean_absolute_difference: 6.6 },
    { score: "SOCIAL", pairs: 0, spearman: null, mean_absolute_difference: null },
  ],
  matches: [
    {
      line: 2,
      company_id: ID,
      company_name: "Atlas",
      dataset_scores: { GLOBAL: 45 },
      platform_scores: { GLOBAL: 40 },
    },
  ],
  unmatched_lines: [
    { line: 6, isin: "FR0000120271", lei: null, company_name: "Hors", reason: "UNKNOWN" },
  ],
};

beforeEach(() => {
  fetchMock.mockReset();
  let importe = false;
  fetchMock.mockImplementation(async (url, init) => {
    const chemin = String(url);
    if (init?.method === "POST") {
      importe = true;
      return Response.json(
        {
          dataset: JEU,
          imported: 3,
          skipped: 1,
          skipped_lines: [{ line: 5, reason: "aucun ISIN ni LEI valide" }],
        },
        { status: 201 },
      );
    }
    if (chemin.endsWith("/cross-validation")) return Response.json(RAPPORT);
    return Response.json(importe ? [JEU] : []);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ConfirmProvider>
        <CrossValidationPage />
      </ConfirmProvider>
    </QueryClientProvider>,
  );
}

describe("CrossValidationPage", () => {
  it("importe un jeu, liste les lignes écartées et affiche la comparaison", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Aucun jeu de données importé.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Nom du jeu de données"), "Kaggle ESG");
    await user.type(screen.getByLabelText("Adresse de la source"), "https://www.kaggle.com/x");
    await user.type(screen.getByLabelText("Licence"), "CC BY 4.0");
    await user.clear(screen.getByLabelText("Échelle : maximum"));
    await user.type(screen.getByLabelText("Échelle : maximum"), "1000");
    await user.upload(
      screen.getByLabelText("Fichier CSV"),
      new File(["isin,total\n"], "jeu.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: "Importer" }));

    expect(await screen.findByText("3 ligne(s) importée(s), 1 écartée(s)")).toBeInTheDocument();
    expect(screen.getByText("Ligne 5 : aucun ISIN ni LEI valide")).toBeInTheDocument();
    const corps = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")?.[1]
      ?.body as FormData;
    expect(corps.get("scale_max")).toBe("1000");
    expect(corps.get("higher_is_better")).toBe("true");
    // Le rapport du jeu importé s'affiche aussitôt.
    expect(await screen.findByText("Score global")).toBeInTheDocument();
    expect(screen.getByText("Aucune entreprise de votre périmètre")).toBeInTheDocument();
    expect(screen.getByText("6,6")).toBeInTheDocument();
    expect(screen.getByText("Atlas")).toBeInTheDocument();
  });
});
