import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { Link, Navigate, Outlet, useParams } from "react-router-dom";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { libellePilier } from "@/shared/format/indicateurs";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Card, CardContent } from "@/shared/ui/card";
import { rapportQueryOptions } from "../api";
import { PILIERS } from "../esg/taxonomie";
import { metriquesDuRapport } from "../esg/vueMetrique";
import { etapeReprise } from "../session/etat";
import { LockBanner } from "../session/LockBanner";
import { FormulaireCorrection } from "./FormulaireCorrection";
import { resumePilier } from "./resume";
import { arrondi, ScoreOfficiel } from "./ScoreOfficiel";

const DECISIONS = ["VALIDATED", "REJECTED", "REVISION_REQUESTED"];

/** Niveau 3, vue d'ensemble (spec §2.2) : verrouillage, score, puis un accès par pilier — les
 * valeurs elles-mêmes sont au niveau 4. Un brouillon n'a rien à survoler : il reprend à l'étape
 * de l'assistant où il s'était arrêté. */
export function OverviewPage() {
  const { rapportId: segment = "" } = useParams();
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  if (!rapport) return null; // DeclarationLayout gère chargement et erreur.
  if (rapport.submitted_at === null) {
    return <Navigate to={`brouillon/${etapeReprise(rapport)}`} replace />;
  }

  const metriques = metriquesDuRapport(rapport);
  return (
    <div className="space-y-6">
      {/* Cause affichée seulement tant que l'échec est l'état courant du rapport. */}
      {rapport.extraction_error && rapport.status === "EXTRACTION_FAILED" ? (
        <Alert variant="destructive">
          <AlertTitle>Échec de la lecture du fichier</AlertTitle>
          <AlertDescription>{libelleCauseExtraction(rapport.extraction_error)}</AlertDescription>
        </Alert>
      ) : null}
      {rapport.submitted_at ? (
        <LockBanner
          submittedAt={rapport.submitted_at}
          checksum={rapport.checksum_sha256}
          close={DECISIONS.includes(rapport.status)}
        />
      ) : null}
      {rapport.status === "VALIDATED" && rapport.official_score ? (
        <ScoreOfficiel score={rapport.official_score} />
      ) : null}
      {rapport.declared_global_score !== null ? (
        <p className="text-sm text-muted-foreground">
          Score ESG global auto-déclaré dans le rapport :{" "}
          <strong className="text-foreground">{arrondi(rapport.declared_global_score)}/100</strong>{" "}
          — affiché séparément, il n’entre pas dans le score calculé.
        </p>
      ) : null}
      {rapport.status === "REVISION_REQUESTED" ? (
        <FormulaireCorrection rapportId={rapport.id} exercice={rapport.fiscal_year} />
      ) : null}
      <ul className="grid gap-4 sm:grid-cols-3">
        {PILIERS.map(({ slug, pilier }) => {
          const { trouves, attendus } = resumePilier(
            metriques,
            rapport.coverage.missing_codes,
            pilier,
          );
          return (
            <li key={slug}>
              <Card className="h-full py-4">
                <CardContent className="px-4">
                  <Link
                    to={slug}
                    className="flex items-center justify-between gap-3 rounded-md focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span>
                      <span className="block font-semibold text-foreground">
                        {libellePilier(pilier)}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {trouves}/{attendus} indicateur(s) trouvé(s)
                      </span>
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                  </Link>
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
      <Outlet />
    </div>
  );
}
