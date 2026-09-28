import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/** État vide standard — icône, message, action optionnelle — jamais un simple <p> perdu dans une
 * carte vide. Utilisé partout où une liste peut être vide (voir prototype/components/shared.tsx
 * pour le patron d'origine, ici branché sur de vraies données). */
export function EmptyState({
  icon: Icon,
  message,
  action,
}: {
  icon: LucideIcon;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-8 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-muted text-muted-foreground">
        <Icon className="size-6" />
      </span>
      <p className="max-w-sm text-sm text-brand-grey">{message}</p>
      {action}
    </div>
  );
}
