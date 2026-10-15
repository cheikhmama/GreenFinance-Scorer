import { useQuery } from "@tanstack/react-query";
import { Download, FileWarning } from "lucide-react";
import { useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { PHASES_DECLARATION, phaseDeclaration } from "@/shared/format/phaseDeclaration";
import { idDepuisSlug } from "@/shared/format/slug";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { MasterDetailLayout } from "@/shared/layout/MasterDetailLayout";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { PhaseProgress } from "@/shared/ui/phase-progress";
import { Skeleton } from "@/shared/ui/skeleton";
import { rapportQueryOptions, useActualisationSurNotification, useReportChecklist } from "../api";
import { etatBrouillon, libelleExercice } from "../session/etat";
import { SubmitDialog } from "../session/SubmitDialog";
import { RailDeclaration } from "./RailDeclaration";
import { StatutDeclaration } from "./StatutDeclaration";

/** Contexte transmis par `<Outlet />` aux pages d'une déclaration. */
export interface ContexteDeclaration {
  ouvrirSoumission: () => void;
}

function Introuvable() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-6 text-center">
        <FileWarning className="size-8 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium text-foreground">Déclaration introuvable</p>
        <p className="text-sm text-muted-foreground">
          Elle a peut-être été abandonnée, ou le lien est incomplet.
        </p>
        <Button asChild variant="outline">
          <Link to="/company/declarations">Retour à mes déclarations</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

/** Niveau 3 (spec §2.2) : en-tête de la déclaration, sa phase, puis rail des piliers + détail.
 * Une seule requête pour tous les niveaux inférieurs (rapportQueryOptions). Le dialogue de
 * soumission est monté ici, hors de la partie qui change de forme à la soumission : le reçu
 * reste affiché quand le brouillon devient une déclaration soumise (la tâche 10 le remplace). */
export function DeclarationLayout() {
  const { rapportId: segment = "", pilier } = useParams();
  const { data: rapport, isPending, error } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  useActualisationSurNotification();
  const [soumissionOuverte, setSoumissionOuverte] = useState(false);
  const etat = rapport ? etatBrouillon(rapport) : null;
  const liste = useReportChecklist(
    rapport?.id ?? "",
    etat === "PRET" ? (rapport?.extraction_finished_at ?? null) : null,
  );

  if (isPending) {
    return (
      <div className="space-y-6" aria-busy="true">
        <Skeleton className="h-14 w-2/3" />
        <Skeleton className="h-8 w-full max-w-xl" />
        <div className="grid gap-6 md:grid-cols-[16rem_1fr]">
          <Skeleton className="h-48" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }
  if (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 403)) {
      return <Introuvable />;
    }
    throw error; // RouteError (errorElement) affiche le message et la référence.
  }

  const phase = phaseDeclaration(rapport);
  const branche =
    phase.branche === null
      ? null
      : {
          libelle: phase.libelle,
          ton: phase.ton === "danger" ? ("danger" as const) : ("attention" as const),
        };
  const contexte: ContexteDeclaration = { ouvrirSoumission: () => setSoumissionOuverte(true) };

  return (
    <div className="space-y-6">
      <PageHeader
        title={titreDeclaration(rapport)}
        description={
          <>
            {libelleExercice(rapport.fiscal_year)} · version {rapport.version}
            {rapport.previous_report_id ? " (correction)" : ""}
            {rapport.original_filename ? ` · ${rapport.original_filename}` : ""}
          </>
        }
        action={
          <>
            <StatutDeclaration rapport={rapport} />
            {rapport.synthesis_available ? (
              <Button asChild variant="outline" size="sm">
                <a href={`/api/v1/company/rapports/${rapport.id}/synthese/fichier`}>
                  <Download aria-hidden="true" />
                  Synthèse PDF
                </a>
              </Button>
            ) : null}
          </>
        }
      />
      <PhaseProgress etapes={PHASES_DECLARATION} courante={phase.index} branche={branche} />
      {/* Un brouillon, même en analyse ou en échec, n’a pas encore de piliers à parcourir. */}
      {rapport.submitted_at === null ? (
        <Outlet context={contexte} />
      ) : (
        <MasterDetailLayout
          railLabel="Sections de la déclaration"
          detailActif={pilier !== undefined}
          rail={<RailDeclaration rapport={rapport} />}
        >
          <Outlet context={contexte} />
        </MasterDetailLayout>
      )}
      <SubmitDialog
        rapport={rapport}
        groupes={liste.data ?? []}
        open={soumissionOuverte}
        onOpenChange={setSoumissionOuverte}
      />
    </div>
  );
}
