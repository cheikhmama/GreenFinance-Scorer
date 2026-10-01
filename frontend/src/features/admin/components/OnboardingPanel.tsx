import { ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";
import type { RegistrationStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { KycDialog } from "./KycDialog";

/** Bandeau d'une inscription en cours d'examen (tâches 1.4, 5.3). La décision — approuver,
 * demander des informations, refuser — se prend dans la fenêtre KYC, à côté des contrôles. */
export function OnboardingPanel({
  entrepriseId,
  statut,
}: {
  entrepriseId: string;
  statut: RegistrationStatus;
}) {
  const [ouverte, setOuverte] = useState(false);
  const attenteReponse = statut === "INFO_REQUESTED";

  return (
    <Alert className="border-amber-200 bg-amber-50/70">
      <UserPlus aria-hidden="true" className="text-amber-700" />
      <AlertTitle>{attenteReponse ? "Informations demandées" : "Inscription à valider"}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>
          {attenteReponse
            ? "Le demandeur a été invité à compléter sa demande depuis sa page de suivi. Vous pouvez tout de même décider dès maintenant."
            : "Cette entreprise s’est inscrite elle-même. Tant qu’elle n’est pas validée, personne ne peut s’y connecter et elle n’apparaît nulle part ailleurs."}
        </p>
        <Button size="sm" onClick={() => setOuverte(true)}>
          <ShieldCheck className="size-4" aria-hidden="true" />
          Examiner la demande
        </Button>
      </AlertDescription>
      <KycDialog entrepriseId={entrepriseId} open={ouverte} onOpenChange={setOuverte} />
    </Alert>
  );
}
