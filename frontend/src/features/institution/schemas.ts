import { z } from "zod";

export const creerProjetSchema = z.object({
  nom: z.string().min(1, "Le nom est requis."),
  description: z.string().optional(),
});

export type CreerProjetForm = z.infer<typeof creerProjetSchema>;

/** Un commentaire est requis pour demander une correction (voir
 * app/institution/analyses.py::demander_correction) ; optionnel pour valider. La validation zod
 * elle-même reste permissive, la contrainte réelle est appliquée côté formulaire/serveur. */
export const decisionAnalyseSchema = z.object({
  commentaire: z.string().optional(),
});

export type DecisionAnalyseForm = z.infer<typeof decisionAnalyseSchema>;
