import { describe, expect, it } from "vitest";
import type {
  DonneeCarboneDetail,
  IndicateurESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  FAMILLE_AUTRES,
  familleDuCode,
  famillesDuPilier,
  pilierDepuisSlug,
  pilierDuCode,
} from "./taxonomie";
import {
  CLES_METRIQUE_VUE,
  libellePreuveVue,
  metriquesDuRapport,
  vueCarbone,
  vueIndicateur,
} from "./vueMetrique";

/** Codes cibles de l'extraction (app/ingestion/cibles.py) — à tenir à jour avec ce fichier. */
const CODES_CONNUS: Record<string, string> = {
  scope_1: "ENVIRONNEMENT",
  scope_2: "ENVIRONNEMENT",
  scope_2_market_based: "ENVIRONNEMENT",
  scope_2_location_based: "ENVIRONNEMENT",
  scope_3: "ENVIRONNEMENT",
  intensite_scope_1_2_marketbased: "ENVIRONNEMENT",
  intensite_scope_1_2_3_hors_cat11: "ENVIRONNEMENT",
  intensite_scope_1_2_3_total: "ENVIRONNEMENT",
  part_renouvelable_pourcentage: "ENVIRONNEMENT",
  dechets_valorises_pourcentage: "ENVIRONNEMENT",
  score_environnement_declare: "ENVIRONNEMENT",
  effectif_total: "SOCIAL",
  femmes_effectif_pourcentage: "SOCIAL",
  femmes_management_pourcentage: "SOCIAL",
  deces_professionnels: "SOCIAL",
  taux_frequence_accidents: "SOCIAL",
  heures_formation_par_employe: "SOCIAL",
  score_social_declare: "SOCIAL",
  taille_conseil: "GOUVERNANCE",
  administrateurs_independants_pourcentage: "GOUVERNANCE",
  femmes_conseil_pourcentage: "GOUVERNANCE",
  score_gouvernance_declare: "GOUVERNANCE",
};

const SENTINELLE = "SENTINELLE-NE-DOIT-PAS-FUIR";

const preuve = {
  id: "p1",
  document_name: "rapport-2025.pdf",
  year: 2025,
  total_pages: 80,
  page_start: 41,
  page_end: 42,
  excerpt_pdf_path: `/stockage/${SENTINELLE}.pdf`,
};

function indicateur(surcharges: Partial<IndicateurESGDetail> = {}): IndicateurESGDetail {
  return {
    id: "i1",
    pillar: "GOUVERNANCE",
    metric_code: "taille_conseil",
    value: 12,
    unit: "count",
    method: "RAPPORTEE",
    proof: preuve,
    raw_value: SENTINELLE,
    section: SENTINELLE,
    proof_text: SENTINELLE,
    value_year: 2025,
    confidence: "ELEVE",
    proof_boxes: [{ page: 41, x0: 0, y0: 0, x1: 1, y1: 1, sentinelle: SENTINELLE } as never],
    review_status: "ACCEPTED",
    audited_value: null,
    ...surcharges,
  };
}

function carbone(surcharges: Partial<DonneeCarboneDetail> = {}): DonneeCarboneDetail {
  return {
    id: "c1",
    scope: 2,
    ghg_category: "market_based",
    tonnes_co2e: 1500,
    year: 2025,
    method: "RAPPORTEE",
    pcaf_data_quality: null,
    proof: preuve,
    raw_value: SENTINELLE,
    section: SENTINELLE,
    proof_text: SENTINELLE,
    value_year: 2025,
    confidence: null,
    review_status: null,
    audited_value: null,
    ...surcharges,
  };
}

describe("taxonomie", () => {
  it.each(Object.entries(CODES_CONNUS))("%s → une famille nommée de son pilier", (code, pilier) => {
    expect(pilierDuCode(code)).toBe(pilier);
    expect(familleDuCode(pilier as never, code)).not.toBe(FAMILLE_AUTRES);
  });

  it("chaque code connu est dans une seule famille", () => {
    for (const pilier of ["ENVIRONNEMENT", "SOCIAL", "GOUVERNANCE"] as const) {
      const codes = famillesDuPilier(pilier).flatMap((f) => f.codes);
      expect(new Set(codes).size).toBe(codes.length);
    }
  });

  it("un code inconnu tombe dans « Autres indicateurs », jamais perdu", () => {
    expect(familleDuCode("SOCIAL", "nouveau_code_2027")).toBe(FAMILLE_AUTRES);
    expect(pilierDuCode("nouveau_code_2027")).toBeNull();
    expect(famillesDuPilier("SOCIAL").at(-1)).toMatchObject({ slug: FAMILLE_AUTRES });
  });

  it("slugs de pilier", () => {
    expect(pilierDepuisSlug("environnement")).toBe("ENVIRONNEMENT");
    expect(pilierDepuisSlug("ENVIRONNEMENT")).toBeNull();
    expect(pilierDepuisSlug(undefined)).toBeNull();
  });
});

describe("MetriqueVue — liste blanche", () => {
  it("n’a que les clés prévues", () => {
    expect(Object.keys(vueIndicateur(indicateur())).sort()).toEqual([...CLES_METRIQUE_VUE].sort());
    expect(Object.keys(vueCarbone(carbone())).sort()).toEqual([...CLES_METRIQUE_VUE].sort());
  });

  it("ne recopie aucun texte d’extraction ni chemin de stockage", () => {
    const vues = metriquesDuRapport({ metrics: [indicateur()], carbon_data: [carbone()] });
    expect(JSON.stringify(vues)).not.toContain(SENTINELLE);
  });

  it("place une ligne carbone par scope et méthode", () => {
    expect(vueCarbone(carbone())).toMatchObject({
      cle: "scope_2_market_based",
      pilier: "ENVIRONNEMENT",
      famille: "emissions-ges",
      valeur: 1500,
      unite: "tCO2e",
      periode: 2025,
    });
    expect(vueCarbone(carbone({ scope: 1, ghg_category: null })).cle).toBe("scope_1");
  });

  it("garde deux lignes de même scope (catégories différentes) distinctes", () => {
    const vues = metriquesDuRapport({
      metrics: [],
      carbon_data: [
        carbone({ id: "a", scope: 3, ghg_category: "cat1" }),
        carbone({ id: "b", scope: 3, ghg_category: "cat11" }),
      ],
    });
    expect(vues.map((v) => v.id)).toEqual(["a", "b"]);
    expect(new Set(vues.map((v) => v.cle)).size).toBe(2);
  });

  it("libellé de preuve", () => {
    expect(libellePreuveVue({ document: "x", annee: 2025, pageDebut: 41, pageFin: 42 })).toBe(
      "Rapport 2025 — p. 41–42",
    );
    expect(libellePreuveVue({ document: "x", annee: 2025, pageDebut: 7, pageFin: 7 })).toBe(
      "Rapport 2025 — p. 7",
    );
  });
});
