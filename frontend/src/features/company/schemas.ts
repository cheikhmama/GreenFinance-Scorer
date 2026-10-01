import { z } from "zod";
import { ReportType } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { ReportType };
export const TYPES_RAPPORT = Object.values(ReportType);

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

/** Lettre de mandat (tâche 5.2) : PDF de 5 Mo au plus — le backend vérifie seul la signature
 * binaire du fichier. */
const TAILLE_MAX_MANDAT = 5 * 1024 * 1024;

export const lettreDeMandatSchema = z
  .instanceof(File, { message: "La lettre de mandat (PDF) est requise." })
  .refine((f) => f.size > 0, "Le fichier est vide.")
  .refine((f) => f.size <= TAILLE_MAX_MANDAT, "La lettre de mandat dépasse 5 Mo.");

/** Formulaire d'inscription publique (POST /companies/register) — mêmes règles que le backend
 * (app/company/schemas.py::CompanyRegistrationRequest), qui reste seul juge des chiffres de
 * contrôle ISIN/LEI : ici, seulement la forme, pour un retour immédiat. */
export const companyRegistrationFormSchema = z.object({
  company_name: z.string().trim().min(2, "Le nom de l’entreprise est requis.").max(200),
  sector: z.string().trim().min(2, "Le secteur est requis.").max(100),
  country: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, "Code pays à deux lettres (ex. MR)."),
  isin: z
    .string()
    .trim()
    .regex(/^$|^[A-Za-z]{2}[A-Za-z0-9]{9}[0-9]$/, "Un ISIN compte 12 caractères (ex. MR…)."),
  lei: z
    .string()
    .trim()
    .regex(/^$|^[A-Za-z0-9]{18}[0-9]{2}$/, "Un LEI compte 20 caractères."),
  website: z
    .string()
    .trim()
    .regex(/^$|^https?:\/\//, "Adresse web attendue (https://…)."),
  contact_name: z.string().trim().min(2, "Votre nom est requis.").max(100),
  contact_email: z
    .string()
    .trim()
    .min(1, "L’adresse e-mail est requise")
    .email("Adresse e-mail invalide"),
  company_fax: z.string(),
  mandate_letter: lettreDeMandatSchema,
});

export type CompanyRegistrationForm = z.infer<typeof companyRegistrationFormSchema>;

/** Réponse à une demande d'informations, depuis la page de suivi publique. */
export const reponseDemandeInfosSchema = z.object({
  mandate_letter: lettreDeMandatSchema,
  message: z.string().trim().max(2000, "2 000 caractères au plus."),
});

export type ReponseDemandeInfosForm = z.infer<typeof reponseDemandeInfosSchema>;
