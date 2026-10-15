import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Label } from "@/shared/ui/label";
import { EntrepriseCombobox } from "./EntrepriseCombobox";

const recherches: string[] = [];

vi.mock("../api", () => ({
  usePublishedCompanies: ({ recherche }: { recherche: string }) => {
    recherches.push(recherche);
    const toutes = [
      { id: "e1", name: "Atlas Énergie", sector: "Énergie", logo: null },
      { id: "e2", name: "Nordwind", sector: "Industrie", logo: null },
    ];
    return {
      data: {
        pages: [
          { items: toutes.filter((e) => e.name.toLowerCase().includes(recherche.toLowerCase())) },
        ],
      },
    };
  },
}));

vi.mock("@/shared/hooks/useDebouncedValue", () => ({
  useDebouncedValue: (valeur: string) => valeur,
}));

function renderChamp(onSelect = vi.fn()) {
  render(
    <>
      <Label htmlFor="entreprise">Entreprise publiée</Label>
      <EntrepriseCombobox id="entreprise" onSelect={onSelect} />
    </>,
  );
  return onSelect;
}

describe("EntrepriseCombobox", () => {
  it("porte le libellé du champ (id transmis par FormControl)", () => {
    renderChamp();
    expect(screen.getByRole("combobox", { name: "Entreprise publiée" })).toBeInTheDocument();
  });

  it("se pilote entièrement au clavier : ouvrir, taper, flèche, Entrée", async () => {
    const user = userEvent.setup();
    const onSelect = renderChamp();
    const declencheur = screen.getByRole("combobox", { name: "Entreprise publiée" });

    declencheur.focus();
    await user.keyboard("{Enter}");
    await user.keyboard("nord");
    expect(recherches.at(-1)).toBe("nord");
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "e2" }));
    expect(declencheur).toHaveTextContent("Nordwind");
    expect(declencheur).toHaveAttribute("aria-expanded", "false");
  });

  it("Échap referme la liste sans rien sélectionner", async () => {
    const user = userEvent.setup();
    const onSelect = renderChamp();
    await user.click(screen.getByRole("combobox", { name: "Entreprise publiée" }));
    expect(screen.getByRole("option", { name: /Atlas Énergie/ })).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
