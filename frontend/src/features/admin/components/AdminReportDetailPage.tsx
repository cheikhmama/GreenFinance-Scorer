import { Cloud, FileCheck2, FileText, History, MessageSquare } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { CompanyIdentity } from "@/shared/esg/CompanyAvatar";
import { libelleDecisionAudit } from "@/shared/format/decisionAudit";
import { formatPourcentage } from "@/shared/format/etatPosition";
import {
  libelleDateRapport,
  libelleStatutRapport,
  variantStatutRapport,
} from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { Textarea } from "@/shared/ui/textarea";
import {
  useAdminReport,
  useCompanyDetail,
  useRecalculateReportScore,
  useRejectReport,
  useReportOpinions,
  useReportScoreVerification,
  useReportVersions,
  useRequestReportCorrection,
  useValidateReport,
} from "../api";

/** Fiche de détail Admin d'un rapport — identité de l'entreprise toujours visible en tête (on
 * arrive ici depuis plusieurs points de la plateforme : file d'affectation, file de décision,
 * fiche entreprise ; sans ce bandeau, rien ne rappelle de quelle entreprise il s'agit une fois
 * sur la page). Le reste (indicateurs, carbone, avis, versions, décision) reprend les mêmes
 * données qu'avant, seulement réorganisé avec des repères visuels cohérents avec le reste de la
 * plateforme (icônes de section, cartes). */
