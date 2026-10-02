import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Clock, FileUp, MailCheck, XCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { RegistrationStatusView } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleStatutInscription,
  variantStatutInscription,
} from "@/shared/format/statutInscription";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
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
import { Input } from "@/shared/ui/input";
import { Skeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useRegistrationStatus, useReplyToRegistrationInfoRequest } from "../api";
import { type ReponseDemandeInfosForm, reponseDemandeInfosSchema } from "../schemas";

// secrets.token_urlsafe(32), émis par app/company/registration.py::nouveau_jeton_de_suivi.
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

function dateCourte(date: string | null) {
  return date ? new Date(date).toLocaleDateString("fr-FR") : "";
}

/** Page de suivi publique d'une demande d'inscription (tâche 5.2), ouverte depuis le lien reçu par
 * e-mail. Le jeton n'est jamais consommé : le demandeur revient sur le même lien jusqu'à la
 * décision, et un lien plus récent (nouvelle demande) remplace l'ancien. */
export function RegistrationStatusPage() {
  const [searchParams] = useSearchParams();
  const tokens = searchParams.getAll("token");
  const token = tokens.length === 1 && TOKEN_PATTERN.test(tokens[0]) ? tokens[0] : null;
  const suivi = useRegistrationStatus(token);

  return (
    <AuthLayout
      eyebrow="DEMANDE D’INSCRIPTION"
      title="Suivi de votre demande"
      description="L’état de votre demande d’inscription, tel qu’examiné par notre équipe."
    >
      {token === null ? (
        <LienInvalide />
      ) : suivi.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : suivi.isError ? (
        suivi.error instanceof ApiError && suivi.error.status === 404 ? (
          <LienInvalide />
        ) : (
          <Alert variant="destructive">
            <AlertTitle>Suivi indisponible</AlertTitle>
            <AlertDescription>Réessayez dans quelques instants.</AlertDescription>
          </Alert>
        )
      ) : (
        <Suivi vue={suivi.data} token={token} />
      )}
      <Link
        to="/login"
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-brand-green underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Retour à la connexion
      </Link>
    </AuthLayout>
  );
}

function LienInvalide() {
  return (
    <Alert variant="destructive">
      <AlertTitle>Lien de suivi invalide</AlertTitle>
      <AlertDescription>
        Ce lien n’est pas reconnu. Si vous avez déposé une nouvelle demande, utilisez le lien du
        dernier e-mail reçu.
      </AlertDescription>
    </Alert>
  );
}

function Suivi({ vue, token }: { vue: RegistrationStatusView; token: string }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-brand-blue">{vue.company_name}</p>
        <Badge variant={variantStatutInscription(vue.status)}>
          {libelleStatutInscription(vue.status)}
        </Badge>
      </div>
      {vue.registered_at ? (
        <p className="text-sm text-brand-grey">
          Demande envoyée le {dateCourte(vue.registered_at)}.
        </p>
      ) : null}

      {vue.status === "PENDING_ONBOARDING" ? (
        <Alert>
          <Clock aria-hidden="true" />
          <AlertTitle>En cours d’examen</AlertTitle>
          <AlertDescription>
            Un administrateur examine votre demande. Vous serez prévenu par e-mail.
          </AlertDescription>
        </Alert>
      ) : null}

      {vue.status === "INFO_REQUESTED" ? (
        <>
          <Alert className="border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/60">
            <FileUp aria-hidden="true" />
            <AlertTitle>Informations demandées le {dateCourte(vue.info_requested_at)}</AlertTitle>
            <AlertDescription className="whitespace-pre-line">
              {vue.info_request_message}
            </AlertDescription>
          </Alert>
          {vue.can_respond ? <FormulaireReponse token={token} /> : null}
        </>
      ) : null}

      {vue.status === "REJECTED" ? (
        <Alert variant="destructive">
          <XCircle aria-hidden="true" />
          <AlertTitle>Demande refusée le {dateCourte(vue.rejected_at)}</AlertTitle>
          <AlertDescription className="space-y-2">
            <p className="whitespace-pre-line">{vue.rejection_reason}</p>
            <p>
              Vous pouvez{" "}
              <Link to="/inscription/entreprise" className="font-medium underline">
                déposer une nouvelle demande
              </Link>{" "}
              avec les mêmes identifiants.
            </p>
          </AlertDescription>
        </Alert>
      ) : null}

      {vue.status === "ACTIVE" || vue.status === "SUSPENDED" ? (
        <Alert className="border-brand-green/20 bg-brand-green-light/60">
          <MailCheck aria-hidden="true" className="text-brand-green" />
          <AlertTitle>Demande validée</AlertTitle>
          <AlertDescription>
            Utilisez le lien reçu par e-mail pour créer votre mot de passe, puis connectez-vous.
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}

function FormulaireReponse({ token }: { token: string }) {
  const repondre = useReplyToRegistrationInfoRequest(token);
  const form = useForm<ReponseDemandeInfosForm>({
    resolver: zodResolver(reponseDemandeInfosSchema),
    defaultValues: { mandate_letter: undefined, message: "" },
  });

  function onSubmit(values: ReponseDemandeInfosForm) {
    if (repondre.isPending) return;
    repondre.mutate({ mandate_letter: values.mandate_letter, message: values.message || null });
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {repondre.isError ? (
          <Alert variant="destructive">
            <AlertTitle>Envoi impossible</AlertTitle>
            <AlertDescription>
              {repondre.error.status === 422
                ? "Le fichier n’est pas un PDF valide de 5 Mo au plus."
                : repondre.error.status === 429
                  ? "Plusieurs envois récents depuis votre connexion : réessayez dans une heure."
                  : "La réponse n’a pas pu être envoyée. Réessayez."}
            </AlertDescription>
          </Alert>
        ) : null}
        <fieldset disabled={repondre.isPending} className="space-y-4">
          <FormField
            control={form.control}
            name="mandate_letter"
            render={({ field: { onChange, onBlur, name, ref } }) => (
              <FormItem>
                <FormLabel>Nouvelle lettre de mandat (PDF)</FormLabel>
                <FormControl>
                  <Input
                    type="file"
                    accept="application/pdf"
                    name={name}
                    ref={ref}
                    onBlur={onBlur}
                    onChange={(event) => onChange(event.target.files?.[0])}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="message"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Message (facultatif)</FormLabel>
                <FormControl>
                  <Textarea rows={3} {...field} />
                </FormControl>
                <FormDescription>Précisions pour l’administrateur.</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </fieldset>
        <Button type="submit" className="h-11 w-full rounded-xl" disabled={repondre.isPending}>
          {repondre.isPending ? "Envoi en cours…" : "Envoyer ma réponse"}
        </Button>
      </form>
    </Form>
  );
}
