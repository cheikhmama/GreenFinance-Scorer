import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyRegistrationPage } from "./CompanyRegistrationPage";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/inscription-entreprise"]}>
        <CompanyRegistrationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function remplirEtEnvoyer() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nom de l’entreprise"), "Minière du Nord");
  await user.type(screen.getByLabelText("Secteur d’activité"), "Mines");
  await user.type(screen.getByLabelText("Pays"), "mr");
  await user.type(screen.getByLabelText("Votre nom"), "Aïcha Ba");
  await user.type(screen.getByLabelText("Votre e-mail professionnel"), "aicha@miniere.mr");
  await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
}

describe("CompanyRegistrationPage", () => {
  it("envoie la demande (pays en majuscules, facultatifs à null) puis annonce l’e-mail", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 202 }));
    renderPage();
    await remplirEtEnvoyer();

    expect(await screen.findByText("Demande envoyée")).toBeInTheDocument();
    expect(screen.getByText(/aicha@miniere\.mr/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/companies/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          company_name: "Minière du Nord",
          sector: "Mines",
          country: "MR",
          isin: null,
          lei: null,
          website: null,
          contact_name: "Aïcha Ba",
          contact_email: "aicha@miniere.mr",
          company_fax: null,
        }),
      }),
    );
  });

  it("n’expose pas le champ piège aux lecteurs d’écran", () => {
    renderPage();

    // Les requêtes par rôle suivent l'arbre d'accessibilité (aria-hidden exclu), comme un
    // lecteur d'écran ; le champ existe bien dans le DOM pour les robots.
    expect(screen.queryByRole("textbox", { name: "Fax" })).not.toBeInTheDocument();
    expect(document.querySelector('input[name="company_fax"]')).not.toBeNull();
  });

  it("explique la limite de demandes", async () => {
    fetchMock.mockResolvedValue(new Response("Error", { status: 429 }));
    renderPage();
    await remplirEtEnvoyer();

    expect(await screen.findByRole("alert")).toHaveTextContent("Réessayez dans une heure");
  });
});
