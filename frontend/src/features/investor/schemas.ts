import { z } from "zod";
import {
  DevisePosition,
  TypeDureeInvestissement,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { DevisePosition, TypeDureeInvestissement };
export const DEVISES = Object.values(DevisePosition);
export const TYPES_DUREE = Object.values(TypeDureeInvestissement);

export const creerPortefeuilleSchema = z.object({
  nom: z.string().min(1, "Le nom est requis."),
  devise_reference: z.enum(DevisePosition),
});

export type CreerPortefeuilleForm = z.infer<typeof creerPortefeuilleSchema>;

export const renommerPortefeuilleSchema = z.object({
  nom: z.string().min(1, "Le nom est requis."),
});

export type RenommerPortefeuilleForm = z.infer<typeof renommerPortefeuilleSchema>;

// z.number() (pas z.coerce.number(), voir features/company/schemas.ts) : le formulaire convertit
// déjà la saisie en number via valueAsNumber dans l'input, jamais une string à coercer ici.
const positionBaseSchema = z.object({
  montant: z.number({ message: "Le montant est requis." }).positive("Le montant doit être positif."),
  devise: z.enum(DevisePosition),
  type_duree: z.enum(TypeDureeInvestissement),
  date_debut: z.string().min(1, "La date de début est requise."),
  date_fin: z.string().optional(),
});

// Même schéma en création et en modification (voir PortfolioDetailPage.tsx) : entreprise_id est
// toujours présent (figé sur l'entreprise existante en modification, jamais affiché ni modifié),
// un seul type de formulaire évite un résolveur conditionnel que react-hook-form ne type pas bien.
export const ajouterPositionSchema = positionBaseSchema
  .extend({ entreprise_id: z.string().min(1, "Une entreprise doit être sélectionnée.") })
  .refine((v) => v.type_duree !== TypeDureeInvestissement.FIXE || !!v.date_fin, {
    message: "La date de fin est requise pour une durée fixe.",
    path: ["date_fin"],
  });

export type AjouterPositionForm = z.infer<typeof ajouterPositionSchema>;
