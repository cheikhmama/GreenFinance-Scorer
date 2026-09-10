import { Check, ChevronRight, FileSearch, Info, X } from "lucide-react";
import { cloneElement, isValidElement, type ReactNode, useId } from "react";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { cn } from "@/shared/ui/cn";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        {eyebrow ? (
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand-green">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-brand-blue sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

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
  tone?: "green" | "blue" | "amber" | "violet";
}) {
  const tones = {
    green: "bg-brand-green-light text-brand-green",
    blue: "bg-blue-50 text-brand-blue",
    amber: "bg-amber-50 text-amber-700",
    violet: "bg-violet-50 text-violet-700",
  };

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

const statusStyles: Record<string, string> = {
  ACTIF: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  ACTIVE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  PUBLIE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  VALIDE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  TERMINEE: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  INVITE: "bg-blue-50 text-blue-700 ring-blue-600/20",
  EN_AUDIT: "bg-blue-50 text-blue-700 ring-blue-600/20",
  SOUMIS: "bg-blue-50 text-blue-700 ring-blue-600/20",
  A_AFFECTER: "bg-amber-50 text-amber-800 ring-amber-600/20",
  CORRECTION_DEMANDEE: "bg-amber-50 text-amber-800 ring-amber-600/20",
  CORRECTION_SOUMISE: "bg-violet-50 text-violet-700 ring-violet-600/20",
  BROUILLON: "bg-slate-100 text-slate-700 ring-slate-600/20",
  DESACTIVE: "bg-slate-100 text-slate-600 ring-slate-500/20",
  SUSPENDU: "bg-slate-100 text-slate-600 ring-slate-500/20",
  REJETE: "bg-red-50 text-red-700 ring-red-600/20",
  EXPORTEE: "bg-violet-50 text-violet-700 ring-violet-600/20",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset",
        statusStyles[status] ?? "bg-slate-100 text-slate-700 ring-slate-500/20",
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {label ?? status.replaceAll("_", " ")}
    </span>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return (
    <div>
      {label ? (
        <div className="mb-2 flex justify-between text-xs text-muted-foreground">
          <span>{label}</span>
          <span className="tabular-nums">{value}%</span>
        </div>
      ) : null}
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <div className="h-full rounded-full bg-brand-green" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export function Modal({
  open,
  title,
  description,
  children,
  onClose,
  size = "md",
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  size?: "md" | "lg" | "xl";
}) {
  if (!open) return null;
  const sizes = { md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-brand-blue/45 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="Fermer la fenêtre"
      />
      <section
        className={cn(
          "relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl",
          sizes[size],
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="prototype-dialog-title"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b bg-white px-6 py-5">
          <div>
            <h2 id="prototype-dialog-title" className="text-lg font-semibold text-brand-blue">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            ) : null}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Fermer">
            <X />
          </Button>
        </header>
        <div className="p-6">{children}</div>
      </section>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  const generatedId = useId();
  const controlId = isValidElement<{ id?: string }>(children)
    ? (children.props.id ?? generatedId)
    : generatedId;
  const control = isValidElement<{ id?: string }>(children)
    ? cloneElement(children, { id: controlId })
    : children;

  return (
    <div className="block space-y-2 text-sm font-medium text-brand-blue">
      <label htmlFor={controlId}>{label}</label>
      {control}
      {hint ? (
        <span className="block text-xs font-normal text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

export const fieldClassName =
  "min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-brand-blue outline-none transition focus:border-brand-green focus:ring-2 focus:ring-brand-green/15";

export function EvidenceCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      className="group flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left transition hover:border-brand-green/40 hover:bg-brand-green-light/40"
      onClick={onOpen}
    >
      <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-white text-brand-green shadow-sm">
        <FileSearch className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-brand-blue">Preuve documentaire</span>
        <span className="mt-1 block truncate text-xs text-muted-foreground">
          Rapport officiel · page source · extrait vérifiable
        </span>
      </span>
      <ChevronRight className="size-4 text-muted-foreground transition group-hover:translate-x-0.5" />
    </button>
  );
}

export function EvidencePreview({ company, page }: { company: string; page: number }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="min-h-80 rounded-xl border bg-slate-100 p-6">
        <div className="mx-auto min-h-64 max-w-md rounded bg-white p-8 text-xs leading-6 text-slate-600 shadow-md">
          <p className="font-semibold text-brand-blue">{company} — Rapport ESG officiel</p>
          <p className="mt-5 uppercase tracking-wide text-muted-foreground">Émissions de GES</p>
          <p className="mt-3 rounded border-l-4 border-brand-green bg-brand-green-light p-3">
            Les émissions Scope 1, Scope 2 et Scope 3 sont présentées avec leur période, leur unité
            et la méthode de calcul associée.
          </p>
          <p className="mt-5 text-right text-muted-foreground">Page {page}</p>
        </div>
      </div>
      <div className="space-y-4">
        <div className="rounded-xl border p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Traçabilité
          </p>
          <dl className="mt-3 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Document</dt>
              <dd className="text-right font-medium">Rapport officiel</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Page</dt>
              <dd className="font-medium">{page}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Confiance</dt>
              <dd className="font-medium text-brand-green">96 %</dd>
            </div>
          </dl>
        </div>
        <div className="flex gap-3 rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
          <Info className="mt-0.5 size-4 shrink-0" />
          <p>
            Cette visionneuse est simulée. Le prototype montre l’emplacement exact de la preuve.
          </p>
        </div>
      </div>
    </div>
  );
}

export function CheckList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item} className="flex gap-3 text-sm text-slate-700">
          <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-brand-green-light text-brand-green">
            <Check className="size-3" />
          </span>
          {item}
        </li>
      ))}
    </ul>
  );
}
