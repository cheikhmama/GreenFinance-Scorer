import { cn } from "@/shared/ui/cn";
import type { PresentationSession } from "./presentation";

/** Pastille d'état : fond pastel, bordure fine, point de couleur devant le libellé. */
export function StatusPill({ presentation }: { presentation: PresentationSession }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        presentation.ton,
      )}
    >
      <span aria-hidden="true" className={cn("mr-1.5 h-2 w-2 rounded-full", presentation.point)} />
      {presentation.libelle}
    </span>
  );
}
