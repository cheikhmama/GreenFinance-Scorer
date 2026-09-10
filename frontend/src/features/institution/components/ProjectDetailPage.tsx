import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { useAssignResearcher, useCloseProject, useMyResearchers, useProjectDetail } from "../api";

export function ProjectDetailPage() {
  const { projetId = "" } = useParams();
  const { data: projet, isLoading, isError } = useProjectDetail(projetId);
  const { data: chercheursAcceptes } = useMyResearchers("ACCEPTE");
  const assigner = useAssignResearcher(projetId);
  const cloturer = useCloseProject(projetId);
  const [chercheurASelectionner, setChercheurASelectionner] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !projet) return <p className="text-destructive">Projet introuvable.</p>;

  const dejaAffectes = new Set(projet.affectations.map((a) => a.chercheur_id));
  const candidats = (chercheursAcceptes ?? []).filter((r) => !dejaAffectes.has(r.chercheur_id));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title={projet.nom}
        description={projet.description ?? "Aucune description."}
        action={
          <div className="flex items-center gap-2">
            <Badge variant={variantStatutProjet(projet.statut)}>{libelleStatutProjet(projet.statut)}</Badge>
            {projet.statut === "OUVERT" ? (
              <Button
                variant="outline"
                size="sm"
                disabled={cloturer.isPending}
                onClick={() => {
                  if (window.confirm("Clôturer ce projet ? Aucune nouvelle affectation ne sera possible.")) {
                    cloturer.mutate();
                  }
                }}
              >
                Clôturer
              </Button>
            ) : null}
          </div>
        }
      />
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-brand-blue">Chercheurs affectés</CardTitle>
          {projet.statut === "OUVERT" && candidats.length > 0 ? (
            <div className="flex items-center gap-2">
              <Select
                value={chercheurASelectionner}
                onChange={(event) => setChercheurASelectionner(event.target.value)}
                className="w-56"
              >
                <option value="">Sélectionner un chercheur accepté...</option>
                {candidats.map((rattachement) => (
                  <option key={rattachement.chercheur_id} value={rattachement.chercheur_id}>
                    {rattachement.chercheur_id}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                disabled={!chercheurASelectionner || assigner.isPending}
                onClick={() =>
                  assigner.mutate(
                    { chercheur_id: chercheurASelectionner },
                    {
                      onSuccess: () => setChercheurASelectionner(""),
                      onError: (error) =>
                        setErreur(error instanceof ApiError ? error.message : "Échec de l'affectation."),
                    },
                  )
                }
              >
                Affecter
              </Button>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          {projet.affectations.length === 0 ? (
            <p className="text-sm text-brand-grey">Aucun chercheur affecté pour l'instant.</p>
          ) : (
            projet.affectations.map((affectation) => (
              <div key={affectation.id} className="flex items-center justify-between border-b py-2 text-sm last:border-0">
                <span>{affectation.chercheur_email}</span>
                <span className="text-brand-grey">
                  depuis le {new Date(affectation.date_affectation).toLocaleDateString("fr-FR")}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Analyses reçues</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {projet.analyses.length === 0 ? (
            <p className="text-sm text-brand-grey">Aucune analyse soumise pour l'instant.</p>
          ) : (
            projet.analyses.map((analyse) => (
              <Link
                key={analyse.id}
                to={`/institution/analyses/${analyse.id}`}
                className="flex items-center justify-between border-b py-2 text-sm last:border-0 hover:bg-slate-50"
              >
                <span className="font-medium text-brand-blue">
                  {analyse.titre} (v{analyse.version})
                </span>
                <Badge variant={variantStatutAnalyse(analyse.statut)}>
                  {libelleStatutAnalyse(analyse.statut)}
                </Badge>
              </Link>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
