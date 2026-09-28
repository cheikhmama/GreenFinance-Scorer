import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ForgotPasswordPage } from "./ForgotPasswordPage";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function submitEmail(email = "utilisateur@example.com") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("E-mail"), email);
  await user.click(screen.getByRole("button", { name: "Recevoir le lien" }));
}

describe("ForgotPasswordPage", () => {
  it("valide l’adresse avant d’appeler l’API et propose le retour à la connexion", async () => {
    renderPage();
    await submitEmail("adresse-invalide");

    expect(await screen.findByText("Adresse e-mail invalide")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Retour à la connexion" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("envoie l’adresse normalisée et affiche une confirmation sans révéler l’existence du compte", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    renderPage();
    await submitEmail("  utilisateur@example.com  ");

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Si un compte actif correspond à cette adresse",
    );
    expect(screen.getByRole("status")).toHaveTextContent("30 minutes");
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/auth/mot-de-passe-oublie",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "utilisateur@example.com" }),
      }),
    );
    expect(screen.queryByRole("button", { name: "Recevoir le lien" })).not.toBeInTheDocument();
  });

  it("empêche une deuxième soumission pendant l’envoi", async () => {
    let resolveRequest: (response: Response) => void = () => {};
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveRequest = resolve;
        }),
    );
    renderPage();
    await submitEmail();

    const pendingButton = await screen.findByRole("button", { name: "Envoi en cours…" });
    expect(pendingButton).toBeDisabled();
    expect(screen.getByLabelText("E-mail")).toBeDisabled();
    await userEvent.click(pendingButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => resolveRequest(new Response(null, { status: 204 })));
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  it("explique une limitation de débit et permet de réessayer", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { error: { code: "too_many_requests", message: "internal detail", correlation_id: null } },
        { status: 429 },
      ),
    );
    renderPage();
    await submitEmail();

    expect(await screen.findByRole("alert")).toHaveTextContent("Veuillez patienter");
    expect(screen.getByRole("button", { name: "Recevoir le lien" })).toBeEnabled();
    expect(screen.queryByText("internal detail")).not.toBeInTheDocument();
  });

  it.each(["réseau", "serveur"])(
    "signale un échec %s sans afficher de faux succès",
    async (failure) => {
      if (failure === "réseau") {
        fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
      } else {
        fetchMock.mockResolvedValue(new Response("Service unavailable", { status: 503 }));
      }
      renderPage();
      await submitEmail();

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "La demande n’a pas pu être envoyée",
      );
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Recevoir le lien" })).toBeEnabled();
    },
  );
});
