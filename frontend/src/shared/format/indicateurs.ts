import type { DataMethod, Pillar } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Libellés lisibles des indicateurs cibles de l'extraction (app/ingestion/cibles.py). Un code
 * absent d'ici (ajouté plus tard côté serveur) reste lisible grâce à libelleIndicateur. */
const LIBELLES_INDICATEURS: Record<string, string> = {
  scope_1: "Émissions Scope 1",
  scope_2: "Émissions Scope 2",
  scope_2_market_based: "Émissions Scope 2 (méthode marché)",
  scope_2_location_based: "Émissions Scope 2 (méthode localisation)",
  scope_3: "Émissions Scope 3",
  intensite_scope_1_2_marketbased: "Intensité carbone Scopes 1 et 2 (marché)",
  intensite_scope_1_2_3_hors_cat11: "Intensité carbone Scopes 1 à 3 (hors catégorie 11)",
  intensite_scope_1_2_3_total: "Intensité carbone Scopes 1 à 3 (total)",
  part_renouvelable_pourcentage: "Part d’énergie renouvelable",
  dechets_valorises_pourcentage: "Déchets valorisés",
  score_environnement_declare: "Score environnemental déclaré",
  effectif_total: "Effectif total",
  femmes_effectif_pourcentage: "Part de femmes dans l’effectif",
  femmes_management_pourcentage: "Part de femmes dans le management",
  heures_formation_par_employe: "Heures de formation par salarié",
  taux_frequence_accidents: "Taux de fréquence des accidents",
  deces_professionnels: "Décès liés au travail",
  score_social_declare: "Score social déclaré",
  femmes_conseil_pourcentage: "Part de femmes au conseil",
  taille_conseil: "Taille du conseil",
  administrateurs_independants_pourcentage: "Administrateurs indépendants",
  score_gouvernance_declare: "Score de gouvernance déclaré",
  score_global_declare: "Score ESG global déclaré",
};

export function libelleIndicateur(code: string): string {
  const connu = LIBELLES_INDICATEURS[code];
  if (connu) return connu;
  const texte = code.replace(/_pourcentage$/, "").replaceAll("_", " ");
  return texte.charAt(0).toUpperCase() + texte.slice(1);
}

/** Liste lisible d'indicateurs (« Taille du conseil, Effectif total »), pour dire ce qui manque. */
export function listeIndicateurs(codes: readonly string[]): string {
  return codes.map(libelleIndicateur).join(", ");
}

const METHODES_SCOPE_2: Record<string, string> = {
  market_based: "méthode marché",
  location_based: "méthode localisation",
};

/** « méthode marché » plutôt que « market_based » (app/ingestion/cibles.py). */
export function libelleCategorieGes(categorie: string): string {
  return METHODES_SCOPE_2[categorie] ?? categorie;
}

/** « Scope 2 (méthode marché) » plutôt que « Scope 2 — market_based ». */
export function libelleScope(scope: number, categorie?: string | null): string {
  return categorie ? `Scope ${scope} (${libelleCategorieGes(categorie)})` : `Scope ${scope}`;
}

const LIBELLES_PILIERS: Record<Pillar, string> = {
  ENVIRONNEMENT: "Environnement",
  SOCIAL: "Social",
  GOUVERNANCE: "Gouvernance",
};

export function libellePilier(pilier: Pillar): string {
  return LIBELLES_PILIERS[pilier] ?? pilier;
}

const LIBELLES_METHODES: Record<DataMethod, string> = {
  RAPPORTEE: "Publiée",
  ESTIMEE: "Estimée",
  CALCULEE: "Calculée",
};

export function libelleMethode(methode: DataMethod): string {
  return LIBELLES_METHODES[methode] ?? methode;
}

// « count » : un nombre sans unité (« 0 décès », pas « 0 count »).
const UNITES: Record<string, string> = { m3: "m³", tco2e: "tCO₂e", tCO2e: "tCO₂e", count: "" };

export function libelleUnite(unite?: string | null): string {
  return unite ? (UNITES[unite] ?? unite) : "";
}

/** Valeur au format français (« 125 400 m³ », « 38,5 % »), unité normalisée. */
export function formatValeur(valeur: number, unite?: string | null): string {
  const nombre = valeur.toLocaleString("fr-FR", { maximumFractionDigits: 3 });
  const u = unite ? (UNITES[unite] ?? unite) : "";
  return u ? `${nombre} ${u}` : nombre;
}
