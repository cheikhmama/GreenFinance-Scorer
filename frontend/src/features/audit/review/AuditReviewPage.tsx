import { ArrowLeft, ClipboardCheck, Keyboard } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { formatValeur, listeIndicateurs } from "@/shared/format/indicateurs";
import { libelleStatutRevue, variantStatutRevue } from "@/shared/format/revue";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import { useAssignedReport, useAuditPreScore, useAuditReviews, useReviewValue } from "../api";
import { OpinionDialog } from "./OpinionDialog";
import { PdfPageViewer } from "./PdfPageViewer";
import { useRaccourcisRevue } from "./useRaccourcisRevue";
import { type DecisionRevue, type ModeRevue, ValueDetailPanel } from "./ValueDetailPanel";
import { prochaineARevoir, type ValeurARevoir, valeursARevoir } from "./valeurs";

function urlPreuve(rapportId: string, preuveId: string) {
  return `/api/v1/audit/rapports/${rapportId}/preuves/${preuveId}/fichier`;
}

/** Espace de revue de l'Auditeur (tâche 5.7), pleine largeur, en trois volets : la liste des
 * valeurs (25 %), la page-preuve avec la valeur surlignée (45 %), le détail et les décisions (30 %).
 * Clavier : A accepter, E corriger, N non trouvée, J / K valeur suivante / précédente. */
