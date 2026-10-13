/** Libellés du journal d'audit. Le backend enregistre des codes anglais (tâche 4.7,
 * app/core/audit.py) ; une valeur inconnue s'affiche telle quelle plutôt que de disparaître. */

const ACTIONS: Record<string, string> = {
  access_request_approved: "Approbation d'une demande d'accès",
  access_request_rejected: "Refus d'une demande d'accès",
  access_request_resubmitted: "Nouvelle demande d'accès après refus",
  access_requested: "Demande d'accès",
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
  registration_email_verified: "Adresse e-mail de l'inscription confirmée",
  registration_rejected: "Refus d'inscription",
  registration_resubmitted: "Nouvelle demande après refus",
  registration_info_provided: "Informations complétées par le demandeur",
  registration_info_requested: "Demande d'informations",
  report_submitted: "Soumission d'un rapport (verrouillé)",
  role_changed: "Changement de rôle",
};

const TYPES_RESSOURCE: Record<string, string> = {
  Company: "Entreprise",
  ESGReport: "Rapport",
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

/** Choix des filtres du journal : le serveur filtre sur le code exact, jamais sur le libellé.
 * Ordre alphabétique par défaut, avant que les compteurs réels ne soient chargés — voir
 * trierOptionsActionsParNombre pour l'ordre affiché une fois les compteurs disponibles. */
export const OPTIONS_ACTIONS_JOURNAL = Object.entries(ACTIONS)
  .map(([value, label]) => ({ value, label }))
  .sort((a, b) => a.label.localeCompare(b.label, "fr"));

/** Trie les options du filtre Action par nombre d'entrées existantes, décroissant — une action
 * jamais survenue (compteur absent ou à 0) passe en bas plutôt qu'en tête d'un ordre alphabétique
 * qui ne reflète pas ce que le journal contient réellement (égalité : ordre alphabétique). */
export function trierOptionsActionsParNombre(
  compteurs: Record<string, number>,
): { value: string; label: string }[] {
  return [...OPTIONS_ACTIONS_JOURNAL].sort((a, b) => {
    const ecart = (compteurs[b.value] ?? 0) - (compteurs[a.value] ?? 0);
    return ecart !== 0 ? ecart : a.label.localeCompare(b.label, "fr");
  });
}

export const OPTIONS_TYPES_RESSOURCE = Object.entries(TYPES_RESSOURCE).map(([value, label]) => ({
  value,
  label,
}));

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
