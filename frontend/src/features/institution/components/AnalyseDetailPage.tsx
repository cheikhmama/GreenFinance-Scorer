import { Building2 } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { BackLink } from "@/shared/ui/back-link";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Textarea } from "@/shared/ui/textarea";
import {
  exportAnalysisFile,
  useAnalysisDetailForInstitution,
  useAnalysisHistoryForInstitution,
  useApproveAnalysis,
  useCompanyDetailForInstitution,
  useRequestAnalysisCorrection,
} from "../api";

export function AnalyseDetailPage() {
  const { analyseId = "" } = useParams();
  const { data: analyse, isLoading, isError } = useAnalysisDetailForInstitution(analyseId);
  const valider = useApproveAnalysis(analyseId, analyse?.project_id ?? "");
  const demanderCorrection = useRequestAnalysisCorrection(analyseId, analyse?.project_id ?? "");
  const [commentaire, setCommentaire] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [exportEnCours, setExportEnCours] = useState(false);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !analyse) return <p className="text-destructive">Analyse introuvable.</p>;

  const enAttenteDeDecision = analyse.status === "SOUMISE";
  const decidee = analyse.status === "VALIDEE" || analyse.status === "CORRECTION_DEMANDEE";
  const enCours = valider.isPending || demanderCorrection.isPending;

  async function lancerExport() {
    if (!analyse) return;
    setErreur(null);
    setExportEnCours(true);
    try {
      await exportAnalysisFile(analyse.id, analyse.title);
    } catch (error) {
      setErreur(error instanceof ApiError ? error.message : "Échec de l'export.");
    } finally {
      setExportEnCours(false);
    }
  }

  return (
    <div className="space-y-6">
      <BackLink to="/institution/analyses">Analyses</BackLink>
      <PageHeader
        title={analyse.title}
        description={`Version ${analyse.version} — ${analyse.company_ids.length} entreprise(s) comparée(s).`}
        action={
          <Badge variant={variantStatutAnalyse(analyse.status)}>
            {libelleStatutAnalyse(analyse.status)}
          </Badge>
        }
      />

      <HistoriqueVersions analyseId={analyse.id} versionActuelle={analyse.version} />

      {analyse.institution_comment ? (
        <Alert>
          <AlertTitle>Votre dernier commentaire</AlertTitle>
          <AlertDescription>{analyse.institution_comment}</AlertDescription>
        </Alert>
      ) : null}
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Building2 className="size-4" />
            Entreprises comparées
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {analyse.company_ids.map((entrepriseId) => (
            <EntrepriseComparee key={entrepriseId} entrepriseId={entrepriseId} />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Contenu</CardTitle>
        </CardHeader>
        <CardContent className="whitespace-pre-wrap text-sm text-brand-grey">
          {analyse.content}
        </CardContent>
      </Card>

      {enAttenteDeDecision ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-brand-blue">Décision</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              rows={3}
              placeholder="Commentaire (requis pour demander une correction)"
              value={commentaire}
              onChange={(event) => setCommentaire(event.target.value)}
            />
            <div className="flex gap-2">
              <Button
                disabled={enCours}
                onClick={() =>
                  valider.mutate(
                    { comment: commentaire || undefined },
                    {
                      onError: (error) =>
                        setErreur(
                          error instanceof ApiError ? error.message : "Échec de la validation.",
                        ),
                    },
                  )
                }
              >
                {valider.isPending ? "Validation..." : "Valider"}
              </Button>
              <Button
                variant="outline"
                disabled={enCours || commentaire.trim().length === 0}
                onClick={() =>
                  demanderCorrection.mutate(
                    { comment: commentaire },
                    {
                      onError: (error) =>
                        setErreur(
                          error instanceof ApiError
                            ? error.message
                            : "Échec de la demande de correction.",
                        ),
                    },
                  )
                }
              >
                {demanderCorrection.isPending ? "Envoi..." : "Demander une correction"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {decidee ? (
        <Button variant="outline" disabled={exportEnCours} onClick={lancerExport}>
          {exportEnCours ? "Export..." : "Exporter en CSV"}
        </Button>
      ) : null}
    </div>
  );
}

function EntrepriseComparee({ entrepriseId }: { entrepriseId: string }) {
  const { data: entreprise, isLoading } = useCompanyDetailForInstitution(entrepriseId);

  if (isLoading || !entreprise) {
    return <div className="h-10 animate-pulse rounded-md bg-muted" />;
  }

  return (
    <Link
      to={`/institution/entreprises/${entrepriseId}`}
      className="flex items-center gap-3 rounded-md border p-2 text-sm transition hover:border-brand-green"
    >
      <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-8" />
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-brand-blue">{entreprise.name}</p>
        <p className="truncate text-xs text-brand-grey">{entreprise.sector}</p>
      </div>
    </Link>
  );
}

/** Reconstruit la chaîne complète v1 -> correction -> v2 -> ... -> validation finale (voir
 * app/researcher/analyses.py::lister_versions) — n'affiche rien si l'analyse n'a qu'une seule
 * version, l'historique n'apportant alors aucune information. */
function HistoriqueVersions({
  analyseId,
  versionActuelle,
}: {
  analyseId: string;
  versionActuelle: number;
}) {
  const { data: versions } = useAnalysisHistoryForInstitution(analyseId);

  if (!versions || versions.length <= 1) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-brand-blue">Historique des versions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {versions.map((version) => (
          <div
            key={version.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <span
                className={
                  version.version === versionActuelle
                    ? "font-semibold text-brand-blue"
                    : "text-brand-grey"
                }
              >
                Version {version.version}
              </span>
              {version.version === versionActuelle ? (
                <span className="text-xs text-brand-grey">(consultée)</span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={variantStatutAnalyse(version.status)}>
                {libelleStatutAnalyse(version.status)}
              </Badge>
              {version.id !== analyseId ? (
                <Link
                  to={`/institution/analyses/${version.id}`}
                  className="text-brand-green underline-offset-2 hover:underline"
                >
                  Consulter
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
