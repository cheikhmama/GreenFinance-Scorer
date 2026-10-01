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

const MANDAT = new File(["%PDF-1.4"], "mandat.pdf", { type: "application/pdf" });

async function remplirEtEnvoyer({ avecMandat = true } = {}) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nom de l’entreprise"), "Minière du Nord");
  await user.type(screen.getByLabelText("Secteur d’activité"), "Mines");
  await user.type(screen.getByLabelText("Pays"), "mr");
  await user.type(screen.getByLabelText("Votre nom"), "Aïcha Ba");
  await user.type(screen.getByLabelText("Votre e-mail professionnel"), "aicha@miniere.mr");
  if (avecMandat) {
    await user.upload(screen.getByLabelText("Lettre de mandat (PDF)"), MANDAT);
  }
  await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
}

describe("CompanyRegistrationPage", () => {
  it("envoie la demande en multipart avec la lettre de mandat, puis annonce l’e-mail", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 202 }));
    renderPage();
    await remplirEtEnvoyer();

    expect(await screen.findByText("Demande envoyée")).toBeInTheDocument();
    expect(screen.getByText(/aicha@miniere\.mr/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/companies/register");
    expect(init?.method).toBe("POST");
    const corps = init?.body as FormData;
    expect(corps).toBeInstanceOf(FormData);
    expect(
      Object.fromEntries([...corps.entries()].filter(([cle]) => cle !== "mandate_letter")),
    ).toEqual({
      company_name: "Minière du Nord",
      sector: "Mines",
      country: "MR",
      contact_name: "Aïcha Ba",
      contact_email: "aicha@miniere.mr",
    });
    // Facultatifs vides : absents du formulaire plutôt qu'envoyés vides.
    expect(corps.has("isin")).toBe(false);
    expect((corps.get("mandate_letter") as File).name).toBe("mandat.pdf");
  });

  it("exige la lettre de mandat avant tout envoi", async () => {
    renderPage();
    await remplirEtEnvoyer({ avecMandat: false });

    expect(await screen.findByText("La lettre de mandat (PDF) est requise.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
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
