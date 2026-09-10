import { useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Textarea } from "@/shared/ui/textarea";
import {
  exportAnalysisFile,
  useAnalysisDetailForInstitution,
  useApproveAnalysis,
  useRequestAnalysisCorrection,
} from "../api";

export function AnalyseDetailPage() {
  const { analyseId = "" } = useParams();
  const { data: analyse, isLoading, isError } = useAnalysisDetailForInstitution(analyseId);
  const valider = useApproveAnalysis(analyseId, analyse?.projet_id ?? "");
  const demanderCorrection = useRequestAnalysisCorrection(analyseId, analyse?.projet_id ?? "");
  const [commentaire, setCommentaire] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [exportEnCours, setExportEnCours] = useState(false);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !analyse) return <p className="text-destructive">Analyse introuvable.</p>;

  const enAttenteDeDecision = analyse.statut === "SOUMISE";
  const decidee = analyse.statut === "VALIDEE" || analyse.statut === "CORRECTION_DEMANDEE";
  const enCours = valider.isPending || demanderCorrection.isPending;

  async function lancerExport() {
    if (!analyse) return;
    setErreur(null);
    setExportEnCours(true);
    try {
      await exportAnalysisFile(analyse.id, analyse.titre);
    } catch (error) {
      setErreur(error instanceof ApiError ? error.message : "Échec de l'export.");
    } finally {
      setExportEnCours(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Version ${analyse.version}`}
        title={analyse.titre}
        description={`${analyse.entreprise_ids.length} entreprise(s) comparée(s).`}
        action={<Badge variant={variantStatutAnalyse(analyse.statut)}>{libelleStatutAnalyse(analyse.statut)}</Badge>}
      />

      {analyse.commentaire_institution ? (
        <Alert>
          <AlertTitle>Votre dernier commentaire</AlertTitle>
          <AlertDescription>{analyse.commentaire_institution}</AlertDescription>
        </Alert>
      ) : null}
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Contenu</CardTitle>
        </CardHeader>
        <CardContent className="whitespace-pre-wrap text-sm text-brand-grey">{analyse.contenu}</CardContent>
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
                    { commentaire: commentaire || undefined },
                    {
                      onError: (error) =>
                        setErreur(error instanceof ApiError ? error.message : "Échec de la validation."),
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
                    { commentaire },
                    {
                      onError: (error) =>
                        setErreur(error instanceof ApiError ? error.message : "Échec de la demande de correction."),
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
