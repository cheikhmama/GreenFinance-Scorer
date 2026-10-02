import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Check, Clock, FileUp, MailCheck, RotateCcw, XCircle } from "lucide-react";
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
import { cn } from "@/shared/ui/cn";
import { FileDrop } from "@/shared/ui/file-drop";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/ui/form";
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
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
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

/** Trois étapes vues par le demandeur : envoi, examen, décision. Une demande d'informations
 * garde l'examen en cours, mais signale qu'une action est attendue de sa part. */
type Etat = "fait" | "en-cours" | "action" | "refus" | "a-venir";

function etapes(statut: RegistrationStatusView["status"]): { libelle: string; etat: Etat }[] {
  const examen: Etat =
    statut === "INFO_REQUESTED" ? "action" : statut === "PENDING_ONBOARDING" ? "en-cours" : "fait";
  const decision: Etat =
    statut === "REJECTED"
      ? "refus"
      : statut === "ACTIVE" || statut === "SUSPENDED"
        ? "fait"
        : "a-venir";
  return [
    { libelle: "Demande envoyée", etat: "fait" },
    { libelle: "Examen (24h à 48h)", etat: examen },
    { libelle: "Décision", etat: decision },
  ];
}

const LIBELLE_ETAT: Record<Etat, string> = {
  fait: "terminée",
  "en-cours": "en cours",
  action: "action requise",
  refus: "refusée",
  "a-venir": "à venir",
};

function Progression({ statut }: { statut: RegistrationStatusView["status"] }) {
  const liste = etapes(statut);
  return (
    <ol aria-label="Avancement de la demande" className="flex items-start">
      {liste.map(({ libelle, etat }, index) => (
        <li
          key={libelle}
          aria-current={etat === "en-cours" || etat === "action" ? "step" : undefined}
          className="relative flex flex-1 flex-col items-center gap-2 text-center"
        >
          {index > 0 ? (
            <span
              aria-hidden="true"
              className={cn(
                "absolute top-3.5 right-1/2 h-px w-full -translate-x-4",
                liste[index - 1].etat === "fait" ? "bg-primary" : "bg-border",
              )}
            />
          ) : null}
          <span
            className={cn(
              "relative z-10 flex size-7 items-center justify-center rounded-full border text-xs",
              etat === "fait" && "border-primary bg-primary text-primary-foreground",
              etat === "en-cours" &&
                "border-primary bg-background text-primary ring-4 ring-primary/15",
              etat === "action" &&
                "border-amber-500 bg-background text-amber-600 ring-4 ring-amber-500/15",
              etat === "refus" && "border-destructive bg-destructive text-white",
              etat === "a-venir" && "border-border bg-muted text-muted-foreground",
            )}
          >
            {etat === "fait" ? (
              <Check className="size-3.5" aria-hidden="true" />
            ) : etat === "refus" ? (
              <XCircle className="size-3.5" aria-hidden="true" />
            ) : etat === "action" ? (
              <FileUp className="size-3.5" aria-hidden="true" />
            ) : (
              index + 1
            )}
          </span>
          <span
            className={cn(
              "text-xs",
              etat === "a-venir" ? "text-muted-foreground" : "font-medium text-foreground",
            )}
          >
            {libelle}
            <span className="sr-only"> ({LIBELLE_ETAT[etat]})</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function Suivi({ vue, token }: { vue: RegistrationStatusView; token: string }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-muted/30 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-foreground">{vue.company_name}</p>
          {vue.registered_at ? (
            <p className="text-xs text-muted-foreground">
              Demande envoyée le {dateCourte(vue.registered_at)}
            </p>
          ) : null}
        </div>
        <Badge variant={variantStatutInscription(vue.status)}>
          {libelleStatutInscription(vue.status)}
        </Badge>
      </div>

      <Progression statut={vue.status} />

      {vue.status === "PENDING_ONBOARDING" ? (
        <Alert>
          <Clock aria-hidden="true" />
          <AlertTitle>Examen en cours</AlertTitle>
          <AlertDescription>
            Un administrateur vérifie vos informations, généralement sous 24h à 48h ouvrées. Vous
            serez prévenu par e-mail ; ce lien reste valable jusqu’à la décision.
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
        <>
          <Alert variant="destructive">
            <XCircle aria-hidden="true" />
            <AlertTitle>Demande refusée le {dateCourte(vue.rejected_at)}</AlertTitle>
            <AlertDescription>
              <p className="whitespace-pre-line">{vue.rejection_reason}</p>
            </AlertDescription>
          </Alert>
          <Button asChild variant="outline" className="h-11 w-full rounded-xl">
            <Link to="/inscription/entreprise">
              <RotateCcw className="size-4" aria-hidden="true" />
              Déposer une nouvelle demande
            </Link>
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Avec les mêmes identifiants, votre demande précédente est rouverte.
          </p>
        </>
      ) : null}

      {vue.status === "ACTIVE" || vue.status === "SUSPENDED" ? (
        <>
          <Alert className="border-primary/20 bg-secondary/60">
            <MailCheck aria-hidden="true" className="text-primary" />
            <AlertTitle>Demande validée</AlertTitle>
            <AlertDescription>
              Ouvrez le lien d’activation reçu par e-mail pour créer votre mot de passe : vous
              entrerez directement dans votre espace. Il est valable 72 heures.
            </AlertDescription>
          </Alert>
          <Button asChild className="h-11 w-full rounded-xl">
            <Link to="/login">J’ai déjà activé mon compte : me connecter</Link>
          </Button>
        </>
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
            render={({ field: { value, onChange, onBlur, name, ref } }) => (
              <FormItem>
                <FormLabel>Nouvelle lettre de mandat (PDF)</FormLabel>
                <FormControl>
                  <FileDrop
                    accept="application/pdf"
                    hint="PDF signé, 5 Mo au maximum"
                    file={value}
                    onFile={onChange}
                    name={name}
                    ref={ref}
                    onBlur={onBlur}
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
