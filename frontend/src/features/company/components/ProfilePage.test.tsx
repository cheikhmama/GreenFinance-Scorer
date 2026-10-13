import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("modifie et enregistre description, site officiel et montant minimum (pas secteur ni pays)", async () => {
    fetchMock.mockImplementation(async (url, init) => {
      const chemin = String(url);
      if (chemin.endsWith("/lei-verification")) {
        return Response.json({ lei: LEI, result: "NOT_VERIFIABLE", detail: "" });
      }
      if (chemin.endsWith("/company/profil") && init?.method === "PATCH") {
        return Response.json(
          profil({
            description: "Nouvelle description.",
            website: "https://nouveau-site.test",
            minimum_investment_amount: 1000,
            minimum_investment_currency: "USD",
          }),
        );
      }
      if (chemin.endsWith("/company/profil")) return Response.json(profil());
      return Response.json({ detail: "non authentifié" }, { status: 401 });
    });
    const user = userEvent.setup();
    renderPage();

    const fiche = await screen.findByRole("region", { name: "Fiche entreprise" });
    await user.type(within(fiche).getByLabelText("Description"), "Nouvelle description.");
    await user.type(within(fiche).getByLabelText("Site officiel"), "https://nouveau-site.test");
    await user.click(within(fiche).getByLabelText("Imposer un montant minimum d'investissement"));
    await user.type(within(fiche).getByLabelText("Montant minimum"), "1000");
    await user.click(within(fiche).getByRole("button", { name: "Enregistrer" }));

    const envoi = await vi.waitFor(() =>
      fetchMock.mock.calls.find(
        ([callUrl, callInit]) =>
          String(callUrl).endsWith("/company/profil") && callInit?.method === "PATCH",
      ),
    );
    expect(envoi).toBeDefined();
    const corps = JSON.parse(envoi?.[1]?.body as string);
    expect(corps).toEqual({
      description: "Nouvelle description.",
      website: "https://nouveau-site.test",
      minimum_investment_amount: 1000,
      // Devise non choisie explicitement : repli sur la première de l'énumération (comportement
      // du formulaire, pas une valeur à deviner côté test).
      minimum_investment_currency: expect.any(String),
    });
  });
});
