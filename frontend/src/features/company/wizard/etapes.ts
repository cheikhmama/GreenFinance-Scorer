import type { EtapeWizard } from "@/shared/ui/wizard";

/** Les quatre étapes d'une déclaration (spec §3.1) : les deux premières avant que le brouillon
 * n'existe, les deux dernières sur le brouillon. */
export const ETAPES_DECLARATION: readonly EtapeWizard[] = [
  { id: "exercice", titre: "Exercice" },
  { id: "finances", titre: "Données financières" },
  { id: "document", titre: "Document" },
  { id: "verification", titre: "Vérification" },
];
