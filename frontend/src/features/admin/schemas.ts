import { z } from "zod";
import { Role } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { Role };

/** Jamais ADMINISTRATEUR — même règle déjà validée côté prototype (docs/PROTOTYPE_FRONTEND.md) et
 * appliquée côté serveur (app/admin/utilisateurs.py::creer_utilisateur). */
export const ROLES_ATTRIBUABLES = [
  Role.ENTREPRISE,
  Role.INVESTISSEUR,
  Role.AUDITEUR,
  Role.INSTITUTION,
  Role.CHERCHEUR,
] as const;

export type RoleAttribuable = (typeof ROLES_ATTRIBUABLES)[number];

export const creerUtilisateurSchema = z
  .object({
    email: z.string().min(1, "L'e-mail est requis.").email("Adresse e-mail invalide."),
    role: z.enum(ROLES_ATTRIBUABLES),
    // Pas de champ nom (titulaire du compte) dans ce formulaire — l'Administrateur ne le saisit
    // pas, app/admin/utilisateurs.py::creer_utilisateur le déduit de la partie locale de l'e-mail
    // quand absent (compromis choisi sciemment). nom_entreprise (nom de l'Entreprise elle-même)
    // reste distinct et requis pour ce rôle uniquement.
    nom_entreprise: z.string().optional(),
    secteur: z.string().optional(),
    pays: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.role !== Role.ENTREPRISE) return;
    // Le profil Entreprise (nom_entreprise/secteur/pays) est requis dans le même geste que la
    // création du compte — voir app/admin/utilisateurs.py::creer_utilisateur, sans lui le compte
    // ne peut rien déposer (aucune Entreprise à laquelle le rattacher).
    (["nom_entreprise", "secteur", "pays"] as const).forEach((champ) => {
      if (!values[champ]?.trim()) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: [champ],
          message: "Ce champ est requis pour créer une Entreprise.",
        });
      }
    });
  });

export type CreerUtilisateurForm = z.infer<typeof creerUtilisateurSchema>;

export const changerRoleSchema = z.object({
  role: z.enum(ROLES_ATTRIBUABLES),
});

export type ChangerRoleForm = z.infer<typeof changerRoleSchema>;

export const decisionSchema = z.object({
  commentaire: z.string().optional(),
});

export type DecisionForm = z.infer<typeof decisionSchema>;