export function AuditReviewPage() {
  const { rapportId = "" } = useParams<{ rapportId: string }>();
  const dossier = useAssignedReport(rapportId);
  const revues = useAuditReviews(rapportId);
  const revoir = useReviewValue(rapportId);
  const [index, setIndex] = useState(0);
  const [mode, setMode] = useState<ModeRevue>("consulter");
  const [erreur, setErreur] = useState<string | null>(null);
  const [avisOuvert, setAvisOuvert] = useState(false);

  const valeurs = useMemo(() => (dossier.data ? valeursARevoir(dossier.data) : []), [dossier.data]);
  const position = Math.min(index, Math.max(valeurs.length - 1, 0));
  const courante: ValeurARevoir | undefined = valeurs[position];
  const modifiable = dossier.data?.status === "IN_AUDIT";
  const avisRendu = dossier.data !== undefined && !modifiable;
  const restantes = valeurs.filter((v) => v.statut === "PENDING").length;
  const preScore = useAuditPreScore(rapportId, avisRendu);

  function aller(nouvelIndex: number) {
    setIndex(nouvelIndex);
    setMode("consulter");
    setErreur(null);
  }

  function decider(decision: DecisionRevue) {
    if (!courante || !modifiable || revoir.isPending) return;
    const cible =
      courante.type === "metric" ? { metric_id: courante.id } : { emission_id: courante.id };
    revoir.mutate(
      { ...cible, ...decision },
      {
        onSuccess: () => {
          const apres = valeurs.map((v, i) =>
            i === position ? { ...v, statut: decision.decision } : v,
          );
          aller(prochaineARevoir(apres, position));
        },
        onError: (error) =>
          setErreur(
            error instanceof ApiError ? error.message : "La décision n’a pas été enregistrée.",
          ),
      },
    );
  }

  useRaccourcisRevue(
    {
      accepter: () => {
        if (mode === "consulter") decider({ decision: "ACCEPTED" });
      },
      corriger: () => {
        if (modifiable) setMode("corriger");
      },
      nonTrouvee: () => {
        if (modifiable) setMode("non_trouvee");
      },
      suivante: () => aller((position + 1) % valeurs.length),
      precedente: () => aller((position - 1 + valeurs.length) % valeurs.length),
    },
    valeurs.length > 0 && !avisOuvert,
  );

  if (dossier.isPending) {
    return (
      <div className="space-y-4 p-2">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-[60vh] w-full" />
      </div>
    );
  }
  if (dossier.isError) {
    return (
      <div className="space-y-2 p-2">
        <p className="text-destructive">Dossier introuvable.</p>
        <Link to="/audit" className="text-brand-green underline underline-offset-2">
          Retour à mes dossiers
        </Link>
      </div>
    );
  }
  const rapport = dossier.data;
  const historique = (revues.data ?? []).filter((entree) =>
    courante?.type === "metric"
      ? entree.metric_id === courante.id
      : entree.emission_id === courante?.id,
  );

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            to="/audit"
            className="inline-flex items-center gap-1 text-sm text-brand-green underline underline-offset-2"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Mes dossiers
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-brand-blue">
            {rapport.company_name || "Dossier"}
          </h1>
          <p className="text-sm text-brand-grey">
            {titreDeclaration(rapport)}
            {rapport.company_sector ? ` · ${rapport.company_sector}` : ""}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant={variantStatutRapport(rapport.status)}>
              {libelleStatutRapport(rapport.status)}
            </Badge>
            <span className="text-sm text-brand-grey" aria-live="polite">
              {valeurs.length - restantes} / {valeurs.length} valeur(s) revue(s)
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <p className="hidden items-center gap-1 text-xs text-brand-grey md:flex">
            <Keyboard className="size-4" aria-hidden="true" />A accepter · E corriger · N non
            trouvée · J/K suivante/précédente
          </p>
          {modifiable ? (
            <Button
              onClick={() => setAvisOuvert(true)}
              disabled={restantes > 0}
              title={restantes > 0 ? `${restantes} valeur(s) à revoir avant l’avis` : undefined}
            >
              <ClipboardCheck className="size-4" aria-hidden="true" />
              Rendre l’avis
            </Button>
          ) : null}
        </div>
      </header>

      {rapport.declared_global_score !== null || rapport.coverage.missing_codes.length > 0 ? (
        <p className="text-sm text-brand-grey">
          {rapport.declared_global_score !== null
            ? `Score global auto-déclaré : ${formatValeur(rapport.declared_global_score)}/100. `
            : ""}
          {rapport.coverage.missing_codes.length > 0
            ? `Indicateurs attendus absents du rapport : ${listeIndicateurs(rapport.coverage.missing_codes)}.`
            : ""}
        </p>
      ) : null}

      {avisRendu ? (
        <Alert>
          <AlertTitle>Avis déjà rendu</AlertTitle>
          <AlertDescription>
            La revue est close : le dossier a été transmis à l’administrateur pour décision.
          </AlertDescription>
        </Alert>
      ) : null}
      {avisRendu ? <PreScoreBandeau etat={preScore} /> : null}

      {valeurs.length === 0 ? (
        <p className="rounded-lg border p-6 text-brand-grey">
          Aucune valeur extraite dans ce dossier : vous pouvez rendre votre avis directement.
        </p>
      ) : (
        <div className="grid min-h-[70vh] grid-cols-1 gap-4 lg:grid-cols-[25%_minmax(0,45%)_minmax(0,30%)]">
          <nav
            aria-label="Valeurs à revoir"
            className="max-h-[75vh] overflow-y-auto rounded-lg border"
          >
            <ul>
              {valeurs.map((valeur, i) => (
                <li key={valeur.cle}>
                  <button
                    type="button"
                    onClick={() => aller(i)}
                    aria-current={i === position ? "true" : undefined}
                    className={`flex w-full items-start justify-between gap-2 border-b px-3 py-2 text-left text-sm hover:bg-muted ${
                      i === position ? "bg-brand-green-light/60" : ""
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block text-xs text-brand-grey">{valeur.groupe}</span>
                      <span className="block truncate font-medium text-brand-blue">
                        {valeur.libelle}
                      </span>
                      <span className="block text-xs text-brand-grey">
                        {formatValeur(valeur.valeurAuditee ?? valeur.valeur, valeur.unite)}
                      </span>
                    </span>
                    <Badge variant={variantStatutRevue(valeur.statut)} className="shrink-0">
                      {libelleStatutRevue(valeur.statut)}
                    </Badge>
                  </button>
                </li>
              ))}
            </ul>
          </nav>

          <section
            aria-label="Page-preuve"
            className="overflow-auto rounded-lg border bg-muted/30 p-2"
          >
            {courante ? (
              <PdfPageViewer
                key={courante.preuve.id}
                url={urlPreuve(rapportId, courante.preuve.id)}
                boites={courante.boites.filter((b) => b.page === courante.preuve.page_start)}
                libelle={courante.libelle}
              />
            ) : null}
          </section>

          <aside
            aria-label="Détail de la valeur"
            className="max-h-[75vh] overflow-y-auto rounded-lg border p-4"
          >
            {courante ? (
              <ValueDetailPanel
                valeur={courante}
                historique={historique}
                mode={mode}
                setMode={setMode}
                decider={decider}
                enCours={revoir.isPending}
                erreur={erreur}
                modifiable={modifiable}
              />
            ) : null}
          </aside>
        </div>
      )}

      <OpinionDialog rapportId={rapportId} open={avisOuvert} onOpenChange={setAvisOuvert} />
    </div>
  );
}

function PreScoreBandeau({ etat }: { etat: ReturnType<typeof useAuditPreScore> }) {
  if (etat.isPending) return <Skeleton className="h-12 w-full" />;
  if (etat.isError || !etat.data) return null;
  const score = etat.data;
  if (!score.computable) {
    return (
      <p className="rounded-lg border p-3 text-sm text-brand-grey">
        Pré-score non calculable avec les valeurs revues.
      </p>
    );
  }
  const piliers: [string, number | null][] = [
    ["E", score.environmental_score],
    ["S", score.social_score],
    ["G", score.governance_score],
  ];
  return (
    <section
      aria-label="Pré-score"
      className="flex flex-wrap items-baseline gap-x-6 gap-y-1 rounded-lg border bg-muted/40 p-3"
    >
      <span className="text-sm text-brand-grey">Pré-score (valeurs revues, non officiel)</span>
      <span className="text-xl font-semibold text-brand-blue">
        {formatValeur(score.global_score ?? 0)} / 100
      </span>
      {piliers.map(([pilier, valeur]) => (
        <span key={pilier} className="text-sm">
          {pilier} {valeur === null ? "—" : formatValeur(valeur)}
        </span>
      ))}
      {score.coverage_rate !== null ? (
        <span className="text-sm text-brand-grey">
          Couverture {Math.round(score.coverage_rate * 100)} %
        </span>
      ) : null}
    </section>
  );
}
