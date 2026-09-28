import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/shared/ui/card";
import { cn } from "@/shared/ui/cn";

const tones = {
  green: "bg-brand-green-light text-brand-green",
  blue: "bg-blue-50 text-brand-blue dark:bg-blue-950/50 dark:text-blue-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  violet: "bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300",
};

/** Carte de statistique pour les vues d'ensemble (ex. tableau de bord Admin) — une valeur,
 * son contexte et une icône, jamais une couleur seule pour porter le sens. `to`, quand fourni,
 * rend toute la carte cliquable vers la page/fonctionnalité correspondante (ex. tableau de bord
 * Investisseur) — omis, la carte reste purement informative, comme avant. */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "green",
  to,
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: ReactNode;
  tone?: keyof typeof tones;
  to?: string;
}) {
  const carte = (
    <Card
      className={cn(
        "gap-4 py-5 shadow-none",
        to &&
          "transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-brand-green/70 hover:shadow-md",
      )}
    >
      <CardContent className="flex items-start justify-between px-5">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-brand-blue">{value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
        </div>
        <span className={cn("grid size-10 place-items-center rounded-xl", tones[tone])}>
          {icon}
        </span>
      </CardContent>
    </Card>
  );
  return to ? (
    <Link to={to} className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-green focus-visible:ring-offset-2">
      {carte}
    </Link>
  ) : (
    carte
  );
}
