import { describe, expect, it } from "vitest";
import { Role } from "@/features/auth/schemas";
import { roleNavConfig } from "./roleNav";

describe("navigation de l’espace Entreprise (tâche 5.9)", () => {
  it("ne garde que les trois liens de structure, sans action ni carte Profil en double", () => {
    const config = roleNavConfig[Role.ENTERPRISE];

    expect(config.items.map((item) => [item.label, item.to])).toEqual([
      ["Tableau de bord", "/company"],
      ["Mes déclarations", "/company/declarations"],
      ["Profil entreprise", "/company/profile"],
    ]);
    expect(config.profilDansNavigation).toBe(true);
  });
});
