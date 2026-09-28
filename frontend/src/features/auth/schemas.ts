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

export const forgotPasswordFormSchema = z.object({
  email: z.string().trim().min(1, "L'adresse e-mail est requise").email("Adresse e-mail invalide"),
});

export type ForgotPasswordForm = z.infer<typeof forgotPasswordFormSchema>;

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

/** Formulaire de PATCH /auth/me — nom et email, jamais le rôle. L'unicité de l'email est
 * vérifiée côté backend (voir app/auth/router.py::modifier_mon_profil). */
export const modifierProfilFormSchema = z.object({
  nom: z.string().min(1, "Le nom est requis."),
  email: z.string().min(1, "L'adresse e-mail est requise").email("Adresse e-mail invalide"),
});

export type ModifierProfilForm = z.infer<typeof modifierProfilFormSchema>;

/** Étape 1 du changement de mot de passe progressif — un seul champ, vérifié avant de proposer
 * quoi que ce soit d'autre (voir POST /auth/verifier-mot-de-passe). */
export const verifierMotDePasseFormSchema = z.object({
  motDePasseActuel: z.string().min(1, "Le mot de passe actuel est requis"),
});

export type VerifierMotDePasseForm = z.infer<typeof verifierMotDePasseFormSchema>;

/** Étape 2 — mot_de_passe_actuel n'est plus redemandé : déjà vérifié à l'étape 1, transmis tel
 * quel au moment d'appeler POST /auth/changer-mot-de-passe. */
export const nouveauMotDePasseFormSchema = z
  .object({
    nouveauMotDePasse: z.string().min(8, "8 caractères minimum"),
    confirmation: z.string().min(1, "La confirmation est requise"),
  })
  .refine((values) => values.nouveauMotDePasse === values.confirmation, {
    message: "Les deux mots de passe ne correspondent pas.",
    path: ["confirmation"],
  });

export type NouveauMotDePasseForm = z.infer<typeof nouveauMotDePasseFormSchema>;

/** La limite bcrypt porte sur les octets UTF-8, y compris pour les caractères accentués. */
export const resetPasswordFormSchema = nouveauMotDePasseFormSchema.refine(
  (values) => new TextEncoder().encode(values.nouveauMotDePasse).length <= 72,
  {
    message: "Ce mot de passe est trop long. Réduisez le nombre de caractères.",
    path: ["nouveauMotDePasse"],
  },
);
