import { describe, expect, it } from "vitest";
import { dernierScoreAffichable, presentationSession } from "./presentation";

describe("présentation de la session active (tableau de bord Entreprise)", () => {
  it("regroupe les étapes d’examen et donne un libellé et une phrase à chaque état", () => {
    for (const statut of [
      "EXTRACTING",
      "AWAITING_ASSIGNMENT",
      "IN_AUDIT",
      "PENDING_DECISION",
    ] as const) {
      expect(presentationSession(statut).libelle).toBe("En cours d'examen");
    }
    expect(presentationSession("DRAFT").libelle).toBe("Brouillon");
    expect(presentationSession("REVISION_REQUESTED").libelle).toBe("Correction demandée");
    expect(presentationSession("VALIDATED").libelle).toBe("Validé & Publié");
  });
});

describe("dernier score affichable à côté de la session active", () => {
  const valide = (fiscal_year: number) => ({
    status: "VALIDATED" as const,
    fiscal_year,
    submitted_at: `${fiscal_year + 1}-03-01T00:00:00Z`,
    official_global_score: 60,
  });

  it("prend le dernier exercice validé antérieur à la session, ou aucun", () => {
    const rapports = [valide(2023), valide(2024), valide(2025)];
    expect(dernierScoreAffichable(rapports, { fiscal_year: 2025 })?.fiscal_year).toBe(2024);
    expect(dernierScoreAffichable(rapports, { fiscal_year: 2026 })?.fiscal_year).toBe(2025);
    expect(dernierScoreAffichable(rapports, undefined)?.fiscal_year).toBe(2025);
    expect(dernierScoreAffichable([valide(2025)], { fiscal_year: 2025 })).toBeUndefined();
  });
});
