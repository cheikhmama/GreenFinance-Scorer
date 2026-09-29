import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EntrepriseAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyIdentifiersCard } from "./CompanyIdentifiersCard";

const ID = "33333333-3333-3333-3333-333333333333";
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

const entreprise = {
  id: ID,
  nom: "Minière du Nord",
  isin: "FR0000120271",
  lei: null,
  ticker: "MDN",
} as EntrepriseAdmin;

function renderCard() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}
    >
      <CompanyIdentifiersCard entreprise={entreprise} />
    </QueryClientProvider>,
  );
}

describe("CompanyIdentifiersCard", () => {
  it("n’envoie que les champs modifiés, un champ vidé valant null", async () => {
    fetchMock.mockResolvedValue(
      Response.json({
        company_id: ID,
        isin: "FR0000120271",
        lei: "HWUPKR0MPOU8FGXBT394",
        ticker: null,
      }),
    );
    const user = userEvent.setup();
    renderCard();

    const bouton = screen.getByRole("button", { name: "Enregistrer les identifiants" });
    expect(bouton).toBeDisabled();
    await user.type(screen.getByLabelText("LEI"), "HWUPKR0MPOU8FGXBT394");
    await user.clear(screen.getByLabelText("Ticker"));
    await user.click(bouton);

    expect(await screen.findByText("Identifiants enregistrés.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/admin/companies/${ID}/identifiers`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ lei: "HWUPKR0MPOU8FGXBT394", ticker: null }),
      }),
    );
  });

  it("signale un identifiant déjà attribué", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "identifiant_deja_utilise", message: "Conflit.", correlation_id: null } },
        { status: 422 },
      ),
    );
    const user = userEvent.setup();
    renderCard();

    await user.clear(screen.getByLabelText("ISIN"));
    await user.type(screen.getByLabelText("ISIN"), "US0378331005");
    await user.click(screen.getByRole("button", { name: "Enregistrer les identifiants" }));

    expect(await screen.findByText(/déjà attribué à une autre entreprise/)).toBeInTheDocument();
  });
});
