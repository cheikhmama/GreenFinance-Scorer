import { NavLink } from "react-router-dom";
import type {
  Pillar,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libellePilier } from "@/shared/format/indicateurs";
import { cn } from "@/shared/ui/cn";
import { PILIERS } from "../esg/taxonomie";
import { metriquesDuRapport } from "../esg/vueMetrique";
import { resumePilier } from "./resume";

function sousScore(rapport: RapportESGDetail, pilier: Pillar): number | null {
  const score = rapport.official_score;
  if (!score) return null;
  return {
    ENVIRONNEMENT: score.environmental_score,
    SOCIAL: score.social_score,
    GOUVERNANCE: score.governance_score,
  }[pilier];
}

const lien = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm",
    isActive ? "bg-secondary font-medium text-foreground" : "text-muted-foreground hover:bg-muted",
  );

/** Rail d'une déclaration soumise (spec §2.2) : synthèse, puis un lien par pilier avec son
 * sous-score (une fois validée) et ses indicateurs trouvés / attendus. */
export function RailDeclaration({ rapport }: { rapport: RapportESGDetail }) {
  const metriques = metriquesDuRapport(rapport);
  return (
    <ul className="space-y-1">
      <li>
        <NavLink to="." end className={lien}>
          Vue d’ensemble
        </NavLink>
      </li>
      {PILIERS.map(({ slug, pilier }) => {
        const { trouves, attendus } = resumePilier(
          metriques,
          rapport.coverage.missing_codes,
          pilier,
        );
        const score = sousScore(rapport, pilier);
        return (
          <li key={slug}>
            <NavLink to={slug} className={lien}>
              <span>{libellePilier(pilier)}</span>
              <span className="text-xs tabular-nums text-muted-foreground">
                {score !== null ? `${Math.round(score)}/100 · ` : ""}
                {trouves}/{attendus}
              </span>
            </NavLink>
          </li>
        );
      })}
    </ul>
  );
}
