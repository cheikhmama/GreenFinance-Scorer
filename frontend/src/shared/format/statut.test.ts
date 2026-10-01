import { describe, expect, it } from "vitest";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  LIBELLE_EN_EXAMEN,
  libelleStatutRapport,
  libelleStatutRapportEntreprise,
  variantStatutRapportEntreprise,
} from "./statut";

const TOUS: ReportStatus[] = [
  "DRAFT",
  "EXTRACTING",
  "EXTRACTION_FAILED",
  "AWAITING_ASSIGNMENT",
  "IN_AUDIT",
  "PENDING_DECISION",
  "REVISION_REQUESTED",
  "VALIDATED",
  "REJECTED",
];

describe("statut d'un rapport", () => {
  it("donne un libellé distinct à chaque état pour les rôles internes", () => {
    expect(new Set(TOUS.map(libelleStatutRapport)).size).toBe(TOUS.length);
  });

  it("regroupe les quatre états d'examen côté Entreprise", () => {
    const enExamen = TOUS.filter((s) => libelleStatutRapportEntreprise(s) === LIBELLE_EN_EXAMEN);
    expect(enExamen).toEqual(["EXTRACTING", "AWAITING_ASSIGNMENT", "IN_AUDIT", "PENDING_DECISION"]);
    expect(new Set(enExamen.map((s) => variantStatutRapportEntreprise(s)))).toEqual(
      new Set(["secondary"]),
    );
  });

  it("laisse visibles à l'Entreprise les états qui l'appellent à agir ou concluent", () => {
    expect(libelleStatutRapportEntreprise("DRAFT")).toBe("Brouillon");
    expect(libelleStatutRapportEntreprise("EXTRACTION_FAILED")).toBe("Échec de l'extraction");
    expect(libelleStatutRapportEntreprise("REVISION_REQUESTED")).toBe("Correction demandée");
    expect(libelleStatutRapportEntreprise("VALIDATED")).toBe("Validé");
  });

  it("ne nomme aucun état intermédiaire, pas même la lecture du fichier d'un brouillon", () => {
    expect(LIBELLE_EN_EXAMEN).toBe("En cours d'examen");
    expect(libelleStatutRapportEntreprise("EXTRACTING")).toBe(LIBELLE_EN_EXAMEN);
  });
});
