import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Textarea } from "@/shared/ui/textarea";
import {
  useAdminReport,
  useRejectReport,
  useReportOpinions,
  useReportVersions,
  useRequestReportCorrection,
  useValidateReport,
} from "../api";

export function AdminReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: rapport, isLoading, isError } = useAdminReport(rapportId ?? "");
  const { data: avis } = useReportOpinions(rapportId ?? "");
  const { data: versions } = useReportVersions(rapportId ?? "");

  if (isLoading) return <div className="p-8 text-brand-grey">Chargement...</div>;
  if (isError || !rapport) {
    return (
      <div className="p-8">
        <p className="text-destructive">Rapport introuvable.</p>
        <Link to="/admin" className="text-brand-green underline underline-offset-2">
          Retour au tableau de bord
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/admin" className="text-sm text-brand-green underline underline-offset-2">
          ← Tableau de bord
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-brand-blue">
          Rapport {rapport.type} — {rapport.annee_reporting ?? "année inconnue"}
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Badge variant={variantStatutRapport(rapport.statut)}>
            {libelleStatutRapport(rapport.statut)}
          </Badge>
          <a
            href={`/api/v1/admin/rapports/${rapport.id}/fichier`}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-brand-green underline underline-offset-2"
          >
            Voir le PDF original
          </a>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Avis d'audit</CardTitle>
        </CardHeader>
        <CardContent>
          {!avis || avis.length === 0 ? (
            <p className="text-brand-grey">Aucun avis rendu pour l'instant.</p>
          ) : (
            <ul className="divide-y">
              {avis.map((item) => (
                <li key={item.id} className="py-3">
                  <p className="font-medium text-brand-blue">
                    {libelleDecisionAudit(item.decision)}
                  </p>
                  {item.commentaire ? (
                    <p className="text-sm text-brand-grey">{item.commentaire}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Indicateurs ESG</CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.indicateurs.length === 0 ? (
            <p className="text-brand-grey">Aucun indicateur extrait.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Pilier</th>
                    <th className="py-2 pr-4 font-medium">Code</th>
                    <th className="py-2 pr-4 font-medium">Valeur</th>
                    <th className="py-2 font-medium">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {rapport.indicateurs.map((indicateur) => (
                    <tr key={indicateur.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{indicateur.pilier}</td>
                      <td className="py-2 pr-4">{indicateur.code}</td>
                      <td className="py-2 pr-4">
                        {indicateur.valeur} {indicateur.unite}
                      </td>
                      <td className="py-2 text-brand-grey">
                        {indicateur.preuve.nom_document} — p.{indicateur.preuve.page_debut}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Émissions carbone (Scope 1/2/3)</CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.donnees_carbone.length === 0 ? (
            <p className="text-brand-grey">Aucune donnée carbone extraite.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Scope</th>
                    <th className="py-2 pr-4 font-medium">Catégorie GES</th>
                    <th className="py-2 pr-4 font-medium">Valeur (tCO2e)</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 pr-4 font-medium">Qualité PCAF</th>
                    <th className="py-2 font-medium">Preuve</th>
                  </tr>
                </thead>
                <tbody>
                  {rapport.donnees_carbone.map((donnee) => (
                    <tr key={donnee.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">Scope {donnee.scope}</td>
                      <td className="py-2 pr-4">{donnee.categorie_ges ?? "—"}</td>
                      <td className="py-2 pr-4">{donnee.valeur_tonnes_co2e}</td>
                      <td className="py-2 pr-4">{donnee.annee}</td>
                      <td className="py-2 pr-4">{donnee.score_qualite_pcaf}/5</td>
                      <td className="py-2 text-brand-grey">
                        {donnee.preuve.nom_document} — p.{donnee.preuve.page_debut}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Historique des versions</CardTitle>
        </CardHeader>
        <CardContent>
          {!versions || versions.length <= 1 ? (
            <p className="text-brand-grey">Aucune version antérieure ou ultérieure.</p>
          ) : (
            <ul className="divide-y">
              {versions.map((version) => (
                <li key={version.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium text-brand-blue">
                      Version {version.version}
                      {version.id === rapport.id ? " (celle-ci)" : ""}
                    </p>
                    <p className="text-sm text-brand-grey">
                      {libelleStatutRapport(version.statut)} — déposé le{" "}
                      {new Date(version.date_depot).toLocaleDateString("fr-FR")}
                    </p>
                  </div>
                  {version.id !== rapport.id ? (
                    <Link
                      to={`/admin/rapports/${version.id}`}
                      className="text-sm text-brand-green underline underline-offset-2"
                    >
                      Ouvrir
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {rapport.statut === "EN_VALIDATION" ? <FormulaireDecision rapportId={rapport.id} /> : null}
    </div>
  );
}

function FormulaireDecision({ rapportId }: { rapportId: string }) {
  const validate = useValidateReport(rapportId);
  const reject = useRejectReport(rapportId);
  const requestCorrection = useRequestReportCorrection(rapportId);
  const [commentaire, setCommentaire] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pending = validate.isPending || reject.isPending || requestCorrection.isPending;
  const succeeded = validate.isSuccess || reject.isSuccess || requestCorrection.isSuccess;

  function surErreur(err: unknown) {
    setError(err instanceof ApiError ? err.message : "La décision n'a pas pu être enregistrée.");
  }

  if (succeeded) {
    return (
      <Alert>
        <AlertTitle>Décision enregistrée</AlertTitle>
        <AlertDescription>L'entreprise a été notifiée.</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Décision</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <Textarea
          placeholder="Commentaire (optionnel pour valider, recommandé pour rejeter ou demander une correction)"
          value={commentaire}
          onChange={(event) => setCommentaire(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={pending}
            onClick={() => {
              setError(null);
              validate.mutate({ commentaire: commentaire || null }, { onError: surErreur });
            }}
          >
            Valider
          </Button>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => {
              setError(null);
              requestCorrection.mutate(
                { commentaire: commentaire || null },
                { onError: surErreur },
              );
            }}
          >
            Demander une correction
          </Button>
          <Button
            variant="destructive"
            disabled={pending}
            onClick={() => {
              setError(null);
              reject.mutate({ commentaire: commentaire || null }, { onError: surErreur });
            }}
          >
            Rejeter
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
