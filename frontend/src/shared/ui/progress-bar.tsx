/** Barre de progression 0-100 avec libellé optionnel — promue depuis le mode prototype
 * (features/prototype/components/shared.tsx::ProgressBar, même rendu visuel), ici branchée sur
 * de vraies données (ex. quota d'export Institution). */
export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const bornee = Math.max(0, Math.min(100, value));
  return (
    <div>
      {label ? (
        <div className="mb-2 flex justify-between text-xs text-muted-foreground">
          <span>{label}</span>
          <span className="tabular-nums">{bornee}%</span>
        </div>
      ) : null}
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={bornee}
      >
        <div className="h-full rounded-full bg-brand-green" style={{ width: `${bornee}%` }} />
      </div>
    </div>
  );
}
