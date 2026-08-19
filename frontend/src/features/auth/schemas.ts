import { z } from "zod";

/**
 * Rôles métier tels que définis par `Role` dans app/core/enums.py côté backend.
 * Une union de littéraux plutôt qu'un `enum` TypeScript : `erasableSyntaxOnly` est
 * activé dans tsconfig.app.json, qui interdit les enums (ils émettent du code à
 * l'exécution, donc ne sont pas "effaçables" par une simple suppression de types).
 */
export const ROLES = [
  "ADMINISTRATEUR",
  "ENTREPRISE",
  "AUDITEUR",
  "INVESTISSEUR",
  "CHERCHEUR",
  "INSTITUTION",
] as const;

export type Role = (typeof ROLES)[number];

/**
 * Forme exacte renvoyée par POST /auth/login et GET /auth/me (contrat backend
 * app/auth/router.py). Les deux routes renvoient la même représentation de
 * l'utilisateur connecté.
 */
export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  role: z.enum(ROLES),
  date_creation: z.string(),
  actif: z.boolean(),
});

export type User = z.infer<typeof userSchema>;

/** Corps de POST /auth/login, validé côté client avant tout appel réseau. */
export const loginRequestSchema = z.object({
  email: z.string().min(1, "L'adresse e-mail est requise").email("Adresse e-mail invalide"),
  password: z.string().min(1, "Le mot de passe est requis"),
});

export type LoginRequest = z.infer<typeof loginRequestSchema>;
