import type { Pillar } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { pilierDuCode } from "../esg/taxonomie";
import type { MetriqueVue } from "../esg/vueMetrique";

/** Trouvés / attendus d'un pilier : les valeurs présentes, plus les codes que le serveur
 * déclare manquants (coverage.missing_codes) et que la taxonomie range dans ce pilier. */
export function resumePilier(
  metriques: readonly MetriqueVue[],
  manquants: readonly string[],
  pilier: Pillar,
) {
  const trouves = metriques.filter((m) => m.pilier === pilier).length;
  const absents = manquants.filter((code) => pilierDuCode(code) === pilier).length;
  return { trouves, attendus: trouves + absents };
}
