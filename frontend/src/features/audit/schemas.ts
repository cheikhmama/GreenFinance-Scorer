import { z } from "zod";
import { AuditDecision } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { AuditDecision };

/** Tout avis autre que favorable est motivé (tâche 5.6) — même règle que le backend
 * (app/audit/schemas.py::SoumettreAvisRequest). */
export const soumettreAvisSchema = z
  .object({
    decision: z.enum(AuditDecision),
    comment: z.string().optional(),
  })
  .refine(
    (values) =>
      values.decision === AuditDecision.FAVORABLE || (values.comment?.trim().length ?? 0) > 0,
    {
      message: "Un commentaire est requis pour tout avis autre que favorable.",
      path: ["comment"],
    },
  );

export type SoumettreAvisForm = z.infer<typeof soumettreAvisSchema>;
