import type { ReactNode } from "react";

/** En-tête de page standard : titre et description à gauche, actions ou avis de statut à droite.
 * Un seul gabarit typographique pour toute la plateforme — mêmes hauteur, tailles et
 * espacements d'une page à l'autre. Aucune métadonnée de contexte (rôle, secteur, identifiants)
 * n'y figure : la barre latérale porte déjà l'espace courant, et les métadonnées d'une entité
 * vivent dans les cartes de la page. Utilisé via shared/layout/PageShell.tsx. */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="flex min-h-14 flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 max-w-3xl space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
        {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>
      ) : null}
    </header>
  );
}
