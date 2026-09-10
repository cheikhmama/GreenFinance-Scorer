import { z } from "zod";
import { TypeRapport } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { TypeRapport };
export const TYPES_RAPPORT = Object.values(TypeRapport);

// z.number(), pas z.coerce.number() : coerce sépare le type d'entrée (unknown) du type de
// sortie (number), ce que le résolveur zodResolver + useForm ne réconcilie pas proprement ici.
// La conversion string -> number se fait dans le onChange de l'input (valueAsNumber), le
// formulaire ne porte donc jamais qu'un number.
const anneeReportingSchema = z
  .number({ message: "L'année est requise." })
  .int("L'année doit être un nombre entier.")
  .min(2000, "L'année est invalide.")
  .max(2100, "L'année est invalide.");

export const deposerRapportSchema = z.object({
  fichier: z
    .instanceof(File, { message: "Un fichier PDF est requis." })
    .refine((f) => f.size > 0, "Le fichier est vide."),
  type: z.string().min(1, "Le type de rapport est requis."),
  annee_reporting: anneeReportingSchema,
});

export type DeposerRapportForm = z.infer<typeof deposerRapportSchema>;

export const correctionSchema = z.object({
  fichier: z
    .instanceof(File, { message: "Un fichier PDF est requis." })
    .refine((f) => f.size > 0, "Le fichier est vide."),
  annee_reporting: anneeReportingSchema,
});

export type CorrectionForm = z.infer<typeof correctionSchema>;
