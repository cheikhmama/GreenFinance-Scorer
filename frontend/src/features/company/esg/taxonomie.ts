import type { Pillar } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

/** Taxonomie de navigation de l'espace Entreprise (spec §2.1) : pilier → famille → codes
 * d'indicateurs (app/ingestion/cibles.py). Un regroupement d'affichage, pas une règle de calcul :
 * le score ne lit que config/weights/default.yaml. Un code inconnu ici reste visible, dans la
 * famille « Autres indicateurs » de son pilier. */
export type SlugPilier = "environnement" | "social" | "gouvernance";

export const PILIERS: readonly { slug: SlugPilier; pilier: Pillar }[] = [
  { slug: "environnement", pilier: "ENVIRONNEMENT" },
  { slug: "social", pilier: "SOCIAL" },
  { slug: "gouvernance", pilier: "GOUVERNANCE" },
];

export function pilierDepuisSlug(slug: string | undefined): Pillar | null {
  return PILIERS.find((p) => p.slug === slug)?.pilier ?? null;
}

export function slugPilier(pilier: Pillar): SlugPilier {
  return PILIERS.find((p) => p.pilier === pilier)?.slug ?? "environnement";
}

export interface Famille {
  slug: string;
  libelle: string;
  pilier: Pillar;
  codes: readonly string[];
}

export const FAMILLE_AUTRES = "autres";

/** Les scores auto-déclarés restent une famille à part : jamais mêlés au score calculé
 * (config/weights/default.yaml). */
const FAMILLES: readonly Famille[] = [
  {
    slug: "emissions-ges",
    libelle: "Émissions GES",
    pilier: "ENVIRONNEMENT",
    codes: ["scope_1", "scope_2", "scope_2_market_based", "scope_2_location_based", "scope_3"],
  },
  {
    slug: "intensite-carbone",
    libelle: "Intensité carbone",
    pilier: "ENVIRONNEMENT",
    codes: [
      "intensite_scope_1_2_marketbased",
      "intensite_scope_1_2_3_hors_cat11",
      "intensite_scope_1_2_3_total",
    ],
  },
  {
    slug: "energie-ressources",
    libelle: "Énergie & ressources",
    pilier: "ENVIRONNEMENT",
    codes: ["part_renouvelable_pourcentage", "dechets_valorises_pourcentage"],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "ENVIRONNEMENT",
    codes: ["score_environnement_declare"],
  },
  {
    slug: "effectifs-diversite",
    libelle: "Effectifs & diversité",
    pilier: "SOCIAL",
    codes: ["effectif_total", "femmes_effectif_pourcentage", "femmes_management_pourcentage"],
  },
  {
    slug: "sante-securite",
    libelle: "Santé & sécurité",
    pilier: "SOCIAL",
    codes: ["deces_professionnels", "taux_frequence_accidents"],
  },
  {
    slug: "formation",
    libelle: "Formation",
    pilier: "SOCIAL",
    codes: ["heures_formation_par_employe"],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "SOCIAL",
    codes: ["score_social_declare"],
  },
  {
    slug: "conseil",
    libelle: "Conseil",
    pilier: "GOUVERNANCE",
    codes: [
      "taille_conseil",
      "administrateurs_independants_pourcentage",
      "femmes_conseil_pourcentage",
    ],
  },
  {
    slug: "score-declare",
    libelle: "Score auto-déclaré",
    pilier: "GOUVERNANCE",
    codes: ["score_gouvernance_declare"],
  },
];

export function famillesDuPilier(pilier: Pillar): Famille[] {
  return [
    ...FAMILLES.filter((f) => f.pilier === pilier),
    { slug: FAMILLE_AUTRES, libelle: "Autres indicateurs", pilier, codes: [] },
  ];
}

export function familleDuCode(pilier: Pillar, code: string): string {
  return (
    FAMILLES.find((f) => f.pilier === pilier && f.codes.includes(code))?.slug ?? FAMILLE_AUTRES
  );
}

export function pilierDuCode(code: string): Pillar | null {
  return FAMILLES.find((f) => f.codes.includes(code))?.pilier ?? null;
}

export function libelleFamille(pilier: Pillar, slug: string | undefined): string | null {
  return famillesDuPilier(pilier).find((f) => f.slug === slug)?.libelle ?? null;
}
