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
      <MemoryRouter initialEntries={["/inscription/entreprise"]}>
        <CompanyRegistrationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MANDAT = new File(["%PDF-1.4"], "mandat.pdf", { type: "application/pdf" });

async function remplirEtEnvoyer({ avecMandat = true, pays = "MR", identifiant = "12345678" } = {}) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nom de l’entreprise"), "Minière du Nord");
  await user.selectOptions(screen.getByLabelText("Secteur d’activité"), "Mines et extraction");
  await user.selectOptions(screen.getByLabelText("Pays"), pays);
  await user.type(
    screen.getByRole("textbox", { name: /NIF|SIREN|EIN|Identifiant fiscal/ }),
    identifiant,
  );
  await user.type(screen.getByLabelText("Nom du responsable"), "Aïcha Ba");
  await user.type(screen.getByLabelText("E-mail professionnel"), "aicha@miniere.mr");
  if (avecMandat) {
    await user.upload(screen.getByLabelText("Lettre de mandat signée (PDF)"), MANDAT);
  }
  await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
  return user;
}

describe("CompanyRegistrationPage", () => {
  it("envoie la demande en multipart, identifiant fiscal compris, puis confirme", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 202 }));
    renderPage();
    await remplirEtEnvoyer();

    expect(await screen.findByText("Demande d’inscription transmise")).toBeInTheDocument();
    expect(
      screen.getByText(/Votre demande d’accès Entreprise a été enregistrée/),
    ).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/companies/register");
    const corps = init?.body as FormData;
    expect(
      Object.fromEntries([...corps.entries()].filter(([cle]) => cle !== "mandate_letter")),
    ).toEqual({
      company_name: "Minière du Nord",
      sector: "Mines et extraction",
      country: "MR",
      tax_id: "12345678",
      contact_name: "Aïcha Ba",
      contact_email: "aicha@miniere.mr",
    });
    // Facultatifs vides : absents du formulaire plutôt qu'envoyés vides.
    expect(corps.has("isin")).toBe(false);
    expect(corps.has("lei")).toBe(false);
    expect((corps.get("mandate_letter") as File).name).toBe("mandat.pdf");
  });

  it("adapte l’identifiant fiscal au pays : NIF, SIREN, EIN", async () => {
    const user = userEvent.setup();
    renderPage();

    for (const [pays, libelle] of [
      ["MR", "NIF"],
      ["FR", "SIREN"],
      ["US", "EIN"],
      ["SN", "Identifiant fiscal"],
    ]) {
      await user.selectOptions(screen.getByLabelText("Pays"), pays);
      expect(screen.getByRole("textbox", { name: libelle })).toBeInTheDocument();
    }
  });

  it("vérifie la forme de l’identifiant fiscal selon le pays avant tout envoi", async () => {
    renderPage();
    await remplirEtEnvoyer({ pays: "FR", identifiant: "732829321" });

    expect(await screen.findByText("Numéro SIREN invalide (clé de contrôle).")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("formulaire épuré : ni ISIN ni LEI visibles, mais repliés en facultatif", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.queryByLabelText("Code ISIN")).not.toBeInTheDocument();
    expect(screen.queryByText(/Présentez votre entreprise/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Télécharger modèle \.docx/ })).toHaveAttribute(
      "href",
      "/modeles/lettre-de-mandat.docx",
    );

    await user.click(screen.getByRole("button", { name: /Identifiants complémentaires/ }));
    expect(screen.getByLabelText("Code ISIN")).toBeInTheDocument();
    expect(screen.getByLabelText("Code LEI (Legal Entity Identifier)")).toBeInTheDocument();
    expect(screen.getByLabelText("Site web officiel")).toBeInTheDocument();
  });

  it("exige la lettre de mandat avant tout envoi", async () => {
    renderPage();
    await remplirEtEnvoyer({ avecMandat: false });

    expect(await screen.findByText("La lettre de mandat (PDF) est requise.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("n’expose pas le champ piège aux lecteurs d’écran", () => {
    renderPage();

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
