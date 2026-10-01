/** Libellés du journal d'audit. Le backend enregistre des codes anglais (tâche 4.7,
 * app/core/audit.py) ; une valeur inconnue s'affiche telle quelle plutôt que de disparaître. */

const ACTIONS: Record<string, string> = {
  account_activated: "Activation du compte",
  account_created: "Création du compte",
  account_deactivated: "Désactivation du compte",
  account_reactivated: "Réactivation du compte",
  activation_link_resent: "Renvoi du lien d'activation",
  company_registered: "Inscription d'entreprise",
  email_change_requested: "Demande de changement d'e-mail",
  email_changed: "Changement d'e-mail",
  login: "Connexion",
  logout: "Déconnexion",
  password_changed: "Changement de mot de passe",
  password_reset: "Réinitialisation du mot de passe",
  password_reset_requested: "Demande de réinitialisation du mot de passe",
  registration_approved: "Validation d'inscription",
  registration_rejected: "Refus d'inscription",
  registration_resubmitted: "Nouvelle demande après refus",
  registration_info_provided: "Informations complétées par le demandeur",
  registration_info_requested: "Demande d'informations",
  role_changed: "Changement de rôle",
};

const TYPES_RESSOURCE: Record<string, string> = {
  Company: "Entreprise",
  User: "Utilisateur",
};

const RESULTATS: Record<string, string> = {
  success: "Succès",
  failure: "Échec",
};

const VALEURS: Record<string, string> = {
  active: "actif",
  inactive: "inactif",
};

export function libelleActionJournal(action: string): string {
  return ACTIONS[action] ?? action;
}

export function libelleTypeRessource(type: string): string {
  return TYPES_RESSOURCE[type] ?? type;
}

export function libelleResultatJournal(resultat: string): string {
  return RESULTATS[resultat] ?? resultat;
}

/** Ancienne / nouvelle valeur : seul l'état du compte est un code, le reste (e-mail, rôle,
 * motif de refus) s'affiche tel quel. */
export function libelleValeurJournal(valeur: string): string {
  return VALEURS[valeur] ?? valeur;
}
