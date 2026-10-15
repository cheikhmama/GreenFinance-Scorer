import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyRegistrationPage, etapeDeLErreur } from "./CompanyRegistrationPage";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Sans délai entre frappes : les tests ne portent pas sur le rythme de saisie. */
function utilisateur() {
  return userEvent.setup({ delay: null });
}

type Utilisateur = ReturnType<typeof utilisateur>;

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/inscription/entreprise"]}>
        <CompanyRegistrationPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const NOMS_PAYS: Record<string, string> = { MR: "Mauritanie", FR: "France", US: "États-Unis" };

/** Ouvre la liste avec recherche, tape la recherche, puis choisit l'option. */
async function choisir(user: Utilisateur, champ: string, recherche: string, option: string) {
  await user.click(screen.getByRole("combobox", { name: champ }));
  const recherche_ = await screen.findByPlaceholderText(/Rechercher/, {}, { timeout: 5000 });
  await user.type(recherche_, recherche);
  await user.click(await screen.findByRole("option", { name: option }, { timeout: 5000 }));
}

const MANDAT = new File(["%PDF-1.4"], "mandat.pdf", { type: "application/pdf" });

async function remplirEtape1(user: Utilisateur, { pays = "MR", identifiant = "12345678" } = {}) {
  await user.type(screen.getByLabelText("Nom de l’entreprise"), "Minière du Nord");
  await choisir(user, "Secteur d’activité", "mines", "Mines et extraction");
  await choisir(user, "Pays", NOMS_PAYS[pays], NOMS_PAYS[pays]);
  await user.type(
    screen.getByRole("textbox", { name: /NIF|SIREN|EIN|Identifiant fiscal/ }),
    identifiant,
  );
  await user.click(screen.getByRole("button", { name: "Suivant" }));
}

/** Étape 1 remplie et validée : attend l'étape Contact (la validation de « Suivant » est asynchrone). */
async function allerAEtape2(user: Utilisateur, options: Parameters<typeof remplirEtape1>[1] = {}) {
  await remplirEtape1(user, options);
  await screen.findByLabelText("Nom & Prénom du responsable");
}

/** Étapes 1 et 2 remplies et validées : attend l'étape Identifiants. */
async function allerAEtape3(user: Utilisateur, options: { avecMandat?: boolean } = {}) {
  await allerAEtape2(user);
  await remplirEtape2(user, options);
  await screen.findByLabelText("Code ISIN");
}

async function remplirEtape2(user: Utilisateur, { avecMandat = true } = {}) {
  await user.type(await screen.findByLabelText("Nom & Prénom du responsable"), "Aïcha Ba");
  await user.type(screen.getByLabelText("E-mail professionnel"), "aicha@miniere.mr");
  if (avecMandat) {
    await user.upload(screen.getByLabelText("Lettre de mandat signée (PDF)"), MANDAT);
  }
  await user.click(screen.getByRole("button", { name: "Suivant" }));
}

/** Parcourt les trois étapes jusqu'au clic sur « Envoyer la demande ». Les tests qui attendent un
 * blocage en cours de route pilotent eux-mêmes les étapes (remplirEtape1/2). */
async function remplirEtEnvoyer() {
  const user = utilisateur();
  await allerAEtape3(user);
  await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
  return user;
}

