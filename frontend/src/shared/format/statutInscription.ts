import type { RegistrationStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellé et couleur du statut d'inscription d'une entreprise (tâche 5.2) — partagés par l'espace
 * Administrateur et la page de suivi publique du demandeur. */
const LIBELLES: Record<RegistrationStatus, string> = {
  // Adresse du demandeur pas encore confirmée par son code (tâche 5.11) : rien à décider encore.
  EMAIL_VERIFICATION_PENDING: "E-mail à confirmer",
  PENDING_ONBOARDING: "Inscription à valider",
  INFO_REQUESTED: "Informations demandées",
  ACTIVE: "Active",
  REJECTED: "Inscription refusée",
  SUSPENDED: "Suspendue",
};

const VARIANTES: Record<RegistrationStatus, "warning" | "success" | "destructive" | "outline"> = {
  EMAIL_VERIFICATION_PENDING: "outline",
  PENDING_ONBOARDING: "warning",
  INFO_REQUESTED: "warning",
  ACTIVE: "success",
  REJECTED: "destructive",
  SUSPENDED: "destructive",
};

export function libelleStatutInscription(statut: RegistrationStatus): string {
  return LIBELLES[statut];
}

export function variantStatutInscription(statut: RegistrationStatus) {
  return VARIANTES[statut];
}

/** Demande qui attend une décision de l'Administrateur. */
export function inscriptionEnExamen(statut: RegistrationStatus): boolean {
  return statut === "PENDING_ONBOARDING" || statut === "INFO_REQUESTED";
}
