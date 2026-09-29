import type { UseMutationResult } from "@tanstack/react-query";
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
import { useActivateAccount, useResetPassword } from "../api";
import { MOT_DE_PASSE_LONGUEUR_MIN, type NouveauMotDePasseForm, resetPasswordFormSchema } from "../schemas";
import { PasswordInput } from "./PasswordInput";

// secrets.token_urlsafe(32), émis par app/auth/password_reset.py et app/auth/activation.py.
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

type TokenPasswordMutation = UseMutationResult<
  void,
  ApiError,
  { token: string; nouveau_mot_de_passe: string }
>;

interface Textes {
  eyebrow: string;
  titre: string;
  titreFait: string;
  description: string;
  descriptionFaite: string;
  alerteFaiteTitre: string;
  alerteFaite: string;
  erreurTitre: string;
  erreurServeur: string;
  lienRejete: string;
  lienAbsent: string;
  actionLienInvalide: { libelle: string; vers: string };
  boutonEnCours: string;
}

/** Page commune aux deux liens qui posent un mot de passe à partir d'un jeton reçu par e-mail :
 * réinitialisation (mot de passe oublié) et activation d'un compte provisionné par
 * l'Administrateur. Même règle de mot de passe, même garde sur le jeton, seuls les textes et
 * l'appel changent. */
function TokenPasswordPage({ mutation, textes }: { mutation: TokenPasswordMutation; textes: Textes }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const tokens = searchParams.getAll("token");
  const token = tokens[0] ?? "";
  const tokenIsWellFormed = tokens.length === 1 && TOKEN_PATTERN.test(token);
  const [done, setDone] = useState(false);
  const [rejectedToken, setRejectedToken] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<NouveauMotDePasseForm>({
    resolver: zodResolver(resetPasswordFormSchema),
    defaultValues: { nouveauMotDePasse: "", confirmation: "" },
  });
  const invalidLink = !tokenIsWellFormed || rejectedToken === token;

  function onSubmit(values: NouveauMotDePasseForm) {
    if (mutation.isPending || invalidLink) return;
    setServerError(null);
    mutation.mutate(
      { token, nouveau_mot_de_passe: values.nouveauMotDePasse },
      {
        onSuccess: () => {
          form.reset();
          mutation.reset();
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
              : textes.erreurServeur,
          );
        },
      },
    );
  }

  return (
    <AuthLayout
      eyebrow={textes.eyebrow}
      title={done ? textes.titreFait : textes.titre}
      description={done ? textes.descriptionFaite : textes.description}
    >
      {done ? (
        <div className="space-y-5">
          <Alert role="status" className="border-brand-green/20 bg-brand-green-light/60">
            <CheckCircle2 aria-hidden="true" className="text-brand-green" />
            <AlertTitle>{textes.alerteFaiteTitre}</AlertTitle>
            <AlertDescription>{textes.alerteFaite}</AlertDescription>
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
              {rejectedToken === token ? textes.lienRejete : textes.lienAbsent}
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to={textes.actionLienInvalide.vers}>{textes.actionLienInvalide.libelle}</Link>
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {serverError ? (
              <Alert variant="destructive">
                <AlertTitle>{textes.erreurTitre}</AlertTitle>
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
                      disabled={mutation.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>{MOT_DE_PASSE_LONGUEUR_MIN} caractères minimum.</FormDescription>
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
                      disabled={mutation.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" className="h-12 w-full rounded-xl" disabled={mutation.isPending}>
              {mutation.isPending ? textes.boutonEnCours : "Enregistrer le mot de passe"}
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

export function ResetPasswordPage() {
  return (
    <TokenPasswordPage
      mutation={useResetPassword()}
      textes={{
        eyebrow: "UN NOUVEAU DÉPART",
        titre: "Nouveau mot de passe",
        titreFait: "Votre accès est rétabli",
        description: "Choisissez un mot de passe personnel pour sécuriser votre compte.",
        descriptionFaite:
          "Vous pouvez maintenant vous reconnecter à votre espace GreenFinance-Scorer.",
        alerteFaiteTitre: "Mot de passe mis à jour",
        alerteFaite:
          "Connectez-vous avec votre nouveau mot de passe. Ce lien ne peut plus être utilisé.",
        erreurTitre: "Réinitialisation impossible",
        erreurServeur:
          "Le mot de passe n’a pas pu être modifié. Vérifiez votre connexion et réessayez dans quelques instants.",
        lienRejete:
          "Ce lien est invalide, a expiré ou a déjà été utilisé. Demandez un nouveau lien pour réinitialiser votre mot de passe.",
        lienAbsent:
          "Le lien de réinitialisation est absent ou incomplet. Ouvrez le lien reçu par e-mail ou demandez-en un nouveau.",
        actionLienInvalide: { libelle: "Demander un nouveau lien", vers: "/mot-de-passe-oublie" },
        boutonEnCours: "Modification en cours…",
      }}
    />
  );
}

/** Cible du lien envoyé à la création d'un compte (app/auth/activation.py::_construire_lien).
 * Un lien expiré ne se renouvelle pas en libre-service : seul l'Administrateur peut renvoyer une
 * invitation (POST /admin/utilisateurs/{id}/renvoyer-activation). */
export function ActivateAccountPage() {
  return (
    <TokenPasswordPage
      mutation={useActivateAccount()}
      textes={{
        eyebrow: "BIENVENUE",
        titre: "Activez votre compte",
        titreFait: "Votre compte est activé",
        description: "Choisissez le mot de passe qui protégera votre compte GreenFinance-Scorer.",
        descriptionFaite: "Vous pouvez maintenant vous connecter à votre espace.",
        alerteFaiteTitre: "Compte activé",
        alerteFaite:
          "Connectez-vous avec l’adresse de votre invitation et ce mot de passe. Ce lien ne peut plus être utilisé.",
        erreurTitre: "Activation impossible",
        erreurServeur:
          "Le compte n’a pas pu être activé. Vérifiez votre connexion et réessayez dans quelques instants.",
        lienRejete:
          "Ce lien d’activation est invalide, a expiré ou a déjà été utilisé. Demandez à l’administrateur de vous renvoyer une invitation.",
        lienAbsent:
          "Le lien d’activation est absent ou incomplet. Ouvrez le lien reçu par e-mail.",
        actionLienInvalide: { libelle: "Contacter l’équipe", vers: "/contact" },
        boutonEnCours: "Activation en cours…",
      }}
    />
  );
}
