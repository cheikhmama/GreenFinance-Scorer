import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResetPasswordPage } from "./ResetPasswordPage";

const TOKEN = "a".repeat(43);
const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function CurrentLocation() {
  // <output> porte un rôle ARIA implicite "status" — en collision avec l'alerte role="status"
  // de la page dès que les deux sont montées, ce qui rend findByRole("status") ambigu. <div>
  // n'a pas de rôle implicite.
  const location = useLocation();
  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
    </div>
  );
}

function renderPage(query = `?token=${TOKEN}`) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/reinitialiser-mot-de-passe${query}`]}>
        <ResetPasswordPage />
        <CurrentLocation />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function submitPassword(password = "nouveau-secret", confirmation = password) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nouveau mot de passe", { selector: "input" }), password);
  await user.type(screen.getByLabelText("Confirmer le mot de passe"), confirmation);
  await user.click(screen.getByRole("button", { name: "Enregistrer le mot de passe" }));
}

describe("ResetPasswordPage", () => {
  it.each([
    "",
    "?token=",
    "?token=incomplet",
    `?token=${TOKEN}&token=${TOKEN}`,
    `?token=${"!".repeat(43)}`,
  ])("refuse un lien absent ou mal formé (%s) sans appel API", (query) => {
    renderPage(query);

    expect(screen.getByRole("alert")).toHaveTextContent("absent ou incomplet");
    expect(screen.getByRole("link", { name: "Demander un nouveau lien" })).toHaveAttribute(
      "href",
      "/mot-de-passe-oublie",
    );
    expect(
      screen.queryByLabelText("Nouveau mot de passe", { selector: "input" }),
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["court", "court", "8 caractères minimum"],
    ["nouveau-secret", "autre-secret", "Les deux mots de passe ne correspondent pas."],
    [
      "a".repeat(73),
      "a".repeat(73),
      "Ce mot de passe est trop long. Réduisez le nombre de caractères.",
    ],
    [
      "é".repeat(37),
      "é".repeat(37),
      "Ce mot de passe est trop long. Réduisez le nombre de caractères.",
    ],
  ])(
    "valide le nouveau mot de passe et sa confirmation (%s)",
    async (password, confirmation, message) => {
      renderPage();
      await submitPassword(password, confirmation);

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("transmet le jeton et le nouveau mot de passe puis retire le jeton de l’URL", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    renderPage();
    await submitPassword();

    expect(await screen.findByRole("status")).toHaveTextContent("Mot de passe mis à jour");
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/auth/reinitialiser-mot-de-passe",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: TOKEN, nouveau_mot_de_passe: "nouveau-secret" }),
      }),
    );
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/reinitialiser-mot-de-passe$/);
    expect(screen.getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/login");
    expect(
      screen.queryByLabelText("Nouveau mot de passe", { selector: "input" }),
    ).not.toBeInTheDocument();
  });

  it("propose un nouveau lien après un jeton invalide, expiré ou déjà utilisé", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "jeton_invalide", message: "internal detail", correlation_id: null } },
        { status: 422 },
      ),
    );
    renderPage();
    await submitPassword();

    expect(await screen.findByRole("alert")).toHaveTextContent("a expiré ou a déjà été utilisé");
    expect(screen.getByRole("link", { name: "Demander un nouveau lien" })).toHaveAttribute(
      "href",
      "/mot-de-passe-oublie",
    );
    expect(
      screen.queryByLabelText("Nouveau mot de passe", { selector: "input" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("internal detail")).not.toBeInTheDocument();
  });

  it("empêche les soumissions concurrentes pendant la modification", async () => {
    let resolveRequest: (response: Response) => void = () => {};
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve;
        }),
    );
    renderPage();
    await submitPassword();

    const pendingButton = await screen.findByRole("button", { name: "Modification en cours…" });
    expect(pendingButton).toBeDisabled();
    expect(screen.getByLabelText("Nouveau mot de passe", { selector: "input" })).toBeDisabled();
    expect(screen.getByLabelText("Confirmer le mot de passe")).toBeDisabled();
    await userEvent.click(pendingButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => resolveRequest(new Response(null, { status: 204 })));
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  it.each(["réseau", "serveur", "limitation"])(
    "permet de réessayer après une erreur %s",
    async (failure) => {
      if (failure === "réseau") {
        fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
      } else {
        fetchMock.mockResolvedValue(
          new Response("Error", { status: failure === "limitation" ? 429 : 503 }),
        );
      }
      renderPage();
      await submitPassword();

      expect(await screen.findByRole("alert")).toHaveTextContent(
        failure === "limitation" ? "Veuillez patienter" : "Le mot de passe n’a pas pu être modifié",
      );
      expect(screen.getByRole("button", { name: "Enregistrer le mot de passe" })).toBeEnabled();
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    },
  );
});
