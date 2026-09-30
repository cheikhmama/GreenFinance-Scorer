import { z } from "zod";
import { AuditDecision } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { AuditDecision };

/** Un commentaire est obligatoire pour recommander un rejet ou demander une clarification
 * (Phase 4 §4.5) — une simple recommandation de validation peut rester silencieuse. */
export const soumettreAvisSchema = z
  .object({
    decision: z.enum([
      AuditDecision.RECOMMANDE_VALIDATION,
      AuditDecision.RECOMMANDE_REJET,
      AuditDecision.DEMANDE_CLARIFICATION,
    ]),
    comment: z.string().optional(),
  })
  .refine(
    (values) =>
      values.decision === AuditDecision.RECOMMANDE_VALIDATION ||
      (values.comment?.trim().length ?? 0) > 0,
    {
      message: "Un commentaire est requis pour recommander un rejet ou demander une clarification.",
      path: ["comment"],
    },
  );

export type SoumettreAvisForm = z.infer<typeof soumettreAvisSchema>;
