import { cn } from "@/shared/ui/cn";

/** Placeholder de chargement générique — remplace le texte brut "Chargement..." dans les pages
 * liste/détail par une forme animée qui préfigure le contenu final, sans logique par page. */
export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

/** Ligne de carte générique (avatar + deux lignes de texte) — le patron répété par la plupart des
 * pages liste des deux espaces Chercheur/Institution pendant leur chargement. */
export function CardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: nombre fixe de lignes de squelette, jamais réordonnées
        <div key={index} className="flex items-center gap-3 rounded-xl border p-4">
          <Skeleton className="size-11 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
