import { z } from "zod";

/** date_debut <= date_fin_prevue et date_limite >= date_debut sont revérifiés côté serveur (voir
 * app/institution/projets.py::_verifier_coherence_dates) — cette validation n'est qu'un
 * confort immédiat, jamais la source de vérité. */
export const creerProjetSchema = z
  .object({
    name: z.string().min(1, "Le nom est requis."),
    description: z.string().optional(),
    objective: z.string().optional(),
    start_date: z.string().optional(),
    planned_end_date: z.string().optional(),
    deadline: z.string().optional(),
  })
  .refine(
    (valeurs) =>
      !valeurs.start_date || !valeurs.planned_end_date || valeurs.start_date <= valeurs.planned_end_date,
    { message: "La date de début doit précéder la date de fin prévue.", path: ["planned_end_date"] },
  )
  .refine(
    (valeurs) => !valeurs.start_date || !valeurs.deadline || valeurs.deadline >= valeurs.start_date,
    { message: "La date limite ne peut pas précéder la date de début.", path: ["deadline"] },
  );

export type CreerProjetForm = z.infer<typeof creerProjetSchema>;

export const inviterChercheurSchema = z.object({
  collaboration_terms: z.string().optional(),
});

export type InviterChercheurForm = z.infer<typeof inviterChercheurSchema>;

/** Un commentaire est requis pour demander une correction (voir
 * app/institution/analyses.py::demander_correction) ; optionnel pour valider. La validation zod
 * elle-même reste permissive, la contrainte réelle est appliquée côté formulaire/serveur. */
export const decisionAnalyseSchema = z.object({
  comment: z.string().optional(),
});

export type DecisionAnalyseForm = z.infer<typeof decisionAnalyseSchema>;
