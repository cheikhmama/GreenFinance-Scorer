import { dateHeure } from "./etat";

/** Bandeau d'une déclaration soumise (tâche 5.8) : verrouillée depuis sa soumission, avec
 * l'empreinte du fichier transmis. */
export function LockBanner({
  submittedAt,
  checksum,
}: {
  submittedAt: string;
  checksum: string | null;
}) {
  return (
    <section
      aria-label="Déclaration verrouillée"
      className="rounded-lg border border-brand-blue/30 bg-brand-blue/5 p-4"
    >
      <p className="font-semibold text-brand-blue">🔒 Soumis le {dateHeure(submittedAt)}</p>
      <p className="mt-1 text-sm text-brand-grey">
        Le fichier et la déclaration ne peuvent plus être modifiés pendant l’examen.
      </p>
      {checksum ? (
        <p className="mt-2 text-xs text-brand-grey">
          Empreinte SHA-256 du fichier :{" "}
          <code className="break-all font-mono text-brand-blue">{checksum}</code>
        </p>
      ) : null}
    </section>
  );
}
