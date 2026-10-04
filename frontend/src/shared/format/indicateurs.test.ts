import { describe, expect, it } from "vitest";
import { formatScore, uneDecimale } from "./etatPosition";
import { formatValeur, libelleIndicateur, libelleScope, listeIndicateurs } from "./indicateurs";
import { libelleRole } from "./role";

describe("libellés lisibles, jamais le code technique", () => {
  it("nomme les indicateurs et la méthode du Scope 2", () => {
    expect(libelleIndicateur("taille_conseil")).toBe("Taille du conseil");
    expect(listeIndicateurs(["scope_2", "effectif_total"])).toBe(
      "Émissions Scope 2, Effectif total",
    );
    expect(libelleScope(2, "location_based")).toBe("Scope 2 (méthode localisation)");
    expect(libelleScope(1, null)).toBe("Scope 1");
  });

  it("écrit les nombres à la française", () => {
    expect(formatValeur(0, "count")).toBe("0");
    expect(formatValeur(0.312, "tCO2e/MWh")).toBe("0,312 tCO2e/MWh");
    expect(uneDecimale(66.7)).toBe("66,7");
    expect(formatScore(70)).toBe("70,0/100");
  });

  it("nomme les rôles", () => {
    expect(libelleRole("AUDITOR")).toBe("Auditeur");
  });
});
