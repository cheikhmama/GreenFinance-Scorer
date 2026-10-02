import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Send } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { ApiError } from "@/shared/api/errors";
import { requestAccess } from "@/shared/api/generated/access-requests/access-requests";
import type {
  AccessRequestCreate,
  InvestorType,
  ResearchDomain,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  LIBELLES_DOMAINE_RECHERCHE,
  LIBELLES_TYPE_INVESTISSEUR,
} from "@/shared/format/demandeAcces";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { RegistrationConfirmation } from "./RegistrationConfirmation";

type Profil = "investisseur" | "chercheur";

/** Ce qui distingue les deux formulaires : libellés, liste de précision, rôle demandé. */
const PROFILS = {
  investisseur: {
    role: "INVESTOR",
    titre: "Accès investisseur",
    email: "E-mail professionnel",
    organisation: "Nom du fonds / Organisation",
    precision: "Type d’investisseur",
    options: Object.entries(LIBELLES_TYPE_INVESTISSEUR),
  },
  chercheur: {
    role: "RESEARCHER",
    titre: "Accès chercheur",
    email: "E-mail institutionnel",
    organisation: "Université / Institut de recherche",
    precision: "Domaine de recherche",
    options: Object.entries(LIBELLES_DOMAINE_RECHERCHE),
  },
} as const;

const schema = z.object({
  full_name: z.string().trim().min(2, "Votre nom est requis.").max(100),
  email: z
    .string()
    .trim()
    .min(1, "L’adresse e-mail est requise")
    .pipe(z.email("Adresse e-mail invalide")),
  organization: z.string().trim().min(2, "Ce champ est requis.").max(200),
  precision: z.string().min(1, "Choisissez une option."),
  website_fax: z.string(),
});

type DemandeForm = z.infer<typeof schema>;

function messageErreur(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Plusieurs demandes ont été envoyées récemment depuis votre connexion. Réessayez dans une heure.";
  }
  if (error instanceof ApiError && error.status === 503) {
    return "Le service de notification e-mail est momentanément indisponible. Veuillez réessayer plus tard.";
  }
  return "La demande n’a pas pu être envoyée. Vérifiez vos informations et réessayez.";
}

/** Inscription d'un Investisseur ou d'un Chercheur (POST /access-requests, tâche 5.10) : le compte
 * n'est ouvert qu'après validation par un administrateur. */
export function AccessRequestPage({ profil }: { profil: Profil }) {
  const config = PROFILS[profil];
  const envoi = useMutation<unknown, ApiError, AccessRequestCreate>({
    mutationFn: (corps) => requestAccess(corps),
    retry: false,
  });
  const form = useForm<DemandeForm>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", organization: "", precision: "", website_fax: "" },
  });

  function onSubmit(valeurs: DemandeForm) {
    if (envoi.isPending) return;
    envoi.mutate({
      role: config.role,
      full_name: valeurs.full_name,
      email: valeurs.email,
      organization: valeurs.organization,
      ...(config.role === "INVESTOR"
        ? { investor_type: valeurs.precision as InvestorType }
        : { research_domain: valeurs.precision as ResearchDomain }),
      website_fax: valeurs.website_fax || null,
    });
  }

  return (
    <AuthLayout eyebrow="REJOINDRE LA PLATEFORME" title={config.titre}>
      {envoi.isSuccess ? (
        <RegistrationConfirmation />
      ) : (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
            {envoi.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Envoi impossible</AlertTitle>
                <AlertDescription>{messageErreur(envoi.error)}</AlertDescription>
              </Alert>
            ) : null}
            <fieldset disabled={envoi.isPending} className="grid min-w-0 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="full_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nom & Prénom</FormLabel>
                    <FormControl>
                      <Input autoComplete="name" className="h-11 rounded-xl" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{config.email}</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        autoComplete="email"
                        className="h-11 rounded-xl"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="organization"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>{config.organisation}</FormLabel>
                    <FormControl>
                      <Input autoComplete="organization" className="h-11 rounded-xl" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="precision"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>{config.precision}</FormLabel>
                    <FormControl>
                      <Select className="h-11 rounded-xl" {...field}>
                        <option value="" disabled>
                          Choisir…
                        </option>
                        {config.options.map(([valeur, libelle]) => (
                          <option key={valeur} value={valeur}>
                            {libelle}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {/* Champ piège (app/access_requests/service.py) : hors écran, jamais atteint au
                  clavier ni annoncé — seul un robot le remplit. */}
              <div
                aria-hidden="true"
                className="absolute -left-[10000px] h-px w-px overflow-hidden"
              >
                <label>
                  Fax
                  <input tabIndex={-1} autoComplete="off" {...form.register("website_fax")} />
                </label>
              </div>
            </fieldset>
            <Button type="submit" className="h-12 w-full rounded-xl" disabled={envoi.isPending}>
              <Send className="size-4" />
              {envoi.isPending ? "Envoi en cours…" : "Envoyer la demande"}
            </Button>
          </form>
        </Form>
      )}
      <Link
        to="/inscription"
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Choisir un autre profil
      </Link>
    </AuthLayout>
  );
}
