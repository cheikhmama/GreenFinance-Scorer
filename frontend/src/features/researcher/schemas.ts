import { z } from "zod";

/** Formulaire de création/modification/correction d'une analyse — entreprise_ids porté par une
 * sélection multiple (au moins une, jamais une saisie libre : voir CompaniesPicker). */
export const analyseFormSchema = z.object({
  title: z.string().min(1, "Le titre est requis."),
  content: z.string().min(1, "Le contenu est requis."),
  company_ids: z.array(z.string()).min(1, "Sélectionne au moins une entreprise à comparer."),
});

export type AnalyseForm = z.infer<typeof analyseFormSchema>;
