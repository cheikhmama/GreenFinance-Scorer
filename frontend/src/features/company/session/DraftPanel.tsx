import { FileUp, Loader2, Send, Trash2 } from "lucide-react";
import { type SyntheticEvent, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type {
  GroupeCompletude,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Skeleton } from "@/shared/ui/skeleton";
import { useAttachDraftFile, useDiscardDraft } from "../api";
import { fichierBrouillonSchema } from "../schemas";
import { CompletenessChecklist } from "./CompletenessChecklist";
import type { EtatBrouillon } from "./etat";

/** Préparation d'une déclaration (tâche 5.8) : joindre le PDF, suivre son analyse, lire la liste
 * de complétude, puis soumettre — ou abandonner le brouillon. */
export function DraftPanel({
  rapport,
  etat,
  groupes,
  chargementListe,
  onSoumettre,
}: {
  rapport: RapportESGDetail;
  etat: EtatBrouillon;
  groupes: GroupeCompletude[] | undefined;
  chargementListe: boolean;
  onSoumettre: () => void;
}) {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const abandonner = useDiscardDraft(rapport.id);

  async function abandonnerBrouillon() {
    const confirme = await confirm({
      title: "Abandonner ce brouillon ?",
      description: "Le brouillon et son fichier sont supprimés ; rien n’a été transmis.",
      confirmLabel: "Abandonner",
      destructive: true,
    });
    if (confirme)
      abandonner.mutate(undefined, { onSuccess: () => navigate("/company/declarations") });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Préparation de la déclaration</CardTitle>
        <CardDescription>
          Rien n’est transmis avant la soumission. Joignez le PDF du rapport : sa lecture indique
          quels indicateurs attendus y ont été trouvés.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {etat === "ANALYSE" ? (
          <p className="flex items-center gap-2 text-sm text-brand-blue" aria-live="polite">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Lecture de « {rapport.original_filename ?? "votre fichier"} » en cours — la liste de
            complétude s’affiche dès qu’elle est terminée.
          </p>
        ) : null}

        {etat === "ECHEC" ? (
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

        {etat === "PRET" ? (
          chargementListe || !groupes ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <CompletenessChecklist groupes={groupes} />
          )
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

        <div className="flex flex-wrap gap-2 border-t pt-4">
          {etat === "PRET" ? (
            <Button onClick={onSoumettre}>
              <Send className="size-4" aria-hidden="true" />
              Soumettre
            </Button>
          ) : null}
          {etat !== "ANALYSE" ? (
            <Button variant="outline" onClick={abandonnerBrouillon} disabled={abandonner.isPending}>
              <Trash2 className="size-4" aria-hidden="true" />
              Abandonner le brouillon
            </Button>
          ) : null}
        </div>
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
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id={id}
          type="file"
          accept="application/pdf"
          className="max-w-md"
          aria-invalid={erreur !== null}
          onChange={(event) => setFichier(event.target.files?.[0] ?? null)}
        />
        <Button type="submit" variant="outline" disabled={joindre.isPending}>
          <FileUp className="size-4" aria-hidden="true" />
          {joindre.isPending ? "Envoi…" : bouton}
        </Button>
      </div>
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}
    </form>
  );
}
