import { z } from "zod";
import {
  Currency,
  DurationType,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { auPlusDeuxDecimales, MESSAGE_DEUX_DECIMALES } from "@/shared/format/montant";

export { Currency, DurationType };
export const DEVISES = Object.values(Currency);
export const TYPES_DUREE = Object.values(DurationType);

// Même limite que côté serveur (app/investor/entreprises.py::_MAX_ENTREPRISES_COMPARAISON) —
// jamais laisser composer une sélection que le backend refusera ensuite.
export const MAX_SELECTION_COMPARAISON = 4;

export const creerPortefeuilleSchema = z.object({
  name: z.string().min(1, "Le nom est requis."),
});

export type CreerPortefeuilleForm = z.infer<typeof creerPortefeuilleSchema>;

export const renommerPortefeuilleSchema = z.object({
  name: z.string().min(1, "Le nom est requis."),
});

export type RenommerPortefeuilleForm = z.infer<typeof renommerPortefeuilleSchema>;

// z.number() (pas z.coerce.number(), voir features/company/schemas.ts) : le formulaire convertit
// déjà la saisie en number via valueAsNumber dans l'input, jamais une string à coercer ici.
const positionBaseSchema = z.object({
  amount: z
    .number({ message: "Le montant est requis." })
    .positive("Le montant doit être positif.")
    .refine(auPlusDeuxDecimales, MESSAGE_DEUX_DECIMALES),
  currency: z.enum(Currency),
  duration_type: z.enum(DurationType),
  start_date: z.string().min(1, "La date de début est requise."),
  end_date: z.string().optional(),
});

// Même schéma en création et en modification (voir PortfolioDetailPage.tsx) : entreprise_id est
// toujours présent (figé sur l'entreprise existante en modification, jamais affiché ni modifié),
// un seul type de formulaire évite un résolveur conditionnel que react-hook-form ne type pas bien.
export const ajouterPositionSchema = positionBaseSchema
  .extend({ company_id: z.string().min(1, "Une entreprise doit être sélectionnée.") })
  .refine((v) => v.duration_type !== DurationType.FIXE || !!v.end_date, {
    message: "La date de fin est requise pour une durée fixe.",
    path: ["end_date"],
  });

export type AjouterPositionForm = z.infer<typeof ajouterPositionSchema>;
