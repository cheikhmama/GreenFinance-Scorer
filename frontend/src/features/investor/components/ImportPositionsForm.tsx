import { FileUp } from "lucide-react";
import { type SyntheticEvent, useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { useImportPositions } from "../api";

/** Classe `line_12` avant `line_3` numériquement ; l'erreur de fichier (`file`) en premier. */
function lignesTriees(fields: Record<string, string>) {
  const rang = (cle: string) => (cle === "file" ? -1 : Number(cle.replace("line_", "")));
  return Object.entries(fields).sort(([a], [b]) => rang(a) - rang(b));
}

/** Import d'un fichier de positions (CSV ou JSON, par ISIN ou ticker) dans un portefeuille vide
 * (tâche 2.2). Tout ou rien : en cas d'erreur, chaque ligne fautive est listée et rien n'est
 * enregistré. Les lignes qu'aucune entreprise publiée ne reconnaît sont conservées. */
export function ImportPositionsForm({ portefeuilleId }: { portefeuilleId: string }) {
  const importer = useImportPositions(portefeuilleId);
  const [fichier, setFichier] = useState<File | null>(null);
  const [valeurTotale, setValeurTotale] = useState("");
  const idFichier = useId();
  const idValeur = useId();

  function envoyer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fichier || importer.isPending) return;
    importer.mutate({
      file: fichier,
      total_value: valeurTotale ? Number(valeurTotale) : null,
    });
  }

  const erreur = importer.error;
  return (
    <form
      onSubmit={envoyer}
      className="mt-4 w-full max-w-lg space-y-3 rounded-xl border p-4 text-left"
    >
      <p className="text-sm font-medium">Ou importer un fichier de positions</p>
      <p className="text-xs text-brand-grey">
        CSV ou JSON : colonne <code>identifier</code> (ISIN, ou ticker avec{" "}
        <code>identifier_type=TICKER</code>), puis <code>outstanding_amount</code> et{" "}
        <code>currency</code>, ou <code>weight</code> (la somme des poids vaut 1).
      </p>
      <div className="space-y-1">
        <Label htmlFor={idFichier}>Fichier</Label>
        <Input
          id={idFichier}
          type="file"
          accept=".csv,.json,text/csv,application/json"
          onChange={(event) => setFichier(event.target.files?.[0] ?? null)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={idValeur}>
          Valeur totale du portefeuille (import par poids uniquement)
        </Label>
        <Input
          id={idValeur}
          type="number"
          min="0"
          step="any"
          value={valeurTotale}
          onChange={(event) => setValeurTotale(event.target.value)}
        />
      </div>
      {importer.isSuccess ? (
        <Alert role="status">
          <AlertTitle>{importer.data.imported} position(s) importée(s)</AlertTitle>
          <AlertDescription>
            {importer.data.matched} rapprochée(s), {importer.data.unmatched} non reconnue(s),{" "}
            {importer.data.ambiguous} ambiguë(s).
          </AlertDescription>
        </Alert>
      ) : null}
      {erreur ? (
        <Alert variant="destructive">
          <AlertTitle>Import refusé — rien n’a été enregistré</AlertTitle>
          <AlertDescription>
            {erreur instanceof ApiError && erreur.fields ? (
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {lignesTriees(erreur.fields).map(([cle, message]) => (
                  <li key={cle}>
                    {cle === "file" ? "Fichier" : `Ligne ${cle.replace("line_", "")}`} : {message}
                  </li>
                ))}
              </ul>
            ) : erreur instanceof ApiError ? (
              erreur.message
            ) : (
              "L’import n’a pas pu être envoyé. Réessayez."
            )}
          </AlertDescription>
        </Alert>
      ) : null}
      <Button type="submit" size="sm" disabled={!fichier || importer.isPending}>
        <FileUp className="size-4" />
        {importer.isPending ? "Import en cours…" : "Importer"}
      </Button>
    </form>
  );
}
