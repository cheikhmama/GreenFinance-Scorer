import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderCompany } from "../test/renderCompany";

const NOTIFICATIONS = { items: [], total: 0, page: 1, page_size: 1, pages: 1 };
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
    if (chemin.includes("/notifications")) return Response.json(NOTIFICATIONS);
    // Compte utilisateur hors du périmètre de ce test : la carte d'identité ne s'affiche pas.
    return Response.json({ detail: "non authentifié" }, { status: 401 });
  });
}

function servirEnregistrement() {
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
    if (chemin.includes("/notifications")) return Response.json(NOTIFICATIONS);
    return Response.json({ detail: "non authentifié" }, { status: 401 });
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

describe("Espace Entreprise — profil", () => {
  it("regroupe secteur, LEI et contrôle GLEIF dans la carte Immatriculations", async () => {
    servir(profil(), { lei: LEI, result: "PASSED", detail: "Enregistrement ISSUED." });
    renderCompany("/company/profile");

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
    renderCompany("/company/profile");

    const immatriculations = await screen.findByRole("region", { name: "Immatriculations" });
    expect(immatriculations).not.toHaveTextContent("LEI");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/lei-verification"))).toBe(
      false,
    );
  });

  it("modifie et enregistre description, site officiel et montant minimum (pas secteur ni pays)", async () => {
    servirEnregistrement();
    const user = userEvent.setup();
    const { router } = renderCompany("/company/profile/fiche-publique");

    const tiroir = await screen.findByRole("dialog", { name: "Modifier la fiche publique" });
    await user.type(within(tiroir).getByLabelText("Description"), "Nouvelle description.");
    await user.type(within(tiroir).getByLabelText("Site officiel"), "https://nouveau-site.test");
    await user.click(within(tiroir).getByLabelText("Imposer un montant minimum d'investissement"));
    await user.type(within(tiroir).getByLabelText("Montant minimum"), "1000");
    await user.click(within(tiroir).getByRole("button", { name: "Enregistrer" }));

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
    await vi.waitFor(() => expect(router.state.location.pathname).toBe("/company/profile"));
  });

  it("option décochée : le PATCH envoie null pour le montant et la devise", async () => {
    servirEnregistrement();
    const user = userEvent.setup();
    renderCompany("/company/profile/fiche-publique");

    const tiroir = await screen.findByRole("dialog", { name: "Modifier la fiche publique" });
    await user.type(within(tiroir).getByLabelText("Description"), "Texte.");
    await user.click(within(tiroir).getByRole("button", { name: "Enregistrer" }));

    const envoi = await vi.waitFor(() => {
      const appel = fetchMock.mock.calls.find(
        ([callUrl, callInit]) =>
          String(callUrl).endsWith("/company/profil") && callInit?.method === "PATCH",
      );
      expect(appel).toBeDefined();
      return appel;
    });
    expect(JSON.parse(envoi?.[1]?.body as string)).toMatchObject({
      minimum_investment_amount: null,
      minimum_investment_currency: null,
    });
  });

  it("la fiche se lit en résumé ; « Modifier » ouvre le tiroir routé", async () => {
    servir(profil());
    const user = userEvent.setup();
    const { router } = renderCompany("/company/profile");
    const fiche = await screen.findByRole("region", { name: "Fiche entreprise" });
    expect(within(fiche).queryByRole("textbox")).not.toBeInTheDocument();
    await user.click(within(fiche).getByRole("link", { name: "Modifier" }));
    expect(router.state.location.pathname).toBe("/company/profile/fiche-publique");
    expect(
      await screen.findByRole("dialog", { name: "Modifier la fiche publique" }),
    ).toBeInTheDocument();
  });

  it("le montant minimum n’apparaît qu’une fois l’option cochée", async () => {
    servir(profil());
    const user = userEvent.setup();
    renderCompany("/company/profile/fiche-publique");
    const tiroir = await screen.findByRole("dialog", { name: "Modifier la fiche publique" });
    expect(within(tiroir).queryByLabelText(/Montant minimum/)).not.toBeInTheDocument();
    await user.click(within(tiroir).getByLabelText("Imposer un montant minimum d'investissement"));
    expect(within(tiroir).getByLabelText(/Montant minimum/)).toBeInTheDocument();
  });
});
