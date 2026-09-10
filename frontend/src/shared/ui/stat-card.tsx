import type { ReactNode } from "react";
import { Card, CardContent } from "@/shared/ui/card";
import { cn } from "@/shared/ui/cn";

const tones = {
  green: "bg-brand-green-light text-brand-green",
  blue: "bg-blue-50 text-brand-blue",
  amber: "bg-amber-50 text-amber-700",
  violet: "bg-violet-50 text-violet-700",
};

/** Carte de statistique pour les vues d'ensemble (ex. tableau de bord Admin) — une valeur,
 * son contexte et une icône, jamais une couleur seule pour porter le sens. */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "green",
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: ReactNode;
  tone?: keyof typeof tones;
}) {
  return (
    <Card className="gap-4 py-5 shadow-none">
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
}
