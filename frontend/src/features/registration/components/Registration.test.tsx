import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { registrationRoutes } from "../routes";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderAt(chemin: string) {
  const router = createMemoryRouter(registrationRoutes, { initialEntries: [chemin] });
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("Inscription — choix du profil", () => {
  it("propose les trois profils et mène au formulaire de chacun", async () => {
    const user = userEvent.setup();
    renderAt("/inscription");

    const profils = screen.getByRole("navigation", { name: "Profil à inscrire" });
    expect(profils).toHaveTextContent("Entreprise (Émetteur)");
    expect(profils).toHaveTextContent("Investisseur / Analyste");
    expect(profils).toHaveTextContent("Chercheur / Académique");

    await user.click(screen.getByRole("link", { name: /Investisseur \/ Analyste/ }));
    expect(await screen.findByRole("heading", { name: "Accès investisseur" })).toBeInTheDocument();
    expect(screen.getByLabelText("Nom du fonds / Organisation")).toBeInTheDocument();
    expect(screen.getByLabelText("Type d’investisseur")).toBeInTheDocument();
  });

  it("l’ancienne adresse d’inscription mène au formulaire entreprise", async () => {
    renderAt("/inscription-entreprise");

    expect(
      await screen.findByRole("heading", { name: "Inscrire mon entreprise" }),
    ).toBeInTheDocument();
  });
});

describe("Inscription — investisseur et chercheur", () => {
  it("investisseur : envoie la demande puis confirme l’attente de validation", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 202 }));
    const user = userEvent.setup();
    renderAt("/inscription/investisseur");

    await user.type(await screen.findByLabelText("Nom & Prénom"), "Claire Martin");
    await user.type(screen.getByLabelText("E-mail professionnel"), "claire@fonds-sahel.com");
    await user.type(screen.getByLabelText("Nom du fonds / Organisation"), "Fonds Sahel Capital");
    await user.selectOptions(screen.getByLabelText("Type d’investisseur"), "BUSINESS_ANGEL");
    await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));

    expect(await screen.findByText("Demande d’inscription transmise")).toBeInTheDocument();
    expect(screen.getByText(/sous 24h à 48h.*dès validation/)).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/access-requests");
    expect(JSON.parse(init?.body as string)).toEqual({
      role: "INVESTOR",
      full_name: "Claire Martin",
      email: "claire@fonds-sahel.com",
      organization: "Fonds Sahel Capital",
      investor_type: "BUSINESS_ANGEL",
      website_fax: null,
    });
  });

  it("e-mail non configuré côté serveur (503) : message dédié, pas de confirmation", async () => {
    fetchMock.mockResolvedValue(new Response("Error", { status: 503 }));
    const user = userEvent.setup();
    renderAt("/inscription/chercheur");

    await user.type(await screen.findByLabelText("Nom & Prénom"), "Ahmed Salem");
    await user.type(screen.getByLabelText("E-mail institutionnel"), "a.salem@univ-nkc.mr");
    await user.type(
      screen.getByLabelText("Université / Institut de recherche"),
      "Université de Nouakchott",
    );
    await user.selectOptions(
      screen.getByLabelText("Domaine de recherche"),
      screen.getAllByRole("option")[1],
    );
    await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));

    expect(
      await screen.findByText(
        "Le service de notification e-mail est momentanément indisponible. Veuillez réessayer plus tard.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Demande d’inscription transmise")).not.toBeInTheDocument();
  });

  it("chercheur : champs propres au profil, tous requis", async () => {
    const user = userEvent.setup();
    renderAt("/inscription/chercheur");

    expect(await screen.findByLabelText("E-mail institutionnel")).toBeInTheDocument();
    expect(screen.getByLabelText("Université / Institut de recherche")).toBeInTheDocument();
    const domaine = screen.getByLabelText("Domaine de recherche");
    expect(domaine).toHaveTextContent("Empreinte carbone");

    await user.click(screen.getByRole("button", { name: /Envoyer la demande/ }));
    expect(await screen.findByText("Choisissez une option.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
