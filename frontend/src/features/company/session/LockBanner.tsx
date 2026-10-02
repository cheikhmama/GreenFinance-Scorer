import { Lock } from "lucide-react";

function dateEtHeure(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  const heure = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  return `${date} à ${heure}`;
}

/** Bandeau d'une déclaration soumise (tâche 5.8) : verrouillée depuis sa soumission, avec
 * l'empreinte du fichier transmis. `close` : une décision est rendue, l'examen est terminé. */
export function LockBanner({
  submittedAt,
  checksum,
  close = false,
}: {
  submittedAt: string;
  checksum: string | null;
  close?: boolean;
}) {
  return (
    <section
      aria-label="Déclaration verrouillée"
      className="flex gap-3 rounded-xl border bg-muted/50 p-4"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
        <Lock className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="font-semibold text-foreground">
          Soumis le {dateEtHeure(submittedAt)} — lecture seule
        </p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {close
            ? "L’examen est terminé : la déclaration et son fichier restent conservés tels que transmis."
            : "Le fichier et la déclaration ne peuvent plus être modifiés pendant l’examen."}
        </p>
        {checksum ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Empreinte SHA-256 du fichier :{" "}
            <code className="break-all font-mono text-foreground">{checksum}</code>
          </p>
        ) : null}
      </div>
    </section>
  );
}
