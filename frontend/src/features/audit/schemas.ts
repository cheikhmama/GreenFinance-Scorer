import { z } from "zod";
import { DecisionAudit } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { DecisionAudit };

/** Un commentaire est obligatoire pour recommander un rejet ou demander une clarification
 * (Phase 4 §4.5) — une simple recommandation de validation peut rester silencieuse. */
export const soumettreAvisSchema = z
  .object({
    decision: z.enum([
      DecisionAudit.RECOMMANDE_VALIDATION,
      DecisionAudit.RECOMMANDE_REJET,
      DecisionAudit.DEMANDE_CLARIFICATION,
    ]),
    commentaire: z.string().optional(),
  })
  .refine(
    (values) =>
      values.decision === DecisionAudit.RECOMMANDE_VALIDATION ||
      (values.commentaire?.trim().length ?? 0) > 0,
    {
      message: "Un commentaire est requis pour recommander un rejet ou demander une clarification.",
      path: ["commentaire"],
    },
  );

export type SoumettreAvisForm = z.infer<typeof soumettreAvisSchema>;
