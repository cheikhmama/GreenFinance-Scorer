import { z } from "zod";

/** date_debut <= date_fin_prevue et date_limite >= date_debut sont revérifiés côté serveur (voir
 * app/institution/projets.py::_verifier_coherence_dates) — cette validation n'est qu'un
 * confort immédiat, jamais la source de vérité. */
export const creerProjetSchema = z
  .object({
    nom: z.string().min(1, "Le nom est requis."),
    description: z.string().optional(),
    objectif: z.string().optional(),
    date_debut: z.string().optional(),
    date_fin_prevue: z.string().optional(),
    date_limite: z.string().optional(),
  })
  .refine(
    (valeurs) =>
      !valeurs.date_debut || !valeurs.date_fin_prevue || valeurs.date_debut <= valeurs.date_fin_prevue,
    { message: "La date de début doit précéder la date de fin prévue.", path: ["date_fin_prevue"] },
  )
  .refine(
    (valeurs) => !valeurs.date_debut || !valeurs.date_limite || valeurs.date_limite >= valeurs.date_debut,
    { message: "La date limite ne peut pas précéder la date de début.", path: ["date_limite"] },
  );

export type CreerProjetForm = z.infer<typeof creerProjetSchema>;

export const inviterChercheurSchema = z.object({
  conditions_collaboration: z.string().optional(),
});

export type InviterChercheurForm = z.infer<typeof inviterChercheurSchema>;

/** Un commentaire est requis pour demander une correction (voir
 * app/institution/analyses.py::demander_correction) ; optionnel pour valider. La validation zod
 * elle-même reste permissive, la contrainte réelle est appliquée côté formulaire/serveur. */
export const decisionAnalyseSchema = z.object({
  commentaire: z.string().optional(),
});

export type DecisionAnalyseForm = z.infer<typeof decisionAnalyseSchema>;
