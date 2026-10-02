import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Building2, ChevronDown, Download } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router-dom";
import { RegistrationConfirmation } from "@/features/registration/components/RegistrationConfirmation";
import {
  exempleIdentifiantFiscal,
  libelleIdentifiantFiscal,
  PAYS,
  SECTEURS,
} from "@/features/registration/referentiels";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/shared/ui/collapsible";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { useRegisterCompany } from "../api";
import { type CompanyRegistrationForm, companyRegistrationFormSchema } from "../schemas";

const MODELE_MANDAT = "/modeles/lettre-de-mandat.docx";

function messageErreur(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Plusieurs demandes ont été envoyées récemment depuis votre connexion. Réessayez dans une heure.";
  }
  if (error instanceof ApiError && error.status === 503) {
    return "Le service d’inscription est momentanément indisponible. Réessayez plus tard.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "Certaines informations sont invalides : vérifiez les champs signalés et la lettre de mandat (PDF).";
  }
  return "La demande n’a pas pu être envoyée. Vérifiez votre connexion et réessayez.";
}

type ChampTexte = "company_name" | "contact_name" | "contact_email" | "tax_id";

const CLASSE_CHAMP = "h-11 rounded-xl";

/** Inscription publique d'une entreprise (POST /companies/register, tâches 5.2, 5.10) : identité,
 * identifiant fiscal selon le pays, contact et lettre de mandat ; ISIN, LEI et site web dans un
 * bloc facultatif replié (ils accélèrent les contrôles KYC). La réponse est la même que la demande
 * aboutisse ou non : la suite arrive par e-mail. */
export function CompanyRegistrationPage() {
  const register = useRegisterCompany();
  const form = useForm<CompanyRegistrationForm>({
    resolver: zodResolver(companyRegistrationFormSchema),
    defaultValues: {
      company_name: "",
      sector: "",
      country: "",
      tax_id: "",
      isin: "",
      lei: "",
      website: "",
      contact_name: "",
      contact_email: "",
      company_fax: "",
      mandate_letter: undefined,
    },
  });
  const pays = useWatch({ control: form.control, name: "country" });
  const [complementsOuverts, setComplementsOuverts] = useState(false);
  const champsSupplementairesEnErreur = Boolean(
    form.formState.errors.isin || form.formState.errors.lei || form.formState.errors.website,
  );

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

  function champTexte(
    name: ChampTexte,
    label: string,
    options: { type?: string; autoComplete?: string; placeholder?: string } = {},
  ) {
    return (
      <FormField
        control={form.control}
        name={name}
        render={({ field }) => (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <Input
                type={options.type ?? "text"}
                autoComplete={options.autoComplete}
                placeholder={options.placeholder}
                className={CLASSE_CHAMP}
                {...field}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    );
  }

  return (
    <AuthLayout eyebrow="REJOINDRE LA PLATEFORME" title="Inscrire mon entreprise">
      {register.isSuccess ? (
        <RegistrationConfirmation profil="Entreprise" />
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
              <div className="sm:col-span-2">
                {champTexte("company_name", "Nom de l’entreprise", {
                  autoComplete: "organization",
                  placeholder: "Raison sociale",
                })}
              </div>
              <FormField
                control={form.control}
                name="sector"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Secteur d’activité</FormLabel>
                    <FormControl>
                      <Select className={CLASSE_CHAMP} {...field}>
                        <option value="" disabled>
                          Choisir…
                        </option>
                        {SECTEURS.map((secteur) => (
                          <option key={secteur} value={secteur}>
                            {secteur}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="country"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pays</FormLabel>
                    <FormControl>
                      <Select className={CLASSE_CHAMP} autoComplete="country" {...field}>
                        <option value="" disabled>
                          Choisir…
                        </option>
                        {PAYS.map(({ code, nom }) => (
                          <option key={code} value={code}>
                            {nom}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="sm:col-span-2">
                {champTexte("tax_id", libelleIdentifiantFiscal(pays ?? ""), {
                  placeholder: pays ? exempleIdentifiantFiscal(pays) : "Choisissez d’abord le pays",
                })}
              </div>
              {champTexte("contact_name", "Nom du responsable", {
                autoComplete: "name",
                placeholder: "Prénom Nom",
              })}
              {champTexte("contact_email", "E-mail professionnel", {
                type: "email",
                autoComplete: "email",
                placeholder: "nom@entreprise.com",
              })}
              <FormField
                control={form.control}
                name="mandate_letter"
                render={({ field: { onChange, onBlur, name, ref } }) => (
                  <FormItem className="sm:col-span-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <FormLabel>Lettre de mandat signée (PDF)</FormLabel>
                      <a
                        href={MODELE_MANDAT}
                        download
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline"
                      >
                        <Download className="size-3.5" aria-hidden="true" />
                        Télécharger modèle .docx
                      </a>
                    </div>
                    <FormControl>
                      <Input
                        type="file"
                        accept="application/pdf"
                        className={CLASSE_CHAMP}
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

              {/* Facultatif, replié : ISIN, LEI et site web accélèrent les contrôles KYC (GLEIF,
                  domaine de l'e-mail). Ouvert d'office si l'un d'eux est en erreur. */}
              <Collapsible
                className="space-y-3 rounded-lg border border-border/60 bg-muted/20 p-4 sm:col-span-2"
                open={complementsOuverts || champsSupplementairesEnErreur}
                onOpenChange={setComplementsOuverts}
              >
                <CollapsibleTrigger className="group flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-muted-foreground hover:text-foreground">
                  <span>
                    Identifiants complémentaires (facultatif — accélère la vérification KYC)
                  </span>
                  <ChevronDown
                    className="size-4 shrink-0 transition group-data-[state=open]:rotate-180"
                    aria-hidden="true"
                  />
                </CollapsibleTrigger>
                <CollapsibleContent className="grid grid-cols-1 gap-4 pt-3 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="lei"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">
                          Code LEI (Legal Entity Identifier)
                        </FormLabel>
                        <FormControl>
                          <Input
                            className="h-9 text-xs"
                            placeholder="Ex : 5493001KJ957L9201584"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="isin"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel className="text-xs">Code ISIN</FormLabel>
                        <FormControl>
                          <Input
                            className="h-9 text-xs"
                            placeholder="Ex : FR0000120271"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="website"
                    render={({ field }) => (
                      <FormItem className="md:col-span-2">
                        <FormLabel className="text-xs">Site web officiel</FormLabel>
                        <FormControl>
                          <Input
                            type="url"
                            autoComplete="url"
                            className="h-9 text-xs"
                            placeholder="https://www.organisation.com"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CollapsibleContent>
              </Collapsible>

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
        to="/inscription"
        className="mt-6 flex items-center justify-center gap-2 rounded text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Choisir un autre profil
      </Link>
    </AuthLayout>
  );
}
