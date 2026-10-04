import type {
  MetricReviewStatus,
  PreuveDocumentairePublic,
  ProofBox,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleIndicateur, libellePilier, libelleScope } from "@/shared/format/indicateurs";

/** Une valeur à revoir dans l'espace de travail de l'Auditeur (tâche 5.7) : un indicateur ESG ou une
 * donnée carbone, sous une forme commune pour la liste, le visualiseur et le panneau de détail. */
export interface ValeurARevoir {
  cle: string;
  type: "metric" | "emission";
  id: string;
  libelle: string;
  groupe: string;
  valeur: number;
  unite: string;
  brute: string | null;
  citation: string | null;
  section: string | null;
  annee: number | null;
  confiance: string | null;
  preuve: PreuveDocumentairePublic;
  boites: ProofBox[];
  statut: MetricReviewStatus;
  valeurAuditee: number | null;
}

const ORDRE_GROUPES = ["Carbone", "Environnement", "Social", "Gouvernance"];

/** Valeurs du dossier dans l'ordre de revue : données carbone, puis indicateurs par pilier. */
export function valeursARevoir(dossier: RapportESGDetail): ValeurARevoir[] {
  const emissions: ValeurARevoir[] = dossier.carbon_data.map((d) => ({
    cle: `emission:${d.id}`,
    type: "emission",
    id: d.id,
    libelle: libelleScope(d.scope, d.ghg_category),
    groupe: "Carbone",
    valeur: d.tonnes_co2e,
    unite: "tCO2e",
    brute: d.raw_value,
    citation: d.proof_text,
    section: d.section,
    annee: d.value_year ?? d.year,
    confiance: d.confidence,
    preuve: d.proof,
    boites: d.proof_boxes ?? [],
    statut: d.review_status ?? "PENDING",
    valeurAuditee: d.audited_value ?? null,
  }));
  const indicateurs: ValeurARevoir[] = dossier.metrics.map((m) => ({
    cle: `metric:${m.id}`,
    type: "metric",
    id: m.id,
    libelle: libelleIndicateur(m.metric_code),
    groupe: libellePilier(m.pillar),
    valeur: m.value,
    unite: m.unit,
    brute: m.raw_value,
    citation: m.proof_text,
    section: m.section,
    annee: m.value_year,
    confiance: m.confidence,
    preuve: m.proof,
    boites: m.proof_boxes ?? [],
    statut: m.review_status ?? "PENDING",
    valeurAuditee: m.audited_value ?? null,
  }));
  return [...emissions, ...indicateurs].sort(
    (a, b) =>
      ORDRE_GROUPES.indexOf(a.groupe) - ORDRE_GROUPES.indexOf(b.groupe) ||
      a.libelle.localeCompare(b.libelle),
  );
}

/** Index de la prochaine valeur encore à revoir après `depuis` (en bouclant), ou `depuis` s'il
 * n'en reste aucune. */
export function prochaineARevoir(valeurs: ValeurARevoir[], depuis: number): number {
  for (let pas = 1; pas <= valeurs.length; pas += 1) {
    const index = (depuis + pas) % valeurs.length;
    if (valeurs[index]?.statut === "PENDING") return index;
  }
  return depuis;
}
