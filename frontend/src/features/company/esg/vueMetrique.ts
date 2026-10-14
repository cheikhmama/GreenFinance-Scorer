import type {
  ConfidenceLevel,
  DataMethod,
  DonneeCarboneDetail,
  IndicateurESGDetail,
  MetricReviewStatus,
  Pillar,
  PreuveDocumentairePublic,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleIndicateur, libelleScope } from "@/shared/format/indicateurs";
import { familleDuCode } from "./taxonomie";

/** Ce qu'un composant de l'espace Entreprise peut afficher d'une valeur extraite (spec §4.1).
 * Liste blanche construite champ par champ — jamais de copie d'objet : un champ ajouté au schéma
 * par le serveur reste invisible tant qu'il n'est pas explicitement repris ici. `proof_text`,
 * `raw_value`, `section`, `proof_boxes` et le chemin de stockage de l'extrait ne sont jamais
 * repris. */
export interface PreuveVue {
  document: string;
  annee: number;
  pageDebut: number;
  pageFin: number;
}

export interface MetriqueVue {
  id: string;
  cle: string;
  libelle: string;
  pilier: Pillar;
  famille: string;
  valeur: number;
  unite: string;
  periode: number | null;
  methode: DataMethod;
  confiance: ConfidenceLevel | null;
  revue: MetricReviewStatus | null;
  valeurAuditee: number | null;
  preuve: PreuveVue;
}

export const CLES_METRIQUE_VUE = [
  "id",
  "cle",
  "libelle",
  "pilier",
  "famille",
  "valeur",
  "unite",
  "periode",
  "methode",
  "confiance",
  "revue",
  "valeurAuditee",
  "preuve",
] as const satisfies readonly (keyof MetriqueVue)[];

function vuePreuve(preuve: PreuveDocumentairePublic): PreuveVue {
  return {
    document: preuve.document_name,
    annee: preuve.year,
    pageDebut: preuve.page_start,
    pageFin: preuve.page_end,
  };
}

export function vueIndicateur(i: IndicateurESGDetail): MetriqueVue {
  return {
    id: i.id,
    cle: i.metric_code,
    libelle: libelleIndicateur(i.metric_code),
    pilier: i.pillar,
    famille: familleDuCode(i.pillar, i.metric_code),
    valeur: i.value,
    unite: i.unit,
    periode: i.value_year,
    methode: i.method,
    confiance: i.confidence,
    revue: i.review_status ?? null,
    valeurAuditee: i.audited_value ?? null,
    preuve: vuePreuve(i.proof),
  };
}

/** Une ligne carbone prend le code cible de son scope (`scope_2_market_based`…) ; une autre
 * catégorie (Scope 3 par catégorie) garde une clé distincte. */
function cleCarbone(c: DonneeCarboneDetail): string {
  return c.ghg_category ? `scope_${c.scope}_${c.ghg_category}` : `scope_${c.scope}`;
}

export function vueCarbone(c: DonneeCarboneDetail): MetriqueVue {
  return {
    id: c.id,
    cle: cleCarbone(c),
    libelle: `Émissions ${libelleScope(c.scope, c.ghg_category)}`,
    pilier: "ENVIRONNEMENT",
    famille: "emissions-ges",
    valeur: c.tonnes_co2e,
    unite: "tCO2e",
    periode: c.year,
    methode: c.method,
    confiance: c.confidence,
    revue: c.review_status ?? null,
    valeurAuditee: c.audited_value ?? null,
    preuve: vuePreuve(c.proof),
  };
}

export function metriquesDuRapport(
  rapport: Pick<RapportESGDetail, "metrics" | "carbon_data">,
): MetriqueVue[] {
  return [...rapport.carbon_data.map(vueCarbone), ...rapport.metrics.map(vueIndicateur)];
}

export function libellePreuveVue(preuve: PreuveVue): string {
  const pages =
    preuve.pageDebut === preuve.pageFin
      ? `p. ${preuve.pageDebut}`
      : `p. ${preuve.pageDebut}–${preuve.pageFin}`;
  return `Rapport ${preuve.annee} — ${pages}`;
}