export function AdminReportDetailPage() {
  const { rapportId } = useParams<{ rapportId: string }>();
  const { data: rapport, isLoading, isError } = useAdminReport(rapportId ?? "");
  const { data: entreprise } = useCompanyDetail(rapport?.company_id ?? "");
  const { data: avis } = useReportOpinions(rapportId ?? "");
  const { data: versions } = useReportVersions(rapportId ?? "");

  if (isLoading) {
    return (
      <div className="space-y-8 p-8">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
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
    <div className="space-y-8">
      <div>
        <Link to="/admin" className="text-sm text-brand-green underline underline-offset-2">
          ← Tableau de bord
        </Link>
      </div>

      <PageHeader
        eyebrow="Administration"
        title={`Rapport ${rapport.type} — ${rapport.fiscal_year ?? "année inconnue"}`}
        description="Indicateurs extraits, données carbone, avis d'audit et décision."
        action={
          <Button asChild variant="outline">
            <a
              href={`/api/v1/admin/rapports/${rapport.id}/fichier`}
              target="_blank"
              rel="noreferrer"
            >
              <FileText className="size-4" />
              Voir le PDF original
            </a>
          </Button>
        }
      />

      <Card className="shadow-none">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
          {entreprise ? (
            <Link to={`/admin/entreprises/${entreprise.id}`} className="hover:opacity-80">
              <CompanyIdentity
                nom={entreprise.name}
                logo={entreprise.logo}
                secteur={`${entreprise.sector} — ${entreprise.country}`}
                avatarClassName="size-12"
              />
            </Link>
          ) : (
            <span className="text-sm text-brand-grey">Entreprise…</span>
          )}
          <Badge variant={variantStatutRapport(rapport.status)}>
            {libelleStatutRapport(rapport.status)}
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <MessageSquare className="size-4" />
            Avis d'audit
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!avis || avis.length === 0 ? (
            <EmptyState icon={MessageSquare} message="Aucun avis rendu pour l'instant." />
          ) : (
            <ul className="divide-y">
              {avis.map((item) => (
                <li key={item.id} className="py-3">
                  <p className="font-medium text-brand-blue">
                    {libelleDecisionAudit(item.decision)}
                  </p>
                  {item.comment ? (
                    <p className="text-sm text-brand-grey">{item.comment}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <FileText className="size-4" />
            Indicateurs ESG
          </CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.declared_global_score !== null ? (
            <p className="mb-3 text-sm">
              Score ESG global auto-déclaré par l'entreprise :{" "}
              <strong className="text-brand-blue">{rapport.declared_global_score}/100</strong>
              {rapport.declared_global_score_proof ? (
                <span className="text-brand-grey">
                  {" "}
                  — {rapport.declared_global_score_proof.document_name} — p.
                  {rapport.declared_global_score_proof.page_start}
                </span>
              ) : null}
            </p>
          ) : null}
          {rapport.metrics.length === 0 ? (
            <EmptyState icon={FileText} message="Aucun indicateur extrait." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pilier</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Valeur</TableHead>
                  <TableHead>Preuve</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rapport.metrics.map((indicateur) => (
                  <TableRow key={indicateur.id}>
                    <TableCell>{indicateur.pillar}</TableCell>
                    <TableCell>{indicateur.metric_code}</TableCell>
                    <TableCell>
                      {indicateur.value} {indicateur.unit}
                    </TableCell>
                    <TableCell className="text-brand-grey">
                      {indicateur.proof.document_name} — p.{indicateur.proof.page_start}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Cloud className="size-4" />
            Émissions carbone (Scope 1/2/3)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {rapport.carbon_data.length === 0 ? (
            <EmptyState icon={Cloud} message="Aucune donnée carbone extraite." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scope</TableHead>
                  <TableHead>Catégorie GES</TableHead>
                  <TableHead>Valeur (tCO2e)</TableHead>
                  <TableHead>Année</TableHead>
                  <TableHead>Qualité PCAF</TableHead>
                  <TableHead>Preuve</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rapport.carbon_data.map((donnee) => (
                  <TableRow key={donnee.id}>
                    <TableCell>Scope {donnee.scope}</TableCell>
                    <TableCell>{donnee.ghg_category ?? "—"}</TableCell>
                    <TableCell>{donnee.tonnes_co2e}</TableCell>
                    <TableCell>{donnee.year}</TableCell>
                    <TableCell>
                      {donnee.pcaf_data_quality != null ? `${donnee.pcaf_data_quality}/5` : "—"}
                    </TableCell>
                    <TableCell className="text-brand-grey">
                      {donnee.proof.document_name} — p.{donnee.proof.page_start}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <History className="size-4" />
            Historique des versions
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!versions || versions.length <= 1 ? (
            <EmptyState icon={History} message="Aucune version antérieure ou ultérieure." />
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
                      {libelleStatutRapport(version.status)} —{" "}
                      {libelleDateRapport(version).toLowerCase()}
                    </p>
                  </div>
                  {version.id !== rapport.id ? (
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/admin/rapports/${version.id}`}>Ouvrir</Link>
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {rapport.status === "PENDING_DECISION" ? <FormulaireDecision rapportId={rapport.id} /> : null}
      {rapport.status === "VALIDATED" ? <RecalculerScoreSection rapportId={rapport.id} /> : null}
    </div>
  );
}

/** État incohérent, normalement inatteignable via le parcours normal (valider_rapport calcule
 * toujours un score dans la même transaction) mais qui peut survenir sur des données historiques
 * — sans quoi la publication de l'entreprise resterait bloquée indéfiniment sans recours (voir
 * app/admin/review_queue.py::recalculer_score, BUG-020). */
function RecalculerScoreSection({ rapportId }: { rapportId: string }) {
  const recalculer = useRecalculateReportScore(rapportId);
  const [error, setError] = useState<string | null>(null);

  if (recalculer.isSuccess) {
    return (
      <Alert>
        <AlertTitle>Score recalculé</AlertTitle>
        <AlertDescription>
          Valeur globale : {recalculer.data.global_score}/100.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="shadow-none">
      <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
        <div>
          <p className="text-sm font-medium text-brand-blue">Score manquant sur ce rapport validé ?</p>
          <p className="text-sm text-brand-grey">
            À utiliser uniquement si l'entreprise reste bloquée en publication faute de score.
          </p>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>
        <Button
          variant="outline"
          disabled={recalculer.isPending}
          onClick={() => {
            setError(null);
            recalculer.mutate(undefined, {
              onError: (err) => {
                setError(
                  err instanceof ApiError ? err.message : "Le score n'a pas pu être recalculé.",
                );
              },
            });
          }}
        >
          {recalculer.isPending ? "Recalcul..." : "Recalculer le score"}
        </Button>
      </CardContent>
    </Card>
  );
}

function FormulaireDecision({ rapportId }: { rapportId: string }) {
  const validate = useValidateReport(rapportId);
  const reject = useRejectReport(rapportId);
  const requestCorrection = useRequestReportCorrection(rapportId);
  const { data: verificationScore } = useReportScoreVerification(rapportId, true);
  const confirm = useConfirm();
  const [commentaire, setCommentaire] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pending = validate.isPending || reject.isPending || requestCorrection.isPending;
  const succeeded = validate.isSuccess || reject.isSuccess || requestCorrection.isSuccess;

  function surErreur(err: unknown) {
    setError(err instanceof ApiError ? err.message : "La décision n'a pas pu être enregistrée.");
  }

  async function rejeter() {
    const confirme = await confirm({
      title: "Rejeter ce rapport ?",
      description:
        "L'entreprise sera notifiée du rejet. Cette décision reste consultable dans l'historique du rapport.",
      confirmLabel: "Rejeter",
      destructive: true,
    });
    if (!confirme) return;
    setError(null);
    reject.mutate({ comment: commentaire || null }, { onError: surErreur });
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
        <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
          <FileCheck2 className="size-4" />
          Décision
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        {verificationScore?.computable === false ? (
          <Alert variant="destructive">
            <AlertTitle>Score non calculable</AlertTitle>
            <AlertDescription>
              {verificationScore.coverage_rate != null &&
              verificationScore.min_coverage != null
                ? `Couverture des indicateurs de ${formatPourcentage(verificationScore.coverage_rate * 100)}, sous le minimum de ${formatPourcentage(verificationScore.min_coverage * 100)} exigé par la méthodologie — valider échouera.`
                : "Le vocabulaire d'indicateurs de ce rapport ne recoupe aucun indicateur de la méthodologie de référence — valider échouera tant que ce n'est pas résolu."}
            </AlertDescription>
          </Alert>
        ) : null}
        {verificationScore?.computable && verificationScore.coverage_rate != null ? (
          <p className="text-sm text-brand-grey">
            Couverture des indicateurs de la méthodologie :{" "}
            {formatPourcentage(verificationScore.coverage_rate * 100)}.
          </p>
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
              validate.mutate({ comment: commentaire || null }, { onError: surErreur });
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
                { comment: commentaire || null },
                { onError: surErreur },
              );
            }}
          >
            Demander une correction
          </Button>
          <Button variant="destructive" disabled={pending} onClick={rejeter}>
            Rejeter
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
