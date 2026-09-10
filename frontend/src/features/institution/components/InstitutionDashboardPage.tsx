import { PageHeader } from "@/shared/ui/page-header";

/**
 * Tableau de bord placeholder de l'espace Institution. Aucune fonctionnalité
 * métier : app/institution/router.py est encore un router vide côté backend
 * (Étape 17). Confirme seulement que RequireRole a laissé passer l'utilisateur.
 */
export function InstitutionDashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title="Tableau de bord"
        description="Supervision institutionnelle et rattachements Chercheur — pas encore disponible."
      />
      <p className="text-sm text-muted-foreground">
        Cet espace sera implémenté à l'Étape 17 (accès Chercheur et Institution).
      </p>
    </div>
  );
}
