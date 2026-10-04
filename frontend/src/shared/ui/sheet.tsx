import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import type * as React from "react";
import { cn } from "@/shared/ui/cn";

/* Tiroir latéral de détail (tâche 5.17) : s'ouvre depuis la droite au-dessus de la table, qui
   reste visible dessous ; plein écran au téléphone. Même primitive que Dialog (focus piégé,
   Échap ferme, le focus revient à l'élément d'origine). */
function Sheet(props: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="sheet" {...props} />;
}

function SheetContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        data-slot="sheet-overlay"
        className="fixed inset-0 z-50 bg-[rgb(10_24_38/0.32)]"
      />
      <DialogPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed inset-y-0 right-0 z-[60] flex w-full flex-col border-l bg-card shadow-(--shadow-e4) outline-none sm:max-w-[460px]",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close className="absolute right-3 top-3 grid size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <X className="size-4" aria-hidden="true" />
          <span className="sr-only">Fermer</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn("flex flex-col gap-1.5 border-b px-5 pt-5 pb-4 pr-14", className)}
      {...props}
    />
  );
}

function SheetBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-body"
      className={cn("flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-5", className)}
      {...props}
    />
  );
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("flex flex-wrap gap-2 border-t px-5 py-4", className)}
      {...props}
    />
  );
}

function SheetTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-lg font-semibold text-foreground", className)}
      {...props}
    />
  );
}

function SheetDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

/** Section titrée d'un tiroir (« Workflow et ESG », « Compte »…). */
function SheetSection({
  titre,
  children,
  className,
}: {
  titre: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("flex flex-col gap-2.5", className)}>
      <h3 className="text-[11px] font-semibold tracking-[0.1em] text-muted-foreground uppercase">
        {titre}
      </h3>
      {children}
    </section>
  );
}

/** Liste « libellé — valeur » d'un tiroir. Une valeur absente s'affiche « — ». */
function SheetFields({ champs }: { champs: { libelle: string; valeur: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
      {champs.map(({ libelle, valeur }) => (
        <div key={libelle} className="contents">
          <dt className="text-muted-foreground">{libelle}</dt>
          <dd className="min-w-0 text-foreground [overflow-wrap:anywhere]">{valeur ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

export {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFields,
  SheetFooter,
  SheetHeader,
  SheetSection,
  SheetTitle,
};
