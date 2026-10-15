import { describe, expect, it } from "vitest";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { PHASES_DECLARATION, phaseDeclaration } from "./phaseDeclaration";

const CAS: [ReportStatus, string | null, number, string, string, string | null][] = [
  ["DRAFT", null, 0, "Déposé", "neutre", null],
  ["DRAFT", "pdf_illisible", 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["EXTRACTING", null, 1, "Analyse en cours", "info", null],
  ["EXTRACTION_FAILED", "pdf_illisible", 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["EXTRACTION_FAILED", null, 1, "Analyse impossible", "danger", "ANALYSE_IMPOSSIBLE"],
  ["AWAITING_ASSIGNMENT", null, 2, "En cours d’examen", "attention", null],
  ["IN_AUDIT", null, 2, "En cours d’examen", "attention", null],
  ["PENDING_DECISION", null, 2, "En cours d’examen", "attention", null],
  ["REVISION_REQUESTED", null, 2, "Correction demandée", "attention", "CORRECTION_DEMANDEE"],
  ["VALIDATED", null, 3, "Validé & publié", "succes", null],
  ["REJECTED", null, 3, "Refusé", "danger", null],
];

describe("phaseDeclaration", () => {
  it.each(CAS)(
    "%s (erreur %s) → phase %i « %s »",
    (status, erreur, index, libelle, ton, branche) => {
      expect(phaseDeclaration({ status, extraction_error: erreur })).toEqual({
        index,
        libelle,
        ton,
        branche,
      });
    },
  );

  it("une erreur d’analyse ancienne ne masque pas l’examen en cours", () => {
    expect(
      phaseDeclaration({ status: "IN_AUDIT", extraction_error: "quota_llm_epuise" }).index,
    ).toBe(2);
  });

  it("quatre phases, dans l’ordre du cycle", () => {
    expect(PHASES_DECLARATION).toEqual([
      "Déposé",
      "Analyse en cours",
      "En cours d’examen",
      "Audité",
    ]);
  });

  it("aucun nom d’étape interne", () => {
    const libelles = CAS.map(
      ([s, e]) => phaseDeclaration({ status: s, extraction_error: e }).libelle,
    );
    for (const interne of ["affecter", "audit", "décision", "Extraction"]) {
      expect(libelles.join(" ")).not.toContain(interne);
    }
  });
});
