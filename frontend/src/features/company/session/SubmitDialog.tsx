import { ApiError } from "@/shared/api/errors";
import type {
  GroupeCompletude,
  RapportESGDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { useSubmitDraft } from "../api";
import { dateHeure, totaux } from "./etat";

function Ligne({ libelle, children }: { libelle: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr]">
      <dt className="text-brand-grey">{libelle}</dt>
      <dd className="min-w-0 text-brand-blue">{children}</dd>
    </div>
  );
}

/** Confirmation de la soumission, puis reçu (tâche 5.8). Monté par la page, pas par le panneau du
 * brouillon : après la soumission le brouillon disparaît, le reçu doit rester affiché. */
export function SubmitDialog({
  rapport,
  groupes,
  open,
  onOpenChange,
}: {
  rapport: RapportESGDetail;
  groupes: GroupeCompletude[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const soumettre = useSubmitDraft(rapport.id);
  const recu = soumettre.data;
  const total = totaux(groupes);

  function fermer(ouvert: boolean) {
    if (!ouvert && recu) soumettre.reset();
    onOpenChange(ouvert);
  }

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent>
        {recu?.submitted_at ? (
          <>
            <DialogHeader>
              <DialogTitle>Reçu de soumission</DialogTitle>
              <DialogDescription>
                Votre rapport est transmis et verrouillé. Conservez ce reçu : l’empreinte identifie
                exactement le fichier soumis.
              </DialogDescription>
            </DialogHeader>
            <dl className="space-y-2 text-sm">
              <Ligne libelle="Rapport">
                {recu.report_type} — exercice {recu.fiscal_year}
              </Ligne>
              <Ligne libelle="Fichier">{recu.original_filename ?? "—"}</Ligne>
              <Ligne libelle="Soumis le">{dateHeure(recu.submitted_at)}</Ligne>
              <Ligne libelle="Empreinte SHA-256">
                <code className="break-all font-mono text-xs">{recu.checksum_sha256}</code>
              </Ligne>
              <Ligne libelle="Référence">
                <code className="break-all font-mono text-xs">{recu.id}</code>
              </Ligne>
            </dl>
            <DialogFooter>
              <Button onClick={() => fermer(false)}>Terminer</Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Soumettre la déclaration ?</DialogTitle>
              <DialogDescription>
                Une fois soumis, le rapport est verrouillé : ni le fichier ni la déclaration ne
                pourront être modifiés pendant l’examen.
              </DialogDescription>
            </DialogHeader>
            {soumettre.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {soumettre.error instanceof ApiError
                    ? soumettre.error.message
                    : "La soumission n’a pas abouti."}
                </AlertDescription>
              </Alert>
            ) : null}
            <dl className="space-y-2 text-sm">
              <Ligne libelle="Rapport">
                {rapport.type} — exercice {rapport.fiscal_year}
              </Ligne>
              <Ligne libelle="Fichier">{rapport.original_filename ?? "—"}</Ligne>
              <Ligne libelle="Empreinte SHA-256">
                <code className="break-all font-mono text-xs">{rapport.checksum_sha256}</code>
              </Ligne>
              <Ligne libelle="Complétude">
                {total.found} indicateur(s) trouvé(s) sur {total.expected}
              </Ligne>
            </dl>
            <DialogFooter>
              <Button variant="outline" onClick={() => fermer(false)}>
                Annuler
              </Button>
              <Button onClick={() => soumettre.mutate()} disabled={soumettre.isPending}>
                {soumettre.isPending ? "Soumission…" : "Confirmer la soumission"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
