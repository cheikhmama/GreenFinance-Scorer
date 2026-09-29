import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ImportPositionsForm } from "./ImportPositionsForm";

const ID = "22222222-2222-2222-2222-222222222222";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderForm() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}
    >
      <ImportPositionsForm portefeuilleId={ID} />
    </QueryClientProvider>,
  );
}

const fichier = () => new File(["identifier,weight\nX,1\n"], "positions.csv", { type: "text/csv" });

describe("ImportPositionsForm", () => {
  it("envoie le fichier et la valeur totale, puis affiche le bilan", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { portfolio_id: ID, imported: 3, matched: 1, unmatched: 1, ambiguous: 1 },
        { status: 201 },
      ),
    );
    const user = userEvent.setup();
    renderForm();

    expect(screen.getByRole("button", { name: /Importer/ })).toBeDisabled();
    await user.upload(screen.getByLabelText("Fichier"), fichier());
    await user.type(screen.getByLabelText(/Valeur totale/), "10000");
    await user.click(screen.getByRole("button", { name: /Importer/ }));

    expect(await screen.findByText("3 position(s) importée(s)")).toBeInTheDocument();
    expect(
      screen.getByText(/1 rapprochée\(s\), 1 non reconnue\(s\), 1 ambiguë\(s\)/),
    ).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/api/v1/portfolios/${ID}/positions/import`);
    const corps = init?.body as FormData;
    expect((corps.get("file") as File).name).toBe("positions.csv");
    expect(corps.get("total_value")).toBe("10000");
  });

  it("liste les erreurs par ligne, l’erreur de fichier en premier", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          error: {
            code: "import_invalide",
            message: "Import refusé.",
            correlation_id: null,
            fields: {
              line_12: "ISIN invalide.",
              line_3: "Montant négatif.",
              file: "Somme des poids ≠ 1.",
            },
          },
        },
        { status: 422 },
      ),
    );
    const user = userEvent.setup();
    renderForm();

    await user.upload(screen.getByLabelText("Fichier"), fichier());
    await user.click(screen.getByRole("button", { name: /Importer/ }));

    expect(await screen.findByText(/rien n’a été enregistré/)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Fichier : Somme des poids ≠ 1.",
      "Ligne 3 : Montant négatif.",
      "Ligne 12 : ISIN invalide.",
    ]);
  });
});
