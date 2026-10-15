import { FileUp, Loader2 } from "lucide-react";
import { type SyntheticEvent, useId, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { RapportESGDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { FileDrop } from "@/shared/ui/file-drop";
import { Label } from "@/shared/ui/label";
import { useAttachDraftFile } from "../api";
import { fichierBrouillonSchema } from "../schemas";
import { etatBrouillon } from "../session/etat";

/** Étape 3 (spec §3.1) : joindre le PDF ; son analyse tourne en arrière-plan — on peut quitter
 * la page et revenir, la phase reste visible partout (tableau de bord, liste, en-tête). */
export function DocumentStep({ rapport }: { rapport: RapportESGDetail }) {
  const etat = etatBrouillon(rapport);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Document</CardTitle>
        <CardDescription>
          Joignez le PDF du rapport : sa lecture indique quels indicateurs attendus y figurent.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {etat === "ANALYSE" ? (
          <div className="space-y-2" aria-live="polite">
            <p className="flex items-center gap-2 text-sm text-foreground">
              <Loader2 className="size-4 motion-safe:animate-spin" aria-hidden="true" />
              Lecture de « {rapport.original_filename ?? "votre fichier"} » en cours — vous pouvez
              quitter cette page, l’analyse continue.
            </p>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
              <div className="h-full w-1/3 rounded-full bg-primary motion-safe:animate-pulse" />
            </div>
          </div>
        ) : null}
        {etat === "ECHEC" && rapport.extraction_error ? (
          <Alert variant="destructive">
            <AlertTitle>
              {rapport.extraction_error === "quota_llm_epuise"
                ? "Analyse momentanément impossible"
                : "Le fichier n’a pas pu être lu"}
            </AlertTitle>
            <AlertDescription>
              {libelleCauseExtraction(rapport.extraction_error)}. Joignez de nouveau le fichier.
            </AlertDescription>
          </Alert>
        ) : null}
        {etat !== "ANALYSE" ? (
          <JoindreFichier
            rapportId={rapport.id}
            libelle={
              etat === "SANS_FICHIER" ? "Rapport (PDF, 50 Mo au plus)" : "Remplacer le fichier"
            }
            bouton={etat === "SANS_FICHIER" ? "Joindre et analyser" : "Analyser ce fichier"}
          />
        ) : null}
        {etat === "PRET" ? (
          <div className="flex justify-end border-t pt-4">
            <Button asChild>
              <Link to="../verification" relative="path">
                Suivant
              </Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function JoindreFichier({
  rapportId,
  libelle,
  bouton,
}: {
  rapportId: string;
  libelle: string;
  bouton: string;
}) {
  const id = useId();
  const joindre = useAttachDraftFile(rapportId);
  const [fichier, setFichier] = useState<File | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  function envoyer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const verifie = fichierBrouillonSchema.safeParse(fichier);
    if (!verifie.success) {
      setErreur(verifie.error.issues[0]?.message ?? "Fichier invalide.");
      return;
    }
    setErreur(null);
    joindre.mutate(verifie.data, {
      onError: (error) =>
        setErreur(error instanceof ApiError ? error.message : "Le fichier n’a pas été transmis."),
    });
  }

  return (
    <form onSubmit={envoyer} className="space-y-2" noValidate>
      <Label htmlFor={id}>{libelle}</Label>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
        <FileDrop
          id={id}
          className="min-w-0 flex-1"
          accept="application/pdf"
          hint="PDF du rapport, 50 Mo au maximum"
          aria-invalid={erreur !== null}
          file={fichier ?? undefined}
          onFile={(choisi) => setFichier(choisi ?? null)}
          disabled={joindre.isPending}
        />
        <Button
          type="submit"
          variant="outline"
          className="h-[66px] shrink-0"
          disabled={joindre.isPending}
        >
          <FileUp className="size-4" aria-hidden="true" />
          {joindre.isPending ? "Envoi…" : bouton}
        </Button>
      </div>
      {erreur ? <p className="text-sm text-destructive dark:text-red-400">{erreur}</p> : null}
    </form>
  );
}
