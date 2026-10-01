import { describe, expect, it } from "vitest";
import { presentationSession } from "./presentation";

describe("présentation de la session active (tableau de bord Entreprise)", () => {
  it("regroupe les étapes d’examen et donne un libellé à chaque état d’action", () => {
    for (const statut of [
      "EXTRACTING",
      "AWAITING_ASSIGNMENT",
      "IN_AUDIT",
      "PENDING_DECISION",
    ] as const) {
      expect(presentationSession(statut).libelle).toBe("En cours d'examen 🔒");
    }
    expect(presentationSession("DRAFT").libelle).toBe("Brouillon");
    expect(presentationSession("REVISION_REQUESTED").libelle).toBe("Précisions requises ⚠️");
    expect(presentationSession("VALIDATED").libelle).toBe("Validé et publié ✓");
    expect(presentationSession("VALIDATED").description).toBe(
      "Votre rapport a été validé et votre score officiel est disponible.",
    );
  });
});
