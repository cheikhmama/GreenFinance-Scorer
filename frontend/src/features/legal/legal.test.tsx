import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { legalRoutes } from "./routes";

function renderRoutes(chemin: string) {
  const router = createMemoryRouter(
    [
      { path: "/login", element: <AuthLayout titreAccessible="Connexion">formulaire</AuthLayout> },
      ...legalRoutes,
    ],
    { initialEntries: [chemin] },
  );
  render(<RouterProvider router={router} />);
}

describe("pages légales", () => {
  it("le pied de page public mène à la politique de confidentialité", async () => {
    renderRoutes("/login");
    await userEvent.click(screen.getByRole("link", { name: "Confidentialité" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Politique de confidentialité" }),
    ).toBeInTheDocument();
    expect(screen.getByText("__Host-access_token")).toBeInTheDocument();
    expect(document.title).toBe("Politique de confidentialité · GreenFinance-Scorer");
  });

  it("mentions légales : informations à fournir signalées, jamais inventées", async () => {
    renderRoutes("/mentions-legales");

    expect(
      await screen.findByRole("heading", { level: 1, name: "Mentions légales" }),
    ).toBeInTheDocument();
    for (const rubrique of ["Éditeur", "Directeur de la publication", "Hébergeur"]) {
      expect(screen.getByRole("heading", { level: 2, name: rubrique })).toBeInTheDocument();
    }
    expect(screen.getAllByText(/À COMPLÉTER/).length).toBeGreaterThan(0);
  });
});
