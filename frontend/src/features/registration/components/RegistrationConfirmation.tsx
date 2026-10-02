import { CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";

/** Confirmation commune aux trois inscriptions (tâche 5.10). La réponse du serveur est la même que
 * la demande aboutisse ou non : la suite arrive par e-mail. */
export function RegistrationConfirmation() {
  return (
    <div className="space-y-5">
      <Alert role="status" className="border-primary/20 bg-secondary/60">
        <CheckCircle2 aria-hidden="true" className="text-primary" />
        <AlertTitle>Demande d’inscription transmise</AlertTitle>
        <AlertDescription>
          Un administrateur examinera vos informations sous 24h à 48h. Vous recevrez une
          notification par e-mail dès validation.
        </AlertDescription>
      </Alert>
      <Button asChild className="h-12 w-full rounded-xl">
        <Link to="/login">Retour à la connexion</Link>
      </Button>
    </div>
  );
}
