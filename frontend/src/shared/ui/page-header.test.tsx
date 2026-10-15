import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { PageHeader } from "./page-header";

describe("titre de l’onglet (WCAG 2.4.2)", () => {
  it("PageHeader : reprend le texte rendu du h1, même quand le titre est un nœud", () => {
    const { rerender } = render(<PageHeader title="Tableau de bord" />);
    expect(document.title).toBe("Tableau de bord · GreenFinance-Scorer");

    rerender(
      <PageHeader
        title={
          <>
            Atlas <span>Énergie</span>
          </>
        }
      />,
    );
    expect(document.title).toBe("Atlas Énergie · GreenFinance-Scorer");
  });

  it("AuthLayout sans titre visible : h1 pour lecteurs d’écran et titre d’onglet", () => {
    const { getByRole } = render(
      <MemoryRouter>
        <AuthLayout titreAccessible="Connexion">formulaire</AuthLayout>
      </MemoryRouter>,
    );
    expect(getByRole("heading", { level: 1, name: "Connexion" })).toHaveClass("sr-only");
    expect(document.title).toBe("Connexion · GreenFinance-Scorer");
  });
});
