import { CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { useConfirmEmailChange } from "../api";

// secrets.token_urlsafe(32), émis par app/auth/email_change.py.
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

/** Cible du lien envoyé à la nouvelle adresse (app/auth/email_change.py::_construire_lien).
 * Aucune saisie : ouvrir le lien EST la confirmation (voir useConfirmEmailChange). Le jeton est
 * lu une seule fois au montage, pour que le retirer de l'URL ne relance ni n'efface rien. */
export function ConfirmEmailChangePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [token] = useState(() => {
    const tokens = searchParams.getAll("token");
    return tokens.length === 1 && TOKEN_PATTERN.test(tokens[0]) ? tokens[0] : null;
  });
  const tokenIsWellFormed = token !== null;
  const confirm = useConfirmEmailChange(token);
  const termine = confirm.isSuccess || confirm.isError;

  useEffect(() => {
    // Ne conserve pas le lien consommé dans l’historique courant du navigateur.
    if (termine) setSearchParams({}, { replace: true });
  }, [termine, setSearchParams]);

  const dejaPris = confirm.error instanceof ApiError && confirm.error.code === "email_deja_utilise";

  return (
    <AuthLayout
      eyebrow="VOTRE COMPTE"
      title={confirm.isSuccess ? "Adresse confirmée" : "Confirmation de votre adresse"}
      description={
        confirm.isSuccess
          ? "Cette adresse est désormais celle de votre compte GreenFinance-Scorer."
          : "Nous vérifions le lien que vous venez d’ouvrir."
      }
    >
      {confirm.isSuccess ? (
        <div className="space-y-5">
          <Alert role="status" className="border-brand-green/20 bg-brand-green-light/60">
            <CheckCircle2 aria-hidden="true" className="text-brand-green" />
            <AlertTitle>Adresse mise à jour</AlertTitle>
            <AlertDescription>
              Utilisez {confirm.data.email} pour vous connecter à partir de maintenant.
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to="/dashboard">Continuer</Link>
          </Button>
        </div>
      ) : !tokenIsWellFormed || confirm.isError ? (
        <div className="space-y-5">
          <Alert variant="destructive">
            <AlertTitle>Lien inutilisable</AlertTitle>
            <AlertDescription>
              {dejaPris
                ? "Cette adresse est déjà utilisée par un autre compte. Votre adresse actuelle reste inchangée."
                : tokenIsWellFormed
                  ? "Ce lien est invalide, a expiré ou a déjà été utilisé. Refaites la demande depuis votre profil."
                  : "Le lien de confirmation est absent ou incomplet. Ouvrez le lien reçu par e-mail."}
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to="/dashboard">Retour à mon espace</Link>
          </Button>
        </div>
      ) : (
        <p role="status" className="text-center text-sm text-muted-foreground">
          Confirmation en cours…
        </p>
      )}
    </AuthLayout>
  );
}
