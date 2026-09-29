import { CheckCircle2, UserPlus, XCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Textarea } from "@/shared/ui/textarea";
import { useOnboardCompany } from "../api";

/** Décision sur une inscription publique en attente (tâche 1.4). Valider envoie au titulaire son
 * lien d'activation ; refuser supprime l'inscription et lui transmet le motif — d'où le retour à
 * la liste, la fiche n'existant plus. */
export function OnboardingPanel({ entrepriseId, nom }: { entrepriseId: string; nom: string }) {
  const onboard = useOnboardCompany();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const [refusEnCours, setRefusEnCours] = useState(false);
  const [motif, setMotif] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);

  function surErreur(error: unknown) {
    setErreur(error instanceof ApiError ? error.message : "La décision n’a pas pu être enregistrée.");
  }

  async function valider() {
    const confirme = await confirm({
      title: "Valider cette inscription ?",
      description: `${nom} devient active et son titulaire reçoit un lien pour créer son mot de passe.`,
      confirmLabel: "Valider",
    });
    if (!confirme) return;
    setErreur(null);
    onboard.mutate({ entrepriseId, decision: "approve" }, { onError: surErreur });
  }

  function refuser() {
    setErreur(null);
    onboard.mutate(
      { entrepriseId, decision: "reject", reason: motif.trim() },
      { onSuccess: () => navigate("/admin/entreprises", { replace: true }), onError: surErreur },
    );
  }

  return (
    <Alert className="border-amber-200 bg-amber-50/70">
      <UserPlus aria-hidden="true" className="text-amber-700" />
      <AlertTitle>Inscription à valider</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>
          Cette entreprise s’est inscrite elle-même. Vérifiez son identité et complétez son profil
          si besoin avant de décider : tant qu’elle n’est pas validée, personne ne peut s’y
          connecter et elle n’apparaît nulle part ailleurs.
        </p>
        {erreur ? <p className="text-destructive">{erreur}</p> : null}
        {refusEnCours ? (
          <div className="space-y-2">
            <label htmlFor="motif-refus" className="text-sm font-medium">
              Motif du refus (envoyé au demandeur)
            </label>
            <Textarea
              id="motif-refus"
              value={motif}
              maxLength={1000}
              onChange={(event) => setMotif(event.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="destructive"
                disabled={onboard.isPending || !motif.trim()}
                onClick={refuser}
              >
                Confirmer le refus
              </Button>
              <Button size="sm" variant="outline" onClick={() => setRefusEnCours(false)}>
                Annuler
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={onboard.isPending} onClick={valider}>
              <CheckCircle2 className="size-4" />
              Valider l’inscription
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={onboard.isPending}
              onClick={() => setRefusEnCours(true)}
            >
              <XCircle className="size-4" />
              Refuser
            </Button>
          </div>
        )}
      </AlertDescription>
    </Alert>
  );
}
