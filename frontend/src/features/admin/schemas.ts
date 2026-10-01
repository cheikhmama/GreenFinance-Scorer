import { z } from "zod";
import { Currency, Role } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { auPlusDeuxDecimales, MESSAGE_DEUX_DECIMALES } from "@/shared/format/montant";

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

/** Rôles consultables dans la liste des comptes (UsersSection) — contrairement à
 * ROLES_ATTRIBUABLES (formulaire de création), inclut ADMIN : on ne peut pas en créer un
 * depuis ce formulaire, mais consulter/désactiver/réactiver les comptes déjà existants reste une
 * opération légitime (ex. suivre l'effectif d'administrateurs actifs). */
export const ROLES_CONSULTABLES = Object.values(Role);

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

/** impose_minimum est un champ purement local au formulaire (jamais envoyé au serveur) : il
 * pilote l'affichage de montant_minimum_investissement/devise_montant_minimum et la décision
 * d'envoyer ce couple ou (null, null) à la soumission — voir AdminCompanyDetailPage.tsx. Le
 * serveur applique la même règle "ensemble ou aucun" (app/admin/schemas.py::
 * ModifierEntrepriseAdminRequest), reproduite ici pour un message d'erreur immédiat. */
export const modifierEntrepriseSchema = z
  .object({
    name: z.string().min(1, "Le nom est requis."),
    sector: z.string().min(1, "Le secteur est requis."),
    country: z.string().min(1, "Le pays est requis."),
    description: z.string().optional(),
    website: z.string().optional(),
    impose_minimum: z.boolean(),
    minimum_investment_amount: z
      .number()
      .refine(auPlusDeuxDecimales, MESSAGE_DEUX_DECIMALES)
      .optional(),
    minimum_investment_currency: z.enum(Currency).optional(),
  })
  .superRefine((values, ctx) => {
    if (!values.impose_minimum) return;
    if (
      values.minimum_investment_amount === undefined ||
      Number.isNaN(values.minimum_investment_amount)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["minimum_investment_amount"],
        message: "Le montant est requis.",
      });
    }
  });

export type ModifierEntrepriseForm = z.infer<typeof modifierEntrepriseSchema>;
