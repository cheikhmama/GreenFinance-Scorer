import { useMutation } from "@tanstack/react-query";
import { MailCheck, RotateCw } from "lucide-react";
import { type SyntheticEvent, useEffect, useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import {
  resendRegistrationCode,
  verifyRegistrationEmail,
} from "@/shared/api/generated/company/company";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

const DELAI_RENVOI_SECONDES = 60;

function messageErreur(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Trop de tentatives depuis votre connexion. Réessayez dans une heure.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "Code invalide ou expiré. Vérifiez-le, ou demandez-en un nouveau.";
  }
  return "La vérification n’a pas abouti. Vérifiez votre connexion et réessayez.";
}

/** Confirmation de l'adresse professionnelle après l'inscription d'une entreprise (tâche 5.11) :
 * le code à 6 chiffres reçu par e-mail. La demande n'est transmise à l'Administrateur qu'ensuite. */
export function EmailVerificationStep({
  email,
  onVerified,
}: {
  email: string;
  onVerified: () => void;
}) {
  const id = useId();
  const [code, setCode] = useState("");
  const [attente, setAttente] = useState(DELAI_RENVOI_SECONDES);
  const verifier = useMutation<void, ApiError, string>({
    mutationFn: (saisi) => verifyRegistrationEmail({ email, code: saisi }),
    retry: false,
    onSuccess: onVerified,
  });
  const renvoyer = useMutation<unknown, ApiError, void>({
    mutationFn: () => resendRegistrationCode({ email }),
    retry: false,
    onSuccess: () => {
      setAttente(DELAI_RENVOI_SECONDES);
      setCode("");
      verifier.reset();
    },
  });

  useEffect(() => {
    if (attente <= 0) return;
    const minuteur = window.setTimeout(() => setAttente((s) => s - 1), 1000);
    return () => window.clearTimeout(minuteur);
  }, [attente]);

  const complet = /^\d{6}$/.test(code);

  function envoyer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (complet && !verifier.isPending) verifier.mutate(code);
  }

  return (
    <form onSubmit={envoyer} className="space-y-5" noValidate>
      <div className="flex items-start gap-3 rounded-xl border bg-muted/40 p-4">
        <MailCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">
          Un code à 6 chiffres a été envoyé à{" "}
          <span className="font-medium text-foreground">{email}</span>. Saisissez-le pour confirmer
          votre adresse professionnelle et transmettre la demande.
        </p>
      </div>

      {verifier.isError ? (
        <Alert variant="destructive">
          <AlertDescription>{messageErreur(verifier.error)}</AlertDescription>
        </Alert>
      ) : null}
      {renvoyer.isSuccess ? (
        <p role="status" className="text-sm text-muted-foreground">
          Si une demande attend cette adresse, un nouveau code vient d’être envoyé.
        </p>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor={id}>Code de vérification</Label>
        <Input
          id={id}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          placeholder="000000"
          className="h-12 rounded-xl text-center font-mono text-lg tracking-[0.5em]"
          value={code}
          onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          aria-invalid={verifier.isError}
          autoFocus
        />
      </div>

      <Button
        type="submit"
        className="h-12 w-full rounded-xl"
        disabled={!complet || verifier.isPending}
      >
        {verifier.isPending ? "Vérification…" : "Vérifier et transmettre la demande"}
      </Button>

      <div className="text-center">
        <Button
          type="button"
          variant="link"
          size="sm"
          disabled={attente > 0 || renvoyer.isPending}
          onClick={() => renvoyer.mutate()}
        >
          <RotateCw aria-hidden="true" />
          {attente > 0 ? `Renvoyer le code (${attente} s)` : "Renvoyer le code"}
        </Button>
      </div>
    </form>
  );
}
