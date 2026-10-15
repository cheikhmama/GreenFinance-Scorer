import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./collapsible";

/** Carte repliable à résumé (spec §2.2, §3.4) : le résumé reste lisible replié comme déplié, le
 * détail n'apparaît que déplié. Contrôlée : l'URL décide de l'ouverture (famille d'un pilier).
 * Ouverte au montage (lien profond), elle se fait défiler en vue. */
export function DisclosureCard({
  id,
  titre,
  resume,
  ouvert,
  onOuvertChange,
  children,
}: {
  id: string;
  titre: ReactNode;
  resume: ReactNode;
  ouvert: boolean;
  onOuvertChange: (ouvert: boolean) => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const ouverteAuMontage = useRef(ouvert);
  useEffect(() => {
    if (ouverteAuMontage.current) ref.current?.scrollIntoView({ block: "start" });
  }, []);

  return (
    <Collapsible open={ouvert} onOpenChange={onOuvertChange} asChild>
      <section
        ref={ref}
        id={id}
        aria-labelledby={`${id}-titre`}
        className="rounded-xl border bg-card shadow-(--shadow-e1)"
      >
        <CollapsibleTrigger className="group flex w-full items-center justify-between gap-4 rounded-xl px-5 py-4 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="min-w-0">
            <span id={`${id}-titre`} className="block font-semibold text-foreground">
              {titre}
            </span>
            <span className="mt-0.5 block text-sm text-muted-foreground">{resume}</span>
          </span>
          <ChevronDown
            className="size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none group-data-[state=open]:rotate-180"
            aria-hidden="true"
          />
        </CollapsibleTrigger>
        <CollapsibleContent className="border-t px-5 py-4">{children}</CollapsibleContent>
      </section>
    </Collapsible>
  );
}
