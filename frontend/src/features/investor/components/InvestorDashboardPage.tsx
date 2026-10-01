import { AlertTriangle, Building2, PieChart, Wallet } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { formatPourcentage, formatScore, variantScore } from "@/shared/format/etatPosition";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useInvestorDashboard, usePublishedCompanies } from "../api";

export function InvestorDashboardPage() {
  const { data } = useInvestorDashboard();

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Investisseur"
        title="Tableau de bord"
        description="Synthèse de vos portefeuilles et de l'activité récente sur les entreprises publiées."
      />

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Indicateurs clés">
        <StatCard
          label="Portefeuilles"
          value={data?.portfolio_count ?? "—"}
          hint="Actifs et archivés"
          icon={<Wallet className="size-5" />}
          to="/investor/portefeuilles"
        />
        <StatCard
          label="Entreprises publiées"
          value={data?.published_company_count ?? "—"}
          hint="Sur toute la plateforme"
          icon={<Building2 className="size-5" />}
          tone="blue"
          to="/investor/entreprises"
        />
        <StatCard
          label="Couverture ESG plateforme"
          value={data ? formatPourcentage(data.platform_esg_coverage_rate) : "—"}
          hint="Entreprises avec E, S et G calculés"
          icon={<PieChart className="size-5" />}
          tone="violet"
        />
        <StatCard
          label="Nouvelles publications suivies"
          value={data?.new_followed_publication_count ?? "—"}
          hint="30 derniers jours, entreprises en position"
          icon={<Building2 className="size-5" />}
          tone="amber"
          to="/investor/entreprises"
        />
      </section>

      {data && data.suspended_followed_companies.length > 0 ? (
        <Card className="border-destructive/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-destructive">
              <AlertTriangle className="size-4" />
              Entreprises suspendues dans vos positions
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {data.suspended_followed_companies.map((entreprise) => (
              <Badge key={entreprise.id} variant="destructive">
                {entreprise.name}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <RepartitionSecteurCard repartition={data?.sector_breakdown} />

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-brand-blue">Publications récentes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {!data || data.recent_publications.length === 0 ? (
              <p className="text-sm text-brand-grey">Aucune publication récente.</p>
            ) : (
              data.recent_publications.map((entreprise) => (
                <Link
                  key={entreprise.id}
                  to={`/investor/entreprises/${entreprise.id}`}
                  className="flex items-center gap-3 rounded-lg p-2 transition hover:bg-slate-50"
                >
                  <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-brand-blue">{entreprise.name}</p>
                    <p className="truncate text-xs text-brand-grey">{entreprise.sector}</p>
                  </div>
                  <Badge variant={variantScore(entreprise.score.global_score)} className="shrink-0">
                    {formatScore(entreprise.score.global_score)}
                  </Badge>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RepartitionSecteurCard({
  repartition,
}: {
  repartition: { sector: string; amount_usd: number }[] | undefined;
}) {
  const [secteurSelectionne, setSecteurSelectionne] = useState<string | null>(null);
  const secteurActif = secteurSelectionne ?? repartition?.[0]?.sector ?? null;
  const { data: entreprisesDuSecteur } = usePublishedCompanies({
    secteur: secteurActif ?? undefined,
  });
  const nombreDisponibles = entreprisesDuSecteur?.pages[0]?.total;
  const montantMax = repartition?.[0]?.amount_usd ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base text-brand-blue">Répartition par secteur</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!repartition || repartition.length === 0 ? (
          <p className="text-sm text-brand-grey">
            Aucune position pour l'instant —{" "}
            <Link
              to="/investor/entreprises"
              className="text-brand-blue underline-offset-2 hover:underline"
            >
              découvrez les entreprises publiées
            </Link>{" "}
            pour choisir un secteur.
          </p>
        ) : (
          <>
            <div className="space-y-2">
              {repartition.map((ligne) => {
                const selectionnee = ligne.sector === secteurActif;
                return (
                  <button
                    key={ligne.sector}
                    type="button"
                    onClick={() => setSecteurSelectionne(ligne.sector)}
                    className={`block w-full rounded-lg border p-2 text-left transition ${
                      selectionnee
                        ? "border-brand-green bg-brand-green-light/40"
                        : "border-transparent hover:border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between text-sm">
                      <span
                        className={
                          selectionnee ? "font-semibold text-brand-blue" : "text-brand-grey"
                        }
                      >
                        {ligne.sector}
                      </span>
                      <span className="font-medium tabular-nums text-brand-blue">
                        {ligne.amount_usd.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} USD
                      </span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-slate-100">
                      <div
                        className="h-1.5 rounded-full bg-brand-green"
                        style={{
                          width: `${montantMax ? (ligne.amount_usd / montantMax) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>

            {secteurActif ? (
              <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="text-brand-grey">
                  Entreprises disponibles dans{" "}
                  <strong className="text-brand-blue">{secteurActif}</strong>
                </span>
                <Link
                  to={`/investor/entreprises?secteur=${encodeURIComponent(secteurActif)}`}
                  className="font-semibold text-brand-blue underline-offset-2 hover:underline"
                >
                  {nombreDisponibles ?? "…"}
                </Link>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
