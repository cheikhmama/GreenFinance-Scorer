import { AlertTriangle, Building2, PieChart, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { formatPourcentage, formatScore } from "@/shared/format/etatPosition";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useInvestorDashboard } from "../api";

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
          value={data?.nombre_portefeuilles ?? "—"}
          hint="Actifs et archivés"
          icon={<Wallet className="size-5" />}
        />
        <StatCard
          label="Entreprises publiées"
          value={data?.nombre_entreprises_publiees ?? "—"}
          hint="Sur toute la plateforme"
          icon={<Building2 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Couverture ESG plateforme"
          value={data ? formatPourcentage(data.taux_couverture_esg_plateforme) : "—"}
          hint="Entreprises avec E, S et G calculés"
          icon={<PieChart className="size-5" />}
          tone="violet"
        />
        <StatCard
          label="Nouvelles publications suivies"
          value={data?.nombre_nouvelles_publications_suivies ?? "—"}
          hint="30 derniers jours, entreprises en position"
          icon={<Building2 className="size-5" />}
          tone="amber"
        />
      </section>

      {data && data.entreprises_suivies_suspendues.length > 0 ? (
        <Card className="border-destructive/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-destructive">
              <AlertTriangle className="size-4" />
              Entreprises suspendues dans vos positions
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {data.entreprises_suivies_suspendues.map((entreprise) => (
              <Badge key={entreprise.id} variant="destructive">
                {entreprise.nom}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-brand-blue">Répartition par secteur</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {!data || data.repartition_secteur.length === 0 ? (
              <p className="text-sm text-brand-grey">Aucune position pour l'instant.</p>
            ) : (
              data.repartition_secteur.map((ligne) => (
                <div key={ligne.secteur} className="flex items-center justify-between text-sm">
                  <span>{ligne.secteur}</span>
                  <span className="font-medium tabular-nums">
                    {ligne.montant_usd.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} USD
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-brand-blue">Publications récentes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {!data || data.publications_recentes.length === 0 ? (
              <p className="text-sm text-brand-grey">Aucune publication récente.</p>
            ) : (
              data.publications_recentes.map((entreprise) => (
                <Link
                  key={entreprise.id}
                  to={`/investor/entreprises/${entreprise.id}`}
                  className="flex items-center justify-between text-sm hover:underline"
                >
                  <span className="text-brand-blue">{entreprise.nom}</span>
                  <span className="text-brand-grey">{formatScore(entreprise.score.valeur_globale)}</span>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Positions principales</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {!data || data.positions_principales.length === 0 ? (
            <p className="text-sm text-brand-grey">Aucune position pour l'instant.</p>
          ) : (
            data.positions_principales.map((position) => (
              <div key={position.id} className="flex items-center justify-between text-sm">
                <Link
                  to={`/investor/portefeuilles/${position.portefeuille_id}`}
                  className="text-brand-blue hover:underline"
                >
                  {position.entreprise.nom}
                </Link>
                <span className="font-medium tabular-nums">
                  {position.montant_converti.toLocaleString("fr-FR", { maximumFractionDigits: 0 })}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
