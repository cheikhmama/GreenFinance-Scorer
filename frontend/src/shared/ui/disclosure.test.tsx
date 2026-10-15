import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileText } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { DisclosureCard } from "./disclosure-card";
import { PhaseProgress } from "./phase-progress";
import { StatusBadge } from "./status-badge";

describe("DisclosureCard", () => {
  it("fermée : le résumé reste visible, le contenu non ; un clic demande l’ouverture", async () => {
    const onOuvertChange = vi.fn();
    const user = userEvent.setup();
    render(
      <DisclosureCard
        id="famille-conseil"
        titre="Conseil"
        resume="2/3 trouvé(s)"
        ouvert={false}
        onOuvertChange={onOuvertChange}
      >
        <p>Taille du conseil</p>
      </DisclosureCard>,
    );
    expect(screen.getByText("2/3 trouvé(s)")).toBeVisible();
    expect(screen.queryByText("Taille du conseil")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Conseil/ }));
    expect(onOuvertChange).toHaveBeenCalledWith(true);
  });

  it("ouverte : contenu et résumé visibles, région nommée par le titre", () => {
    render(
      <DisclosureCard id="f" titre="Conseil" resume="2/3" ouvert onOuvertChange={() => {}}>
        <p>Taille du conseil</p>
      </DisclosureCard>,
    );
    expect(screen.getByRole("region", { name: "Conseil" })).toBeInTheDocument();
    expect(screen.getByText("Taille du conseil")).toBeVisible();
    expect(screen.getByRole("button", { name: /Conseil/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });
});

describe("StatusBadge", () => {
  it("porte le libellé, pas seulement une couleur", () => {
    render(<StatusBadge libelle="Analyse en cours" ton="info" icone={FileText} />);
    expect(screen.getByText("Analyse en cours")).toBeInTheDocument();
  });
});

describe("PhaseProgress", () => {
  it("marque l’étape courante et annonce une branche", () => {
    render(
      <PhaseProgress
        etapes={["Déposé", "Analyse en cours", "En cours d’examen", "Audité"]}
        courante={2}
        branche={{ libelle: "Correction demandée", ton: "attention" }}
      />,
    );
    const liste = screen.getByRole("list", { name: "Progression" });
    expect(liste.querySelector("[aria-current='step']")).toHaveTextContent("En cours d’examen");
    expect(screen.getByText("Correction demandée")).toBeInTheDocument();
  });
});
