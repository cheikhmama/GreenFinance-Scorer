import { Bell, FileText, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { useMyNotifications } from "@/shared/notifications/api";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { PageHeader } from "@/shared/ui/page-header";
import { StatCard } from "@/shared/ui/stat-card";
import { useCompanyReports } from "../api";

/** Vue d'ensemble de l'espace Entreprise — le dépôt (CompanyDepositPage) et le suivi détaillé
 * (CompanyReportsPage) vivent chacun sur leur propre page, cohérent avec les autres espaces
 * (Investisseur, Institution, ...) qui séparent toujours « Tableau de bord » de leurs pages
 * métier. Le statut le plus récent et le total de rapports se déduisent de la liste déjà chargée
 * par useCompanyReports — aucune route dédiée n'était nécessaire pour ça. */
export function CompanyDashboardPage() {
  const { data: rapports, isLoading: chargementRapports } = useCompanyReports();
  const { data: notifications, isLoading: chargementNotifications } = useMyNotifications(5);

  const rapportsTries = [...(rapports ?? [])].sort(
    // date_creation, jamais date_depot : un brouillon (sans dépôt) reste le rapport le plus récent.
    (a, b) => new Date(b.date_creation).getTime() - new Date(a.date_creation).getTime(),
  );
  const dernierRapport = rapportsTries[0];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Tableau de bord"
        description="Vue d'ensemble de vos dépôts et de leur suivi."
        action={
          <Button asChild>
            <Link to="/company/deposer">
              <Upload />
              Déposer un rapport
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard
          label="Rapports déposés"
          value={chargementRapports ? "…" : (rapports?.length ?? 0)}
          hint="Toutes versions confondues"
          icon={<FileText className="size-5" />}
          tone="blue"
          to="/company/rapports"
        />
        <Card className="gap-4 py-5 shadow-none">
          <CardContent className="px-5">
            <p className="text-sm font-medium text-muted-foreground">Statut du dernier rapport</p>
            <div className="mt-2">
              {chargementRapports ? (
                <span className="text-brand-grey">…</span>
              ) : dernierRapport ? (
                <Badge variant={variantStatutRapport(dernierRapport.statut)}>
                  {libelleStatutRapport(dernierRapport.statut, dernierRapport.statut_extraction)}
                </Badge>
              ) : (
                <span className="text-sm text-brand-grey">Aucun rapport déposé</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Bell className="size-4" />
            Notifications récentes
          </CardTitle>
          <Link to="/company/rapports" className="text-sm text-brand-green underline underline-offset-2">
            Voir mes rapports
          </Link>
        </CardHeader>
        <CardContent>
          {chargementNotifications ? <p className="text-brand-grey">Chargement...</p> : null}
          {!chargementNotifications && (notifications?.length ?? 0) === 0 ? (
            <p className="text-brand-grey">Aucune notification pour l'instant.</p>
          ) : null}
          {notifications && notifications.length > 0 ? (
            <ul className="divide-y">
              {notifications.map((notification) => (
                <li key={notification.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                  <span className={notification.lu ? "text-brand-grey" : "font-medium text-brand-blue"}>
                    {notification.message}
                  </span>
                  <span className="shrink-0 text-xs text-brand-grey">
                    {new Date(notification.date_envoi).toLocaleDateString("fr-FR")}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
