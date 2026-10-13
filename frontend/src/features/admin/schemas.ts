import { z } from "zod";
import { Currency, Role } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export { Currency, Role };
export const DEVISES = Object.values(Currency);

/** Jamais ADMIN — même règle déjà validée côté prototype (docs/PROTOTYPE_FRONTEND.md) et
 * appliquée côté serveur (app/admin/utilisateurs.py::creer_utilisateur). */
export const ROLES_ATTRIBUABLES = [
  Role.ENTERPRISE,
  Role.INVESTOR,
  Role.AUDITOR,
  Role.INSTITUTION,
  Role.RESEARCHER,
] as const;

export type RoleAttribuable = (typeof ROLES_ATTRIBUABLES)[number];

/** Rôles consultables dans le filtre de la liste des comptes (UsersSection) — exclut ADMIN :
 * l'effectif d'administrateurs n'a pas vocation à être filtré/parcouru comme les autres rôles
 * depuis cet écran. Ne change rien aux droits : un compte ADMIN reste un rôle valide côté
 * serveur, seule l'option de filtre disparaît ici. */
export const ROLES_CONSULTABLES = Object.values(Role).filter((role) => role !== Role.ADMIN);

export type RoleConsultable = (typeof ROLES_CONSULTABLES)[number];

export const creerUtilisateurSchema = z
  .object({
    email: z.string().min(1, "L'e-mail est requis.").email("Adresse e-mail invalide."),
    role: z.enum(ROLES_ATTRIBUABLES),
    // Pas de champ nom (titulaire du compte) dans ce formulaire — l'Administrateur ne le saisit
    // pas, app/admin/utilisateurs.py::creer_utilisateur le déduit de la partie locale de l'e-mail
    // quand absent (compromis choisi sciemment). nom_entreprise (nom de l'Entreprise elle-même)
    // reste distinct et requis pour ce rôle uniquement.
    company_name: z.string().optional(),
    sector: z.string().optional(),
    country: z.string().optional(),
  })
  .superRefine((values, ctx) => {
    if (values.role !== Role.ENTERPRISE) return;
    // Le profil Entreprise (nom_entreprise/secteur/pays) est requis dans le même geste que la
    // création du compte — voir app/admin/utilisateurs.py::creer_utilisateur, sans lui le compte
    // ne peut rien déposer (aucune Entreprise à laquelle le rattacher).
    (["company_name", "sector", "country"] as const).forEach((champ) => {
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
  comment: z.string().optional(),
});

export type DecisionForm = z.infer<typeof decisionSchema>;

/** Identité seulement (nom, secteur, pays) : description, site officiel et montant minimum sont
 * désormais modifiables par l'Entreprise elle-même, jamais par l'Admin (voir
 * features/company/schemas.ts::modifierProfilEntrepriseSchema et app/admin/schemas.py::
 * ModifierEntrepriseAdminRequest, qui ne les porte plus côté serveur non plus). */
export const modifierEntrepriseSchema = z.object({
  name: z.string().min(1, "Le nom est requis."),
  sector: z.string().min(1, "Le secteur est requis."),
  country: z.string().min(1, "Le pays est requis."),
});

export type ModifierEntrepriseForm = z.infer<typeof modifierEntrepriseSchema>;
