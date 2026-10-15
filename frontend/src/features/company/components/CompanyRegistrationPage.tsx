import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Building2, Download } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link } from "react-router-dom";
import { EmailVerificationStep } from "@/features/registration/components/EmailVerificationStep";
import { RegistrationConfirmation } from "@/features/registration/components/RegistrationConfirmation";
import {
  exempleIdentifiantFiscal,
  libelleIdentifiantFiscal,
  OPTIONS_PAYS,
  OPTIONS_SECTEURS,
} from "@/features/registration/referentiels";
import { ApiError } from "@/shared/api/errors";
import { AuthLayout } from "@/shared/layout/AuthLayout";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Combobox } from "@/shared/ui/combobox";
import { FileDrop } from "@/shared/ui/file-drop";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { WizardStepper } from "@/shared/ui/wizard";
import { useRegisterCompany } from "../api";
import { type CompanyRegistrationForm, companyRegistrationFormSchema } from "../schemas";

const MODELE_MANDAT = "/modeles/lettre-de-mandat.docx";

function messageErreur(error: unknown) {
  if (error instanceof ApiError && error.status === 429) {
    return "Plusieurs demandes ont été envoyées récemment depuis votre connexion. Réessayez dans une heure.";
  }
  if (error instanceof ApiError && error.status === 503) {
    return "Le service de notification e-mail est momentanément indisponible. Veuillez réessayer plus tard.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "Certaines informations sont invalides : vérifiez les champs signalés et la lettre de mandat (PDF).";
  }
  return "La demande n’a pas pu être envoyée. Vérifiez votre connexion et réessayez.";
}

type ChampTexte = "company_name" | "contact_name" | "contact_email" | "tax_id";

const CLASSE_CHAMP = "h-11 rounded-xl";

const ETAPES_INSCRIPTION = [
  { id: "entreprise", titre: "Entreprise" },
  { id: "contact", titre: "Contact & mandat" },
  { id: "identifiants", titre: "Identifiants (facultatifs)" },
] as const;
type EtapeInscription = (typeof ETAPES_INSCRIPTION)[number]["id"];

const CHAMPS_INSCRIPTION = {
  entreprise: ["company_name", "sector", "country", "tax_id"],
  contact: ["contact_name", "contact_email", "mandate_letter"],
  identifiants: ["lei", "isin", "website"],
} as const satisfies Record<EtapeInscription, readonly (keyof CompanyRegistrationForm)[]>;

/** Étape qui porte le premier champ en erreur — une règle croisée (adresse / site) n'est connue
 * qu'à l'envoi, l'utilisateur doit être ramené là où il peut corriger. */
export function etapeDeLErreur(
  erreurs: Partial<Record<keyof CompanyRegistrationForm, unknown>>,
): EtapeInscription | null {
  for (const { id } of ETAPES_INSCRIPTION) {
    if (CHAMPS_INSCRIPTION[id].some((champ) => erreurs[champ])) return id;
  }
  return null;
}

/** Inscription publique d'une entreprise (POST /companies/register, tâches 5.2, 5.10) : identité,
 * identifiant fiscal selon le pays, contact et lettre de mandat ; assistant en trois étapes (ISIN,
 * LEI et site web, facultatifs, à la dernière : ils accélèrent les contrôles KYC). La réponse est la même que la demande
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
  const [etape, setEtape] = useState<EtapeInscription>("entreprise");
  const [adresseConfirmee, setAdresseConfirmee] = useState(false);
  const indexEtape = ETAPES_INSCRIPTION.findIndex((e) => e.id === etape);
  const derniereEtape = indexEtape === ETAPES_INSCRIPTION.length - 1;

  async function etapeSuivante() {
    if (await form.trigger([...CHAMPS_INSCRIPTION[etape]])) {
      setEtape(ETAPES_INSCRIPTION[indexEtape + 1].id);
    }
  }

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
      {adresseConfirmee ? (
        <RegistrationConfirmation />
      ) : register.isSuccess && register.variables ? (
        // La demande attend la confirmation de l'adresse (tâche 5.11).
        <EmailVerificationStep
          email={register.variables.contact_email}
          onVerified={() => setAdresseConfirmee(true)}
        />
      ) : (
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit, (erreurs) => {
              const cible = etapeDeLErreur(erreurs);
              if (cible) setEtape(cible);
            })}
            className="space-y-5"
            noValidate
          >
            <WizardStepper etapes={ETAPES_INSCRIPTION} courante={etape} />
            {register.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Envoi impossible</AlertTitle>
                <AlertDescription>{messageErreur(register.error)}</AlertDescription>
              </Alert>
            ) : null}
            <fieldset disabled={register.isPending} className="grid min-w-0 gap-4 sm:grid-cols-2">
              {etape === "entreprise" ? (
                <>
                  <div className="sm:col-span-2">
                    {champTexte("company_name", "Nom de l’entreprise", {
                      autoComplete: "organization",
                      placeholder: "Raison sociale",
                    })}
                  </div>
                  <FormField
                    control={form.control}
                    name="sector"
                    render={({ field: { value, onChange, ...field } }) => (
                      <FormItem>
                        <FormLabel>Secteur d’activité</FormLabel>
                        <FormControl>
                          <Combobox
                            {...field}
                            value={value}
                            onValueChange={onChange}
                            options={OPTIONS_SECTEURS}
                            searchPlaceholder="Rechercher un secteur…"
                            emptyText="Aucun secteur ne correspond."
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="country"
                    render={({ field: { value, onChange, ...field } }) => (
                      <FormItem>
                        <FormLabel>Pays</FormLabel>
                        <FormControl>
                          <Combobox
                            {...field}
                            value={value}
                            onValueChange={onChange}
                            options={OPTIONS_PAYS}
                            searchPlaceholder="Rechercher un pays…"
                            emptyText="Aucun pays ne correspond."
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <div className="sm:col-span-2">
                    {champTexte("tax_id", libelleIdentifiantFiscal(pays ?? ""), {
                      placeholder: pays
                        ? exempleIdentifiantFiscal(pays)
                        : "Choisissez d’abord le pays",
                    })}
                  </div>
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
                </>
              ) : null}
              {etape === "contact" ? (
                <>
                  {champTexte("contact_name", "Nom & Prénom du responsable", {
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
                    render={({ field: { value, onChange, onBlur, name, ref } }) => (
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
                </>
              ) : null}
              {etape === "identifiants" ? (
                <>
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
                      <FormItem className="sm:col-span-2">
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
                </>
              ) : null}
            </fieldset>
            <div className="flex gap-3">
              {indexEtape > 0 ? (
                <Button
                  type="button"
                  variant="outline"
                  className="h-12 rounded-xl"
                  disabled={register.isPending}
                  onClick={() => setEtape(ETAPES_INSCRIPTION[indexEtape - 1].id)}
                >
                  Précédent
                </Button>
              ) : null}
              {derniereEtape ? (
                <Button
                  type="submit"
                  className="h-12 flex-1 rounded-xl"
                  disabled={register.isPending}
                >
                  <Building2 className="size-4" />
                  {register.isPending ? "Envoi en cours…" : "Envoyer la demande"}
                </Button>
              ) : (
                <Button type="button" className="h-12 flex-1 rounded-xl" onClick={etapeSuivante}>
                  Suivant
                  <ArrowRight className="size-4" />
                </Button>
              )}
            </div>
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
