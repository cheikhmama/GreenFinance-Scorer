import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Breadcrumbs } from "./Breadcrumbs";
import type { HandleRoute } from "./handle";

function renderA(chemin: string) {
  const router = createMemoryRouter(
    [
      {
        element: (
          <>
            <Breadcrumbs />
            <Outlet />
          </>
        ),
        children: [
          {
            path: "/company",
            handle: { fil: "Tableau de bord" } satisfies HandleRoute,
            children: [
              { index: true, element: <p>accueil</p> },
              {
                path: "declarations",
                handle: { fil: "Mes déclarations" } satisfies HandleRoute,
                children: [
                  { index: true, element: <p>liste</p> },
                  {
                    path: ":rapportId",
                    handle: { fil: (p) => `Déclaration ${p.rapportId}` } satisfies HandleRoute,
                    element: <p>détail</p>,
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
    { initialEntries: [chemin] },
  );
  render(<RouterProvider router={router} />);
}

describe("Breadcrumbs", () => {
  it("construit le fil depuis les routes, la dernière étape sans lien", async () => {
    renderA("/company/declarations/fy2025");
    const fil = await screen.findByRole("navigation", { name: "Fil d’Ariane" });
    const liste = within(fil).getByRole("list");
    expect(within(liste).getByRole("link", { name: "Tableau de bord" })).toHaveAttribute(
      "href",
      "/company",
    );
    expect(within(liste).getByRole("link", { name: "Mes déclarations" })).toHaveAttribute(
      "href",
      "/company/declarations",
    );
    expect(within(liste).getByText("Déclaration fy2025")).toHaveAttribute("aria-current", "page");
    // Au téléphone : un seul lien, vers le parent.
    expect(within(fil).getByRole("link", { name: /Retour à Mes déclarations/ })).toHaveAttribute(
      "href",
      "/company/declarations",
    );
  });

  it("aucun fil sur une page de premier niveau", async () => {
    renderA("/company");
    await screen.findByText("accueil");
    expect(screen.queryByRole("navigation", { name: "Fil d’Ariane" })).not.toBeInTheDocument();
  });
});
