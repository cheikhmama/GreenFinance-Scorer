import { describe, expect, it } from "vitest";
import { appreciationScore, formatScoreApprecie, variantScore } from "./etatPosition";

describe("appréciation d’un score (jamais la couleur seule)", () => {
  it.each([
    [83.1, "élevé", "success"],
    [70, "élevé", "success"],
    [62.45, "moyen", "warning"],
    [40, "moyen", "warning"],
    [12, "faible", "destructive"],
  ] as const)("%s → %s / %s", (score, appreciation, variante) => {
    expect(appreciationScore(score)).toBe(appreciation);
    expect(variantScore(score)).toBe(variante);
  });

  it("le texte du badge porte l’appréciation", () => {
    expect(formatScoreApprecie(66.69)).toBe("66,7/100 · moyen");
    expect(formatScoreApprecie(null)).toBe("—");
    expect(variantScore(null)).toBe("secondary");
  });
});
