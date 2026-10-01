import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyIdentityHeader } from "./CompanyIdentityHeader";

const fetchMock = vi.fn<typeof fetch>();
const LEI = "5493001KJTIIGC8Y1R12";

function profil(surcharges: Record<string, unknown> = {}) {
  return {
    id: "c1",
    name: "Atlas Industries",
    sector: "Industrie manufacturière",
    country: "MR",
    logo: null,
    description: null,
    website: null,
    active: true,
    status: "ACTIVE",
    minimum_investment_amount: null,
    minimum_investment_currency: null,
    published_at: null,
    isin: "MR0001234567",
    lei: LEI,
    ticker: null,
    ...surcharges,
  };
}

function servir(entreprise: object, verification?: object) {
  fetchMock.mockImplementation(async (url) =>
    String(url).endsWith("/lei-verification")
      ? Response.json(verification)
      : Response.json(entreprise),
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderHeader() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <CompanyIdentityHeader />
    </QueryClientProvider>,
  );
}

describe("En-tête de l’espace Entreprise", () => {
  it("affiche le nom, le secteur, le LEI et l’ISIN, et « GLEIF Validé » si la GLEIF confirme", async () => {
    servir(profil(), { lei: LEI, result: "PASSED", detail: "Enregistrement ISSUED." });
    renderHeader();

    expect(await screen.findByRole("heading", { name: "Atlas Industries" })).toBeInTheDocument();
    expect(screen.getByText("Industrie manufacturière")).toBeInTheDocument();
    expect(screen.getByText(LEI)).toBeInTheDocument();
    expect(screen.getByText("MR0001234567")).toBeInTheDocument();
    expect(await screen.findByText("GLEIF Validé")).toBeInTheDocument();
  });

  it("signale un LEI que la GLEIF ne confirme pas, et n’affiche rien si elle ne répond pas", async () => {
    servir(profil(), { lei: LEI, result: "FAILED", detail: "Nom légal différent." });
    const { unmount } = renderHeader();
    expect(await screen.findByText("LEI non confirmé par la GLEIF")).toBeInTheDocument();
    expect(screen.queryByText("GLEIF Validé")).not.toBeInTheDocument();
    unmount();

    servir(profil(), { lei: LEI, result: "NOT_VERIFIABLE", detail: "GLEIF muette." });
    renderHeader();
    await screen.findByRole("heading", { name: "Atlas Industries" });
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/lei-verification"))).toBe(
        true,
      ),
    );
    expect(screen.queryByText("GLEIF Validé")).not.toBeInTheDocument();
    expect(screen.queryByText("LEI non confirmé par la GLEIF")).not.toBeInTheDocument();
  });

  it("sans LEI ni ISIN : ni identifiant inventé, ni appel à la GLEIF", async () => {
    servir(profil({ lei: null, isin: null }));
    renderHeader();

    expect(await screen.findByRole("heading", { name: "Atlas Industries" })).toBeInTheDocument();
    expect(screen.queryByText(/LEI :/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ISIN :/)).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/lei-verification"))).toBe(
      false,
    );
  });
});
