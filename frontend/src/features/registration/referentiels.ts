/** Listes et règles du formulaire d'inscription (tâche 5.10). Le serveur reste seul juge : ces
 * règles reprennent app/company/identifiers.py::normaliser_identifiant_fiscal pour un retour
 * immédiat. */

export const PAYS: { code: string; nom: string }[] = [
  { code: "MR", nom: "Mauritanie" },
  { code: "FR", nom: "France" },
  { code: "US", nom: "États-Unis" },
  { code: "SN", nom: "Sénégal" },
  { code: "MA", nom: "Maroc" },
  { code: "DZ", nom: "Algérie" },
  { code: "TN", nom: "Tunisie" },
  { code: "ML", nom: "Mali" },
  { code: "CI", nom: "Côte d’Ivoire" },
  { code: "BE", nom: "Belgique" },
  { code: "CH", nom: "Suisse" },
  { code: "DE", nom: "Allemagne" },
  { code: "ES", nom: "Espagne" },
  { code: "GB", nom: "Royaume-Uni" },
  { code: "CA", nom: "Canada" },
];

export const SECTEURS = [
  "Énergie",
  "Mines et extraction",
  "Industrie manufacturière",
  "Agroalimentaire",
  "Transport et logistique",
  "Banque et assurance",
  "Télécommunications",
  "BTP et immobilier",
  "Commerce et distribution",
  "Santé",
  "Technologies",
  "Autre",
];

/** Libellé de l'identifiant fiscal selon le pays. */
export function libelleIdentifiantFiscal(pays: string): string {
  switch (pays.toUpperCase()) {
    case "MR":
      return "NIF";
    case "FR":
      return "SIREN";
    case "US":
      return "EIN";
    default:
      return "Identifiant fiscal";
  }
}

export function exempleIdentifiantFiscal(pays: string): string {
  switch (pays.toUpperCase()) {
    case "MR":
      return "8 chiffres";
    case "FR":
      return "9 chiffres, ex. 732 829 320";
    case "US":
      return "ex. 12-3456789";
    default:
      return "Numéro d’identification fiscale";
  }
}

function luhnValide(chiffres: string): boolean {
  let total = 0;
  for (const [position, caractere] of [...chiffres].reverse().entries()) {
    let chiffre = Number(caractere);
    if (position % 2 === 1) {
      chiffre *= 2;
      if (chiffre > 9) chiffre -= 9;
    }
    total += chiffre;
  }
  return total % 10 === 0;
}

/** Message d'erreur, ou null si l'identifiant fiscal a la bonne forme pour ce pays. */
export function erreurIdentifiantFiscal(pays: string, valeur: string): string | null {
  const propre = valeur.replace(/\s+/g, "").toUpperCase();
  switch (pays.toUpperCase()) {
    case "MR":
      return /^\d{8}$/.test(propre)
        ? null
        : "Le NIF mauritanien doit comporter exactement 8 chiffres.";
    case "FR":
      if (!/^\d{9}$/.test(propre)) return "Le numéro SIREN doit comporter 9 chiffres.";
      return luhnValide(propre) ? null : "Numéro SIREN invalide (clé de contrôle).";
    case "US":
      return /^\d{2}-?\d{7}$/.test(propre)
        ? null
        : "L’EIN doit comporter 9 chiffres (ex. 12-3456789).";
    default:
      return /^[A-Z0-9][A-Z0-9./-]{2,31}$/.test(propre)
        ? null
        : "Saisissez un identifiant fiscal valide (3 à 32 caractères).";
  }
}
