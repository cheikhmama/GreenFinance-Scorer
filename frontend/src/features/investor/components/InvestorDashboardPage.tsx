import { PageHeader } from "@/shared/ui/page-header";

/**
 * Tableau de bord placeholder de l'espace Investisseur. Aucune fonctionnalité
 * métier : app/investor/router.py est encore un router vide côté backend (Étape 16).
 * Confirme seulement que RequireRole a laissé passer l'utilisateur.
 */
export function InvestorDashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investisseur"
        title="Tableau de bord"
        description="Portefeuille, scores et agrégations — pas encore disponible."
      />
      <p className="text-sm text-muted-foreground">
        Cet espace sera implémenté à l'Étape 16 (portefeuilles et scores ESG).
      </p>
    </div>
  );
}
