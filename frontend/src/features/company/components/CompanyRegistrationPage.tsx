import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Building2, CheckCircle2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
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
import { Input } from "@/shared/ui/input";
import { useRegisterCompany } from "../api";
import { type CompanyRegistrationForm, companyRegistrationFormSchema } from "../schemas";

function messageErreur(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Plusieurs demandes ont été envoyées récemment depuis votre connexion. Réessayez dans une heure.";
  }
  if (error instanceof ApiError && error.status === 503) {
    return "Le service d’inscription est momentanément indisponible. Réessayez plus tard.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "Certaines informations sont invalides : vérifiez notamment l’ISIN, le LEI et la lettre de mandat (PDF).";
  }
  return "La demande n’a pas pu être envoyée. Vérifiez votre connexion et réessayez.";
}

const CHAMPS: {
  name: Exclude<keyof CompanyRegistrationForm, "company_fax" | "mandate_letter">;
  label: string;
  description?: string;
  autoComplete?: string;
  type?: string;
}[] = [
  { name: "company_name", label: "Nom de l’entreprise", autoComplete: "organization" },
  { name: "sector", label: "Secteur d’activité" },
  {
    name: "country",
    label: "Pays",
    description: "Code à deux lettres, ex. MR.",
    autoComplete: "country",
  },
  { name: "website", label: "Site web (facultatif)", autoComplete: "url", type: "url" },
  { name: "isin", label: "ISIN (facultatif)", description: "Pour une entreprise cotée." },
  {
    name: "lei",
    label: "LEI (facultatif)",
    description: "Legal Entity Identifier, 20 caractères.",
  },
  { name: "contact_name", label: "Votre nom", autoComplete: "name" },
  {
    name: "contact_email",
    label: "Votre e-mail professionnel",
    autoComplete: "email",
    type: "email",
  },
];

/** Inscription publique d'une entreprise (POST /companies/register, décision D5). Champs
 * d'identité, contact et lettre de mandat (tâche 5.2). La réponse est la même que la demande
 * aboutisse ou non : le résultat arrive par e-mail avec un lien de suivi, et le lien pour créer un
 * mot de passe n'est envoyé qu'après validation par un administrateur. */
export function CompanyRegistrationPage() {
  const register = useRegisterCompany();
  const form = useForm<CompanyRegistrationForm>({
    resolver: zodResolver(companyRegistrationFormSchema),
    defaultValues: {
      company_name: "",
      sector: "",
      country: "",
      isin: "",
      lei: "",
      website: "",
      contact_name: "",
      contact_email: "",
      company_fax: "",
      mandate_letter: undefined,
    },
  });

  function onSubmit(values: CompanyRegistrationForm) {
    if (register.isPending) return;
    register.mutate({
      ...values,
      country: values.country.toUpperCase(),
      isin: values.isin || null,
      lei: values.lei || null,
      website: values.website || null,
      company_fax: values.company_fax || null,
    });
  }

  return (
    <AuthLayout
      eyebrow="REJOINDRE LA PLATEFORME"
      title="Inscrire mon entreprise"
      description="Présentez votre entreprise : un administrateur valide chaque inscription avant l’ouverture de votre espace."
    >
      {register.isSuccess ? (
        <div className="space-y-5">
          <Alert role="status" className="border-brand-green/20 bg-brand-green-light/60">
            <CheckCircle2 aria-hidden="true" className="text-brand-green" />
            <AlertTitle>Demande envoyée</AlertTitle>
            <AlertDescription>
              Nous vous écrivons à {register.variables?.contact_email}, avec un lien pour suivre
              votre demande. Après validation de votre entreprise, vous recevrez un lien pour créer
              votre mot de passe.
            </AlertDescription>
          </Alert>
          <Button asChild className="h-12 w-full rounded-xl">
            <Link to="/login">Retour à la connexion</Link>
          </Button>
        </div>
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {register.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Envoi impossible</AlertTitle>
                <AlertDescription>{messageErreur(register.error)}</AlertDescription>
              </Alert>
            ) : null}
            <fieldset disabled={register.isPending} className="grid min-w-0 gap-4 sm:grid-cols-2">
              {CHAMPS.map((champ) => (
                <FormField
                  key={champ.name}
                  control={form.control}
                  name={champ.name}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{champ.label}</FormLabel>
                      <FormControl>
                        <Input
                          type={champ.type ?? "text"}
                          autoComplete={champ.autoComplete}
                          className="h-11 rounded-xl"
                          {...field}
                        />
                      </FormControl>
                      {champ.description ? (
                        <FormDescription>{champ.description}</FormDescription>
                      ) : null}
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))}
              <FormField
                control={form.control}
                name="mandate_letter"
                render={({ field: { onChange, onBlur, name, ref } }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>Lettre de mandat (PDF)</FormLabel>
                    <FormControl>
                      <Input
                        type="file"
                        accept="application/pdf"
                        className="h-11 rounded-xl"
                        name={name}
                        ref={ref}
                        onBlur={onBlur}
                        onChange={(event) => onChange(event.target.files?.[0])}
                      />
                    </FormControl>
                    <FormDescription>
                      Signée par un représentant légal, elle vous autorise à inscrire l’entreprise.
                      5 Mo au plus.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {/* Champ piège (app/company/registration.py) : hors écran, jamais atteint au clavier
                  ni annoncé par un lecteur d'écran — seul un robot le remplit. */}
              <div
                aria-hidden="true"
                className="absolute -left-[10000px] h-px w-px overflow-hidden"
              >
                <label>
                  Fax
                  <input tabIndex={-1} autoComplete="off" {...form.register("company_fax")} />
                </label>
              </div>
            </fieldset>
            <Button type="submit" className="h-12 w-full rounded-xl" disabled={register.isPending}>
              <Building2 className="size-4" />
              {register.isPending ? "Envoi en cours…" : "Envoyer la demande"}
            </Button>
          </form>
        </Form>
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
