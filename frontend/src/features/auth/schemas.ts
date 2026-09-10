import { z } from "zod";
import type { UtilisateurPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Role } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/**
 * Rôle et forme de l'utilisateur connecté : ré-exportés depuis le client généré (Orval, voir
 * orval.config.ts) plutôt que redéfinis à la main — une seule source de vérité avec le contrat
 * backend (app/core/enums.py::Role, app/auth/schemas.py::UtilisateurPublic).
 */
export { Role };
export type User = UtilisateurPublic;

/** Corps de POST /auth/login, validé côté client avant tout appel réseau. */
export const loginRequestSchema = z.object({
  email: z.string().min(1, "L'adresse e-mail est requise").email("Adresse e-mail invalide"),
  password: z.string().min(1, "Le mot de passe est requis"),
});

export type LoginRequest = z.infer<typeof loginRequestSchema>;

/** Formulaire de POST /auth/changer-mot-de-passe — la confirmation n'existe que côté
 * client (le backend ne reçoit que mot_de_passe_actuel/nouveau_mot_de_passe). */
export const changerMotDePasseFormSchema = z
  .object({
    motDePasseActuel: z.string().min(1, "Le mot de passe actuel est requis"),
    nouveauMotDePasse: z.string().min(8, "8 caractères minimum"),
    confirmation: z.string().min(1, "La confirmation est requise"),
  })
  .refine((values) => values.nouveauMotDePasse === values.confirmation, {
    message: "Les deux mots de passe ne correspondent pas.",
    path: ["confirmation"],
  });

export type ChangerMotDePasseForm = z.infer<typeof changerMotDePasseFormSchema>;
