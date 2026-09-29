import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyFinancialsCard } from "./CompanyFinancialsCard";

const ID = "55555555-5555-5555-5555-555555555555";
const fetchMock = vi.fn<typeof fetch>();
const VIDE = {
  company_id: ID,
  revenue: null,
  revenue_currency: null,
  enterprise_value: null,
  enterprise_value_currency: null,
  enterprise_value_as_of: null,
};

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderCard() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <CompanyFinancialsCard entrepriseId={ID} />
    </QueryClientProvider>,
  );
}

describe("CompanyFinancialsCard", () => {
  it("envoie le remplacement complet, la devise seulement avec son montant", async () => {
    fetchMock
      .mockResolvedValueOnce(Response.json(VIDE))
      .mockResolvedValueOnce(
        Response.json({ ...VIDE, enterprise_value: 1000000.5, enterprise_value_currency: "EUR" }),
      );
    const user = userEvent.setup();
    renderCard();

    await user.type(await screen.findByLabelText("EVIC"), "1000000.5");
    await user.selectOptions(screen.getByLabelText("Devise de l’EVIC"), "EUR");
    await user.click(screen.getByRole("button", { name: "Enregistrer les données financières" }));

    expect(await screen.findByText("Données financières enregistrées.")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe(`/api/v1/admin/companies/${ID}/financials`);
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string)).toEqual({
      revenue: null,
      revenue_currency: null,
      enterprise_value: 1000000.5,
      enterprise_value_currency: "EUR",
      enterprise_value_as_of: null,
    });
  });

  it("refuse plus de deux décimales et une date sans EVIC, sans appeler le serveur", async () => {
    fetchMock.mockResolvedValueOnce(Response.json(VIDE));
    const user = userEvent.setup();
    renderCard();

    await user.type(await screen.findByLabelText("Chiffre d’affaires"), "10.005");
    await user.type(screen.getByLabelText("Date de l’EVIC"), "2025-12-31");
    await user.click(screen.getByRole("button", { name: "Enregistrer les données financières" }));

    expect(screen.getByText("Au plus deux décimales.")).toBeInTheDocument();
    expect(screen.getByText("Renseignez l'EVIC avec sa date.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
