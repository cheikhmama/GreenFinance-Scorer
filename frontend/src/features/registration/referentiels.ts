/** Listes et règles du formulaire d'inscription (tâche 5.10). Le serveur reste seul juge : ces
 * règles reprennent app/company/identifiers.py::normaliser_identifiant_fiscal pour un retour
 * immédiat. */

/** Pays proposés en tête de liste : la zone d'activité principale de la plateforme. */
const PAYS_FREQUENTS = ["MR", "SN", "FR", "US", "MA", "CI", "ML", "DZ", "TN"];

// ISO 3166-1 alpha-2 (249 codes). Le serveur n'accepte que deux lettres
// (app/company/schemas.py::_pays_iso) ; les noms viennent de la locale française du navigateur.
const CODES_ISO =
  "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split(
    " ",
  );

const nomsDePays = new Intl.DisplayNames(["fr"], { type: "region" });
const nomDuPays = (code: string) => nomsDePays.of(code) ?? code;

export const PAYS: { code: string; nom: string }[] = CODES_ISO.map((code) => ({
  code,
  nom: nomDuPays(code),
})).sort((a, b) => a.nom.localeCompare(b.nom, "fr"));

/** Options du sélecteur de pays : les pays fréquents d'abord, puis tous les autres par ordre
 * alphabétique ; le code ISO retrouve aussi le pays (« MR »). */
export const OPTIONS_PAYS = [
  ...PAYS_FREQUENTS.map((code) => ({
    value: code,
    label: nomDuPays(code),
    group: "Pays fréquents",
    keywords: [code],
  })),
  ...PAYS.filter(({ code }) => !PAYS_FREQUENTS.includes(code)).map(({ code, nom }) => ({
    value: code,
    label: nom,
    group: "Tous les pays",
    keywords: [code],
  })),
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

export const OPTIONS_SECTEURS = SECTEURS.map((secteur) => ({ value: secteur, label: secteur }));

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

/** Messageries grand public (app/company/domaines.py) : une telle adresse ne rattache pas le
 * demandeur à son entreprise (tâche 5.11). */
const MESSAGERIES_GRAND_PUBLIC = new Set([
  "gmail.com",
  "googlemail.com",
  "yahoo.com",
  "yahoo.fr",
  "hotmail.com",
  "hotmail.fr",
  "outlook.com",
  "outlook.fr",
  "live.com",
  "live.fr",
  "msn.com",
  "icloud.com",
  "me.com",
  "aol.com",
  "gmx.com",
  "gmx.fr",
  "proton.me",
  "protonmail.com",
  "orange.fr",
  "free.fr",
  "laposte.net",
  "yandex.com",
  "mail.com",
]);

function domaineDuSite(site: string): string | null {
  try {
    return (
      new URL(site).hostname
        .toLowerCase()
        .replace(/\.$/, "")
        .replace(/^www\./, "") || null
    );
  } catch {
    return null;
  }
}

/** Message d'erreur, ou null si l'adresse est professionnelle et — quand un site web est donné —
 * sur son domaine (ou un sous-domaine). Même règle que le serveur. */
export function erreurAdresseProfessionnelle(email: string, site: string): string | null {
  const domaine = email.split("@").pop()?.toLowerCase().replace(/\.$/, "") ?? "";
  if (!domaine) return null;
  if (MESSAGERIES_GRAND_PUBLIC.has(domaine)) {
    return "Utilisez votre adresse e-mail professionnelle (pas une messagerie grand public).";
  }
  const domaineSite = site ? domaineDuSite(site) : null;
  if (
    domaineSite &&
    domaine !== domaineSite &&
    !domaine.endsWith(`.${domaineSite}`) &&
    !domaineSite.endsWith(`.${domaine}`)
  ) {
    return `L'adresse doit appartenir au domaine du site web (${domaineSite}).`;
  }
  return null;
}
