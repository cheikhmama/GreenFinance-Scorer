import { Building2, CheckCircle2, FileText, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { EntrepriseAdmin } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libellePays } from "@/shared/format/pays";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import {
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import {
  useAllCompanies,
  useReactivateCompany,
  useSuspendCompany,
  useValidateReport,
} from "../api";

/** Vue de suivi de TOUTES les entreprises pour l'Administrateur — contrairement à
 * PublishableCompaniesSection (uniquement celles prêtes à publier), inclut aussi une entreprise
 * sans aucun rapport et sans compte utilisateur rattaché, avec son statut. Recherche et
 * pagination portées par l'API (GET /admin/entreprises?recherche=&page=&page_size=), même
 * principe "Voir plus" que les autres listes Admin. */
export function AllCompaniesSection() {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useAllCompanies(rechercheDebattue);

  const entreprises = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Toutes les entreprises</CardTitle>
      </CardHeader>
      <CardContent>
        <label htmlFor="toutes-entreprises-recherche" className="relative mb-4 block max-w-sm">
          <span className="sr-only">Rechercher une entreprise</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
          <Input
            id="toutes-entreprises-recherche"
            value={recherche}
            onChange={(event) => setRecherche(event.target.value)}
            placeholder="Rechercher par nom, secteur ou pays"
            className="pl-9"
          />
        </label>

        {isLoading ? <CardListSkeleton count={3} /> : null}
        {isError ? <p className="text-destructive">Impossible de charger la liste.</p> : null}
        {!isLoading && !isError && entreprises.length === 0 ? (
          <EmptyState icon={Building2} message="Aucune entreprise." />
        ) : null}

        {entreprises.length > 0 ? (
          <div className="space-y-3">
            {entreprises.map((entreprise) => (
              <EntrepriseLigne key={entreprise.id} entreprise={entreprise} />
            ))}
          </div>
        ) : null}

        {entreprises.length > 0 && hasNextPage ? (
          <div className="mt-3">
            <Button
              variant="outline"
              size="sm"
              disabled={isFetchingNextPage}
              onClick={() => fetchNextPage()}
            >
              {isFetchingNextPage ? "Chargement..." : "Voir plus"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

/** Une carte par entreprise — logo + identité toujours visibles, actions (Voir le rapport /
 * Valider / Suspendre-Réactiver) regroupées et cohérentes plutôt que des liens texte épars.
 * « Valider » n'apparaît que si le dernier rapport est réellement en attente de décision
 * (PENDING_DECISION) : un raccourci vers la même action que le formulaire de décision du rapport
 * (voir AdminReportDetailPage), jamais une validation à l'aveugle sans avoir pu consulter les
 * données — le bouton "Voir le rapport" reste toujours à côté pour ça. */
function EntrepriseLigne({ entreprise }: { entreprise: EntrepriseAdmin }) {
  const suspend = useSuspendCompany();
  const reactivate = useReactivateCompany();
  const validate = useValidateReport(entreprise.latest_report_id ?? "");
  const confirm = useConfirm();
  const [actionError, setActionError] = useState<string | null>(null);

  const enAttenteDeDecision = entreprise.latest_report_status === "PENDING_DECISION";

  async function suspendre() {
    const confirme = await confirm({
      title: "Suspendre cette entreprise ?",
      description: `${entreprise.name} ne pourra plus déposer de nouveau rapport tant qu'elle reste suspendue. Vous pourrez la réactiver à tout moment.`,
      confirmLabel: "Suspendre",
    });
    if (!confirme) return;
    setActionError(null);
    suspend.mutate(entreprise.id, {
      onError: (err) =>
        setActionError(err instanceof ApiError ? err.message : "Échec de la suspension."),
    });
  }

  return (
    <Card className="shadow-none">
      <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <CompanyAvatar
            nom={entreprise.name}
            logo={entreprise.logo}
            className="size-14 shrink-0"
          />
          <div className="min-w-0">
            <Link
              to={`/admin/entreprises/${entreprise.id}`}
              className="font-semibold text-brand-blue hover:underline"
            >
              {entreprise.name}
            </Link>
            <p className="text-sm text-brand-grey">
              {entreprise.sector} — {libellePays(entreprise.country)}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {entreprise.status !== "ACTIVE" ? (
                <Badge variant={variantStatutInscription(entreprise.status)}>
                  {libelleStatutInscription(entreprise.status)}
                </Badge>
              ) : null}
              {entreprise.latest_report_status ? (
                <Badge variant={variantStatutRapport(entreprise.latest_report_status)}>
                  {libelleStatutRapport(entreprise.latest_report_status)}
                </Badge>
              ) : (
                <Badge variant="secondary">Aucun rapport</Badge>
              )}
              <Badge variant={entreprise.owner_user_id ? "success" : "outline"}>
                {entreprise.owner_user_id ? "Compte lié" : "Sans compte"}
              </Badge>
            </div>
            {actionError ? <p className="mt-1 text-xs text-destructive">{actionError}</p> : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
          {entreprise.latest_report_id ? (
            <Button asChild size="sm" variant="outline">
              <Link to={`/admin/rapports/${entreprise.latest_report_id}`}>
                <FileText className="size-4" />
                Voir le rapport
              </Link>
            </Button>
          ) : null}
          {enAttenteDeDecision && entreprise.latest_report_id ? (
            <Button
              size="sm"
              disabled={validate.isPending}
              onClick={() => {
                setActionError(null);
                validate.mutate(
                  { comment: null },
                  {
                    onError: (err) =>
                      setActionError(
                        err instanceof ApiError ? err.message : "Échec de la validation.",
                      ),
                  },
                );
              }}
            >
              <CheckCircle2 className="size-4" />
              Valider
            </Button>
          ) : null}
          {/* Une inscription en attente ne se suspend ni ne se réactive : seule sa validation
              (tâche 1.4) la rend active. */}
          {entreprise.status === "ACTIVE" ? (
            <Button size="sm" variant="outline" disabled={suspend.isPending} onClick={suspendre}>
              Suspendre
            </Button>
          ) : null}
          {entreprise.status === "SUSPENDED" ? (
            <Button
              size="sm"
              variant="outline"
              disabled={reactivate.isPending}
              onClick={() => {
                setActionError(null);
                reactivate.mutate(entreprise.id, {
                  onError: (err) =>
                    setActionError(
                      err instanceof ApiError ? err.message : "Échec de la réactivation.",
                    ),
                });
              }}
            >
              Réactiver
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
