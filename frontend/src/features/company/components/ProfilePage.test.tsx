import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePage } from "./ProfilePage";

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
    isin: null,
    lei: LEI,
    ticker: null,
    ...surcharges,
  };
}

function servir(entreprise: object, verification?: object) {
  fetchMock.mockImplementation(async (url) => {
    const chemin = String(url);
    if (chemin.endsWith("/lei-verification")) {
      return Response.json(verification ?? { lei: LEI, result: "NOT_VERIFIABLE", detail: "" });
    }
    if (chemin.endsWith("/company/profil")) return Response.json(entreprise);
    // Compte utilisateur hors du périmètre de ce test : la carte d'identité ne s'affiche pas.
    return Response.json({ detail: "non authentifié" }, { status: 401 });
  });
}

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
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Espace Entreprise — profil", () => {
  it("regroupe secteur, LEI et contrôle GLEIF dans la carte Immatriculations", async () => {
    servir(profil(), { lei: LEI, result: "PASSED", detail: "Enregistrement ISSUED." });
    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: "Profil entreprise" }),
    ).toBeInTheDocument();
    const immatriculations = await screen.findByRole("region", { name: "Immatriculations" });
    expect(immatriculations).toHaveTextContent("SecteurIndustrie manufacturière");
    expect(within(immatriculations).getByText(LEI)).toBeInTheDocument();
    expect(await within(immatriculations).findByText("GLEIF Validé")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Fiche entreprise" })).toHaveTextContent(
      "Non publiée",
    );
  });

  it("sans LEI : ni identifiant inventé, ni appel à la GLEIF", async () => {
    servir(profil({ lei: null }));
    renderPage();

    const immatriculations = await screen.findByRole("region", { name: "Immatriculations" });
    expect(immatriculations).not.toHaveTextContent("LEI");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/lei-verification"))).toBe(
      false,
    );
  });
});
