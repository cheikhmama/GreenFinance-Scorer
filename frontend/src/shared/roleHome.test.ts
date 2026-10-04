import { describe, expect, it } from "vitest";
import { cheminAutorisePour } from "./roleHome";

describe("page rouverte après connexion", () => {
  it("rouvre une page de l’espace du compte qui se connecte", () => {
    expect(cheminAutorisePour("RESEARCHER", "/researcher/analyses?statut=SOUMISE")).toBe(true);
    expect(cheminAutorisePour("ADMIN", "/admin")).toBe(true);
  });

  it("ne rouvre jamais la page d’un autre espace (changement de compte)", () => {
    expect(cheminAutorisePour("RESEARCHER", "/admin/rapports")).toBe(false);
    // « /audit » n'est pas un préfixe de « /admin », ni l'inverse.
    expect(cheminAutorisePour("AUDITOR", "/admin")).toBe(false);
    expect(cheminAutorisePour("ADMIN", "/audit/historique")).toBe(false);
  });

  it("laisse passer une page hors de tout espace", () => {
    expect(cheminAutorisePour("INVESTOR", "/contact")).toBe(true);
  });
});
