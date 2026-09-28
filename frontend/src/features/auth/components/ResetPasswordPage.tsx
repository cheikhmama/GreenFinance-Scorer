import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/ui/form";
import { useResetPassword } from "../api";
import { type NouveauMotDePasseForm, resetPasswordFormSchema } from "../schemas";
import { PasswordInput } from "./PasswordInput";

// secrets.token_urlsafe(32), émis par app/auth/password_reset.py.
const RESET_TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

export function ResetPasswordPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tokens = searchParams.getAll("token");
  const token = tokens[0] ?? "";
  const tokenIsWellFormed = tokens.length === 1 && RESET_TOKEN_PATTERN.test(token);
  const resetPassword = useResetPassword();
  const [done, setDone] = useState(false);
  const [rejectedToken, setRejectedToken] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<NouveauMotDePasseForm>({
    resolver: zodResolver(resetPasswordFormSchema),
    defaultValues: { nouveauMotDePasse: "", confirmation: "" },
  });
  const invalidLink = !tokenIsWellFormed || rejectedToken === token;

  function onSubmit(values: NouveauMotDePasseForm) {
    if (resetPassword.isPending || invalidLink) return;
    setServerError(null);
    resetPassword.mutate(
      { token, nouveau_mot_de_passe: values.nouveauMotDePasse },
      {
        onSuccess: () => {
          form.reset();
          resetPassword.reset();
          setDone(true);
          // Ne conserve pas le lien consommé dans l’historique courant du navigateur.
          setSearchParams({}, { replace: true });
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === "jeton_invalide") {
            form.reset();
            setRejectedToken(token);
            return;
          }
          setServerError(
            error instanceof ApiError && error.status === 429
              ? "Trop de tentatives ont été effectuées. Veuillez patienter avant de réessayer."
              : "Le mot de passe n’a pas pu être modifié. Vérifiez votre connexion et réessayez dans quelques instants.",
          );
        },
      },
    );
  }

  return (
    <AuthLayout
      eyebrow="UN NOUVEAU DÉPART"
      title={done ? "Votre accès est rétabli" : "Nouveau mot de passe"}
      description={
        done
          ? "Vous pouvez maintenant vous reconnecter à votre espace GreenFinance-Scorer."
          : "Choisissez un mot de passe personnel pour sécuriser votre compte."
      }
    >
      {done ? (
        <div className="space-y-5">
          <Alert role="status" className="border-brand-green/20 bg-brand-green-light/60">
            <CheckCircle2 aria-hidden="true" className="text-brand-green" />
            <AlertTitle>Mot de passe mis à jour</AlertTitle>
            <AlertDescription>
              Connectez-vous avec votre nouveau mot de passe. Ce lien ne peut plus être utilisé.
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to="/login">Se connecter</Link>
          </Button>
        </div>
      ) : invalidLink ? (
        <div className="space-y-5">
          <Alert variant="destructive">
            <AlertTitle>Lien inutilisable</AlertTitle>
            <AlertDescription>
              {rejectedToken === token
                ? "Ce lien est invalide, a expiré ou a déjà été utilisé. Demandez un nouveau lien pour réinitialiser votre mot de passe."
                : "Le lien de réinitialisation est absent ou incomplet. Ouvrez le lien reçu par e-mail ou demandez-en un nouveau."}
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to="/mot-de-passe-oublie">Demander un nouveau lien</Link>
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {serverError ? (
              <Alert variant="destructive">
                <AlertTitle>Réinitialisation impossible</AlertTitle>
                <AlertDescription>{serverError}</AlertDescription>
              </Alert>
            ) : null}
            <FormField
              control={form.control}
              name="nouveauMotDePasse"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nouveau mot de passe</FormLabel>
                  <FormControl>
                    <PasswordInput
                      autoComplete="new-password"
                      className="h-12 rounded-xl"
                      disabled={resetPassword.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>8 caractères minimum.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmation"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Confirmer le mot de passe</FormLabel>
                  <FormControl>
                    <PasswordInput
                      autoComplete="new-password"
                      className="h-12 rounded-xl"
                      disabled={resetPassword.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              className="h-12 w-full rounded-xl"
              disabled={resetPassword.isPending}
            >
              {resetPassword.isPending ? "Modification en cours…" : "Enregistrer le mot de passe"}
            </Button>
          </form>
        </Form>
      )}
      {!done ? (
        <Link
          to="/login"
          className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-brand-green underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          Retour à la connexion
        </Link>
      ) : null}
    </AuthLayout>
  );
}
