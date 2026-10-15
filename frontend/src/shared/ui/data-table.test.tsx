import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { celluleCsv, type ColonneTable, DataTable } from "./data-table";

interface Ligne {
  id: string;
  nom: string;
  pays: string;
  score: number | null;
}

const LIGNES: Ligne[] = Array.from({ length: 12 }, (_, i) => ({
  id: `e${i}`,
  nom: `Entreprise ${String(i).padStart(2, "0")}`,
  pays: i % 3 === 0 ? "Mauritanie" : "France",
  score: i === 5 ? null : 50 + i,
}));
LIGNES[0].nom = "Ferrosahel Mining";

const COLONNES: ColonneTable<Ligne>[] = [
  { id: "nom", entete: "Entreprise", masquable: false, valeurTri: (l) => l.nom, cellule: (l) => l.nom },
  { id: "pays", entete: "Pays", valeurTri: (l) => l.pays, cellule: (l) => l.pays },
  {
    id: "score",
    entete: "Score",
    alignement: "droite",
    valeurTri: (l) => l.score,
    cellule: (l) => (l.score === null ? "—" : String(l.score)),
  },
];

beforeEach(() => localStorage.clear());

function rendre(surOuvrir = vi.fn()) {
  render(
    <DataTable
      libelle="Entreprises"
      lignes={LIGNES}
      colonnes={COLONNES}
      cle={(l) => l.id}
      rechercheDans={(l) => `${l.nom} ${l.pays}`}
      filtres={[{ id: "pays", libelle: "Pays", valeur: (l) => l.pays }]}
      triInitial={{ colonne: "nom", sens: "asc" }}
      surOuvrir={surOuvrir}
      libelleLigne={(l) => l.nom}
    />,
  );
  return surOuvrir;
}

const corps = () => screen.getAllByRole("rowgroup")[1];

describe("DataTable", () => {
  it("un seul compteur, en pied : plage sur plusieurs pages, total sur une page", async () => {
    const user = userEvent.setup();
    rendre();
    expect(screen.getByText("Affichage 1–10 sur 12")).toBeInTheDocument();
    expect(within(corps()).getAllByRole("row")).toHaveLength(10);

    await user.click(screen.getByRole("button", { name: "Page suivante" }));
    expect(screen.getByText("Affichage 11–12 sur 12")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: /Par page/ }), "25");
    expect(screen.getByText("12 résultats")).toBeInTheDocument();
  });

  it("recherche sans tenir compte des accents ni de la casse", async () => {
    const user = userEvent.setup();
    rendre();
    await user.type(screen.getByRole("searchbox"), "ferrosahel");
    expect(within(corps()).getAllByRole("row")).toHaveLength(1);
    expect(screen.getByText("1 résultat")).toBeInTheDocument();
  });

  it("filtre à choix multiples, avec réinitialisation", async () => {
    const user = userEvent.setup();
    rendre();
    await user.click(within(screen.getByRole("search")).getByRole("button", { name: /^Pays/ }));
    await user.click(screen.getByRole("checkbox", { name: "Mauritanie" }));
    expect(screen.getByText("4 résultats")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réinitialiser" }));
    expect(screen.getByText("Affichage 1–10 sur 12")).toBeInTheDocument();
  });

  it("trie par colonne, valeurs absentes en dernier, et annonce le sens", async () => {
    const user = userEvent.setup();
    rendre();
    await user.click(screen.getByRole("button", { name: /^Score/ }));
    await user.click(screen.getByRole("button", { name: /^Score/ }));
    expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    const premiere = within(corps()).getAllByRole("row")[0];
    expect(premiere).toHaveTextContent("61");
  });

  it("masque une colonne et ouvre le détail d'une ligne", async () => {
    const user = userEvent.setup();
    const surOuvrir = rendre();
    await user.click(screen.getByRole("button", { name: "Colonnes" }));
    await user.click(screen.getByRole("checkbox", { name: "Pays" }));
    expect(screen.queryByRole("columnheader", { name: /Pays/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Voir le détail de Entreprise 01" }));
    expect(surOuvrir).toHaveBeenCalledWith(expect.objectContaining({ id: "e1" }));
  });

  it("signale une liste tronquée en pied de table", () => {
    render(
      <DataTable
        libelle="Journal"
        lignes={LIGNES}
        colonnes={COLONNES}
        cle={(l) => l.id}
        rechercheDans={(l) => l.nom}
        tronque
      />,
    );
    expect(screen.getByText(/Liste limitée aux 5\s000 premières lignes/)).toBeInTheDocument();
  });

  it("relance la recherche quand une donnée extérieure déclarée change", async () => {
    const user = userEvent.setup();
    const table = (surnoms: Record<string, string>) => (
      <DataTable
        libelle="Entreprises"
        lignes={LIGNES}
        colonnes={COLONNES}
        cle={(l) => l.id}
        rechercheDans={(l) => surnoms[l.id] ?? l.nom}
        dependances={[surnoms]}
      />
    );
    const { rerender } = render(table({}));
    await user.type(screen.getByRole("searchbox"), "zeta");
    expect(screen.getByText("Aucun résultat pour ces critères.")).toBeInTheDocument();
    rerender(table({ e3: "Zeta Corp" }));
    expect(within(corps()).getAllByRole("row")).toHaveLength(1);
  });
});

describe("celluleCsv", () => {
  it("neutralise les formules saisies, pas les nombres", () => {
    expect(celluleCsv('=HYPERLINK("http://x","y")')).toBe(`"'=HYPERLINK(""http://x"",""y"")"`);
    expect(celluleCsv("@SUM(A1)")).toBe("'@SUM(A1)");
    expect(celluleCsv("+33 6 00")).toBe("'+33 6 00");
    expect(celluleCsv("-x")).toBe("'-x");
    expect(celluleCsv(-12.5)).toBe("-12.5");
    expect(celluleCsv(null)).toBe("");
  });

  it("met entre guillemets les séparateurs, guillemets et retours chariot", () => {
    expect(celluleCsv("a;b")).toBe('"a;b"');
    expect(celluleCsv("a\rb")).toBe('"a\rb"');
    expect(celluleCsv("Ferrosahel")).toBe("Ferrosahel");
  });
});
