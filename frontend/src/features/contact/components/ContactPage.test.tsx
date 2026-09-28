import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ContactPage } from "./ContactPage";

const fetchMock = vi.fn<typeof fetch>();
const message = "Bonjour, je souhaite obtenir de l’aide pour accéder à mon espace.";

function renderContactPage() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ContactPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return userEvent.setup();
}

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Nom complet"), "  Amina Diallo  ");
  await user.type(screen.getByLabelText("Adresse e-mail"), "amina@example.com");
  await user.type(screen.getByLabelText("Sujet"), "  Accès à mon espace  ");
  await user.type(screen.getByLabelText("Votre message"), `  ${message}  `);
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ContactPage", () => {
  it("signale chaque champ invalide et empêche l’envoi d’un formulaire vide", async () => {
    const user = renderContactPage();
    await user.click(screen.getByRole("button", { name: "Envoyer le message" }));

    expect(await screen.findByText("Indiquez votre nom (2 caractères minimum).")).toBeVisible();
    expect(screen.getByText("Indiquez une adresse e-mail valide.")).toBeVisible();
    expect(
      screen.getByText("Précisez le sujet de votre demande (3 caractères minimum)."),
    ).toBeVisible();
    expect(screen.getByText("Décrivez votre demande en au moins 20 caractères.")).toBeVisible();
    expect(screen.getByLabelText("Nom complet")).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("envoie les champs nettoyés et confirme uniquement après la réponse du serveur", async () => {
    let resolveRequest: ((response: Response) => void) | undefined;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const user = renderContactPage();
    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Envoyer le message" }));

    expect(await screen.findByRole("button", { name: "Envoi en cours…" })).toBeDisabled();
    expect(screen.getByLabelText("Votre message")).toBeDisabled();
    expect(screen.queryByText("Votre message a été envoyé")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/contact",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          nom: "Amina Diallo",
          email: "amina@example.com",
          sujet: "Accès à mon espace",
          message,
        }),
      }),
    );
    await user.click(screen.getByRole("button", { name: "Envoi en cours…" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => resolveRequest?.(new Response(null, { status: 204 })));

    expect(await screen.findByRole("status")).toHaveTextContent("Votre message a été envoyé");
    expect(screen.getByRole("status")).toHaveTextContent("amina@example.com");
    expect(screen.queryByLabelText("Votre message")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Envoyer un autre message" }));
    expect(screen.getByLabelText("Votre message")).toHaveValue("");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it.each([
    { status: 429, text: "Patientez quelques minutes" },
    { status: 503, text: "Votre message n’a pas été envoyé" },
  ])(
    "conserve la demande après une erreur HTTP $status et permet de réessayer",
    async ({ status, text }) => {
      fetchMock.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "contact_unavailable",
              message: "Détail technique",
              correlation_id: null,
            },
          }),
          { status, headers: { "Content-Type": "application/json" } },
        ),
      );
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
      const user = renderContactPage();
      await fillForm(user);
      await user.click(screen.getByRole("button", { name: "Envoyer le message" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(text);
      expect(screen.getByLabelText("Votre message")).toHaveValue(`  ${message}  `);
      expect(screen.getByLabelText("Adresse e-mail")).toHaveValue("amina@example.com");
      expect(screen.getByRole("button", { name: "Envoyer le message" })).toBeEnabled();
      expect(screen.queryByText("Votre message a été envoyé")).not.toBeInTheDocument();
      expect(screen.queryByText("Détail technique")).not.toBeInTheDocument();
      expect(fetchMock).toHaveBeenCalledTimes(1);

      await user.click(screen.getByRole("button", { name: "Envoyer le message" }));
      expect(await screen.findByRole("status")).toHaveTextContent("Votre message a été envoyé");
      expect(fetchMock).toHaveBeenCalledTimes(2);
    },
  );

  it("explique un échec réseau sans afficher de fausse confirmation", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const user = renderContactPage();
    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Envoyer le message" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("L’envoi n’a pas pu être confirmé");
    expect(screen.getByLabelText("Votre message")).toHaveValue(`  ${message}  `);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("donne accès à la récupération du mot de passe et à la connexion", () => {
    renderContactPage();

    expect(screen.getByRole("link", { name: "Réinitialiser mon accès" })).toHaveAttribute(
      "href",
      "/mot-de-passe-oublie",
    );
    expect(screen.getByRole("link", { name: "Retour à la connexion" })).toHaveAttribute(
      "href",
      "/login",
    );
  });
});
