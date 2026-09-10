import { PageHeader } from "@/shared/ui/page-header";

/**
 * Tableau de bord placeholder de l'espace Chercheur. Aucune fonctionnalité métier :
 * app/researcher/router.py est encore un router vide côté backend (Étape 17).
 * Confirme seulement que RequireRole a laissé passer l'utilisateur.
 */
export function ResearcherDashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Chercheur"
        title="Tableau de bord"
        description="Données ESG autorisées, analyses et rattachements — pas encore disponible."
      />
      <p className="text-sm text-muted-foreground">
        Cet espace sera implémenté à l'Étape 17 (accès Chercheur et Institution).
      </p>
    </div>
  );
}