describe("CompanyRegistrationPage", () => {
  it("envoie la demande, fait confirmer l’adresse par le code reçu, puis confirme", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith("/verify-email")
        ? new Response(null, { status: 204 })
        : new Response(null, { status: 202 }),
    );
    renderPage();
    const user = await remplirEtEnvoyer();

    // Étape du code (tâche 5.11) : la demande n'est pas encore transmise.
    expect(await screen.findByText(/Un code à 6 chiffres a été envoyé à/)).toHaveTextContent(
      "aicha@miniere.mr",
    );
    expect(screen.queryByText("Demande d’inscription transmise")).not.toBeInTheDocument();
    const verifier = screen.getByRole("button", { name: /Vérifier et transmettre/ });
    expect(verifier).toBeDisabled();
    await user.type(screen.getByLabelText("Code de vérification"), "12a3456");
    expect(screen.getByLabelText("Code de vérification")).toHaveValue("123456");
    await user.click(verifier);

    expect(await screen.findByText("Demande d’inscription transmise")).toBeInTheDocument();
    expect(screen.getByText(/sous 24h à 48h.*dès validation/)).toBeInTheDocument();
    const verification = fetchMock.mock.calls.find(([u]) => String(u).endsWith("/verify-email"));
    expect(JSON.parse(verification?.[1]?.body as string)).toEqual({
      email: "aicha@miniere.mr",
      code: "123456",
    });
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
    const user = utilisateur();
    renderPage();

    for (const [recherche, pays, libelle] of [
      ["Mau", "Mauritanie", "NIF"],
      ["fra", "France", "SIREN"],
      ["etats", "États-Unis", "EIN"],
      ["sene", "Sénégal", "Identifiant fiscal"],
    ]) {
      await choisir(user, "Pays", recherche, pays);
      expect(screen.getByRole("combobox", { name: "Pays" })).toHaveTextContent(pays);
      expect(screen.getByRole("textbox", { name: libelle })).toBeInTheDocument();
    }
  });

  it("recherche sans tenir compte des accents ni de la casse, code ISO compris", async () => {
    const user = utilisateur();
    renderPage();

    await user.click(screen.getByRole("combobox", { name: "Secteur d’activité" }));
    await user.type(await screen.findByPlaceholderText("Rechercher un secteur…"), "ENERGIE");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Énergie"]);
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("combobox", { name: "Pays" }));
    await user.type(await screen.findByPlaceholderText("Rechercher un pays…"), "ci");
    expect(screen.getByRole("option", { name: "Côte d’Ivoire" })).toBeInTheDocument();
    await user.clear(screen.getByPlaceholderText("Rechercher un pays…"));
    await user.type(screen.getByPlaceholderText("Rechercher un pays…"), "zzz");
    expect(screen.getByText("Aucun pays ne correspond.")).toBeInTheDocument();
  });

  it("vérifie la forme de l’identifiant fiscal selon le pays avant tout envoi", async () => {
    renderPage();
    const user = utilisateur();
    await allerAEtape2(user, { pays: "FR", identifiant: "732829321" });
    await remplirEtape2(user);
    await screen.findByLabelText("Code ISIN");
    await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));

    expect(await screen.findByText("Numéro SIREN invalide (clé de contrôle).")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ISIN, LEI et site web sur l’étape 3, marqués facultatifs", async () => {
    const user = utilisateur();
    renderPage();

    expect(screen.queryByLabelText("Code ISIN")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Site web officiel")).not.toBeInTheDocument();
    expect(screen.queryByText(/Présentez votre entreprise/)).not.toBeInTheDocument();

    await allerAEtape2(user);
    expect(screen.getByRole("link", { name: /Télécharger modèle \.docx/ })).toHaveAttribute(
      "href",
      "/modeles/lettre-de-mandat.docx",
    );
    await remplirEtape2(user);

    expect(await screen.findByLabelText("Code ISIN")).toBeInTheDocument();
    expect(screen.getByLabelText("Code LEI (Legal Entity Identifier)")).toBeInTheDocument();
    expect(screen.getByLabelText("Site web officiel")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent(
      "Identifiants (facultatifs)",
    );
  });

  it("trois étapes ; « Suivant » ne vérifie que l’étape affichée", async () => {
    const user = utilisateur();
    renderPage();
    expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent("Étape 1 sur 3");
    await user.click(screen.getByRole("button", { name: "Suivant" }));
    expect(await screen.findByText("Le nom de l’entreprise est requis.")).toBeInTheDocument();
    expect(screen.queryByText("Votre nom est requis.")).not.toBeInTheDocument();
  });

  it("changer d’étape met le focus sur le titre de la nouvelle étape", async () => {
    const user = utilisateur();
    renderPage();
    await allerAEtape2(user);
    expect(screen.getByRole("heading", { name: "Étape 2 sur 3 : Contact & mandat" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Précédent" }));
    expect(screen.getByRole("heading", { name: "Étape 1 sur 3 : Entreprise" })).toHaveFocus();
  });

  it("exige la lettre de mandat avant tout envoi", async () => {
    renderPage();
    const user = utilisateur();
    await allerAEtape2(user);
    await remplirEtape2(user, { avecMandat: false });

    expect(await screen.findByText("La lettre de mandat (PDF) est requise.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Code ISIN")).not.toBeInTheDocument();
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

  it("refuse une messagerie grand public dès la saisie", async () => {
    const user = utilisateur();
    renderPage();
    await allerAEtape2(user);

    await user.type(screen.getByLabelText("E-mail professionnel"), "aicha@gmail.com");
    await user.click(screen.getByRole("button", { name: "Suivant" }));

    expect(
      await screen.findByText(
        "Utilisez votre adresse e-mail professionnelle (pas une messagerie grand public).",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("erreur d’adresse trouvée à l’envoi : retour à l’étape Contact avec le message (Review Focus 4)", async () => {
    const user = utilisateur();
    renderPage();
    await allerAEtape3(user);
    await user.type(screen.getByLabelText("Site web officiel"), "https://www.autre-groupe.mr");
    await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));

    expect(await screen.findByLabelText("E-mail professionnel")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent("Étape 2 sur 3");
    expect(
      await screen.findByText(
        "L'adresse doit appartenir au domaine du site web (autre-groupe.mr).",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("conserve les valeurs en changeant d’étape et les envoie à l’étape 3", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 202 }));
    const user = utilisateur();
    renderPage();
    await allerAEtape3(user);
    await user.click(screen.getByRole("button", { name: "Précédent" }));
    await screen.findByLabelText("Nom & Prénom du responsable");
    await user.click(screen.getByRole("button", { name: "Précédent" }));
    await screen.findByLabelText("Nom de l’entreprise");

    expect(screen.getByLabelText("Nom de l’entreprise")).toHaveValue("Minière du Nord");
    expect(screen.getByRole("combobox", { name: "Pays" })).toHaveTextContent("Mauritanie");
    expect(screen.getByRole("textbox", { name: "NIF" })).toHaveValue("12345678");

    await user.click(screen.getByRole("button", { name: "Suivant" }));
    expect(await screen.findByLabelText("Nom & Prénom du responsable")).toHaveValue("Aïcha Ba");
    expect(screen.getByLabelText("E-mail professionnel")).toHaveValue("aicha@miniere.mr");
    expect(screen.getByText("mandat.pdf")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Suivant" }));
    await user.click(await screen.findByRole("button", { name: /Envoyer la demande/ }));
    await screen.findByText(/Un code à 6 chiffres a été envoyé à/);
    const corps = fetchMock.mock.calls[0][1]?.body as FormData;
    expect(corps.get("company_name")).toBe("Minière du Nord");
    expect(corps.get("contact_email")).toBe("aicha@miniere.mr");
    expect((corps.get("mandate_letter") as File).name).toBe("mandat.pdf");
  });

  it.each([
    ["Code ISIN", "XX", "Un ISIN compte 12 caractères (ex. MR…)."],
    ["Code LEI (Legal Entity Identifier)", "123", "Un LEI compte 20 caractères."],
  ])(
    "%s invalide à l’envoi : reste à l’étape 3 avec le message",
    async (champ, saisie, message) => {
      const user = utilisateur();
      renderPage();
      await allerAEtape3(user);
      await user.type(screen.getByLabelText(champ), saisie);
      await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(screen.getByRole("navigation", { name: "Étapes" })).toHaveTextContent("Étape 3 sur 3");
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("etapeDeLErreur désigne l’étape du premier champ en erreur", () => {
    // Aucun chemin réaliste par l’interface : « Suivant » valide l’étape 1 avant de la quitter.
    expect(etapeDeLErreur({ tax_id: {}, contact_email: {} })).toBe("entreprise");
    expect(etapeDeLErreur({ website: {}, mandate_letter: {} })).toBe("contact");
    expect(etapeDeLErreur({ lei: {} })).toBe("identifiants");
    expect(etapeDeLErreur({})).toBeNull();
  });

  it("signale un code faux et permet d’en redemander un après le délai", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock.mockImplementation(async (url) => {
      if (String(url).endsWith("/verify-email")) {
        return Response.json(
          { error: { code: "code_invalide", message: "Code invalide", correlation_id: null } },
          { status: 422 },
        );
      }
      return new Response(null, { status: 202 });
    });
    renderPage();
    const user = await remplirEtEnvoyer();
    const renvoyer = await screen.findByRole("button", { name: /Renvoyer le code \(60 s\)/ });
    expect(renvoyer).toBeDisabled();

    await user.type(screen.getByLabelText("Code de vérification"), "000000");
    await user.click(screen.getByRole("button", { name: /Vérifier et transmettre/ }));
    expect(await screen.findByText(/Code invalide ou expiré/)).toBeInTheDocument();

    for (let seconde = 0; seconde < 61; seconde += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
    }
    await user.click(await screen.findByRole("button", { name: "Renvoyer le code" }));
    expect(await screen.findByText(/un nouveau code vient d’être envoyé/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith("/resend-code"))).toBe(true);
  });
});
