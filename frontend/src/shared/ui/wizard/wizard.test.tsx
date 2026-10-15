import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { createMemoryRouter, Link, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ConfirmProvider } from "@/shared/ui/confirm-dialog";
import { useConfirmationAbandon, WizardStepper } from ".";

const ETAPES = [
  { id: "exercice", titre: "Exercice" },
  { id: "finances", titre: "Données financières" },
  { id: "document", titre: "Document" },
];

describe("WizardStepper", () => {
  it("marque l’étape courante et annonce la position", () => {
    render(<WizardStepper etapes={ETAPES} courante="finances" />);
    const nav = screen.getByRole("navigation", { name: "Étapes" });
    expect(nav.querySelector("[aria-current='step']")).toHaveTextContent("Données financières");
    expect(nav).toHaveTextContent("Étape 2 sur 3");
  });
});

function Saisie() {
  const sale = useRef(true);
  useConfirmationAbandon(() => sale.current);
  return (
    <>
      <p>Saisie en cours</p>
      <Link to="/ailleurs">Quitter</Link>
    </>
  );
}

function renderAbandon() {
  const router = createMemoryRouter(
    [
      { path: "/saisie", element: <Saisie /> },
      { path: "/ailleurs", element: <p>Ailleurs</p> },
    ],
    { initialEntries: ["/saisie"] },
  );
  render(
    <ConfirmProvider>
      <RouterProvider router={router} />
    </ConfirmProvider>,
  );
  return router;
}

describe("useConfirmationAbandon", () => {
  it("demande confirmation ; « Continuer la saisie » reste sur place", async () => {
    const user = userEvent.setup();
    renderAbandon();
    await user.click(screen.getByRole("link", { name: "Quitter" }));
    await user.click(await screen.findByRole("button", { name: "Continuer la saisie" }));
    expect(screen.getByText("Saisie en cours")).toBeInTheDocument();
  });

  it("« Abandonner » quitte la page", async () => {
    const user = userEvent.setup();
    renderAbandon();
    await user.click(screen.getByRole("link", { name: "Quitter" }));
    await user.click(await screen.findByRole("button", { name: "Abandonner" }));
    expect(await screen.findByText("Ailleurs")).toBeInTheDocument();
  });
});
