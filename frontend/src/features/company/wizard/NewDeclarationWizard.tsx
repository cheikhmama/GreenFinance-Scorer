import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { creerSlug } from "@/shared/format/slug";
import { libelleTypeRapport, titreDeclaration } from "@/shared/format/typeRapport";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { useConfirmationAbandon, WizardStepper } from "@/shared/ui/wizard";
import { useCompanyReports, useOpenDeclaration } from "../api";
import {
  corpsOuverture,
  DEVISES,
  type OuvrirDeclarationForm,
  ouvrirDeclarationSchema,
  TYPES_RAPPORT,
} from "../schemas";
import { separerDeclarations } from "../session/etat";
import { ETAPES_DECLARATION } from "./etapes";

const ANNEE_COURANTE = new Date().getFullYear();
/** Les exercices proposés : les cinq derniers, le plus récent clos en premier. */
const EXERCICES = Array.from({ length: 6 }, (_, i) => ANNEE_COURANTE - i);
const CHAMPS_EXERCICE = ["fiscal_year", "report_type"] as const;

/** Étapes 1 et 2 d'une déclaration (spec §3.1) : rien n'existe côté serveur avant « Créer le
 * brouillon » ; un seul formulaire pour les deux étapes, validé étape par étape. */
export function NewDeclarationWizard() {
  const { etape = "exercice" } = useParams();
  const { data: rapports, isPending } = useCompanyReports();
  if (etape !== "exercice" && etape !== "finances") {
    return <Navigate to="/company/declarations/nouvelle/exercice" replace />;
  }
  if (isPending || !rapports) return <Skeleton className="h-64 w-full" />;
  const { sessionBloquante } = separerDeclarations(rapports);
  const exercicesExclus = rapports
    .filter((r) => r.status === "VALIDATED" && r.fiscal_year !== null)
    .map((r) => r.fiscal_year as number);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Nouvelle déclaration"
        description="Rien n’est transmis avant la soumission ; le brouillon reste modifiable jusque-là."
      />
      {sessionBloquante ? (
        <Alert role="note" className="bg-muted/50">
          <Info className="text-primary" aria-hidden="true" />
          <AlertDescription>
            <span className="font-medium text-foreground">Une seule déclaration à la fois.</span>{" "}
            Terminez la déclaration{" "}
            <Link
              className="underline"
              to={`/company/declarations/${creerSlug(titreDeclaration(sessionBloquante), sessionBloquante.id)}`}
            >
              {titreDeclaration(sessionBloquante)}
            </Link>{" "}
            avant d’en ouvrir une autre.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid gap-6 md:grid-cols-[14rem_minmax(0,1fr)]">
          <WizardStepper etapes={ETAPES_DECLARATION} courante={etape} />
          <Formulaire etape={etape} exercicesExclus={exercicesExclus} />
        </div>
      )}
    </div>
  );
}

function Formulaire({
  etape,
  exercicesExclus,
}: {
  etape: "exercice" | "finances";
  exercicesExclus: number[];
}) {
  const navigate = useNavigate();
  const ouvrir = useOpenDeclaration();
  const [erreur, setErreur] = useState<string | null>(null);
  const departAutorise = useRef(false);
  const exercices = EXERCICES.filter((annee) => !exercicesExclus.includes(annee));
  const form = useForm<OuvrirDeclarationForm>({
    resolver: zodResolver(ouvrirDeclarationSchema),
    defaultValues: {
      report_type: "RAPPORT_ESG",
      fiscal_year: exercices[0] ?? ANNEE_COURANTE - 1,
    },
  });
  const devise = form.watch("currency");
  // isDirty n'est calculé par react-hook-form que s'il est lu au rendu : on le garde dans une ref
  // que le prédicat de navigation relit.
  const { isDirty } = form.formState;
  const saisieModifiee = useRef(false);
  saisieModifiee.current = isDirty;
  useConfirmationAbandon(
    (prochaine) =>
      !departAutorise.current &&
      saisieModifiee.current &&
      !prochaine.pathname.startsWith("/company/declarations/nouvelle"),
  );

  async function suivant() {
    if (await form.trigger([...CHAMPS_EXERCICE])) {
      navigate("/company/declarations/nouvelle/finances");
    }
  }

  function creer(valeurs: OuvrirDeclarationForm) {
    // Entrée dans un champ de l'étape 1 : on avance, on ne crée rien.
    if (etape !== "finances") {
      void suivant();
      return;
    }
    setErreur(null);
    ouvrir.mutate(corpsOuverture(valeurs), {
      onSuccess: (brouillon) => {
        departAutorise.current = true;
        const titre = titreDeclaration({
          type: brouillon.report_type,
          fiscal_year: brouillon.fiscal_year,
          version: brouillon.version,
        });
        navigate(`/company/declarations/${creerSlug(titre, brouillon.id)}/brouillon/document`);
      },
      onError: (error) =>
        setErreur(
          error instanceof ApiError ? error.message : "La déclaration n’a pas été ouverte.",
        ),
    });
  }

  function montant(field: { onChange: (v: number | undefined) => void }) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      const valeur = event.target.valueAsNumber;
      field.onChange(Number.isNaN(valeur) ? undefined : valeur);
    };
  }

  return (
    <Card>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(creer)} className="space-y-5" noValidate>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
            {etape === "exercice" ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="fiscal_year"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Exercice fiscal</FormLabel>
                        <FormControl>
                          <Select
                            {...field}
                            onChange={(event) => field.onChange(Number(event.target.value))}
                          >
                            {exercices.map((annee) => (
                              <option key={annee} value={annee}>
                                FY{annee}
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
                    name="report_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Type de rapport</FormLabel>
                        <FormControl>
                          <Select {...field}>
                            {TYPES_RAPPORT.map((type) => (
                              <option key={type} value={type}>
                                {libelleTypeRapport(type)}
                              </option>
                            ))}
                          </Select>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="flex justify-end border-t pt-4">
                  <Button type="button" onClick={suivant}>
                    Suivant
                  </Button>
                </div>
              </>
            ) : (
              <>
                <FormField
                  control={form.control}
                  name="currency"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Devise</FormLabel>
                      <FormControl>
                        <Select
                          {...field}
                          value={field.value ?? ""}
                          onChange={(event) => {
                            field.onChange(event.target.value || undefined);
                            if (!event.target.value) {
                              // Montants masqués : ils ne doivent plus bloquer la validation.
                              form.resetField("revenue");
                              form.resetField("enterprise_value");
                            }
                          }}
                        >
                          <option value="">Aucune donnée financière</option>
                          {DEVISES.map((d) => (
                            <option key={d} value={d}>
                              {d}
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {devise ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="revenue"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Chiffre d’affaires</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={0}
                              step="0.01"
                              name={field.name}
                              ref={field.ref}
                              onBlur={field.onBlur}
                              value={field.value ?? ""}
                              onChange={montant(field)}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="enterprise_value"
                      render={({ field }) => (
                        <FormItem className="sm:col-span-2">
                          <FormLabel>Valeur d’entreprise (EVIC)</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={0}
                              step="0.01"
                              name={field.name}
                              ref={field.ref}
                              onBlur={field.onBlur}
                              value={field.value ?? ""}
                              onChange={montant(field)}
                            />
                          </FormControl>
                          <p className="text-xs text-brand-grey">
                            Trésorerie incluse, à la clôture de l’exercice. Facultatif, comme le
                            chiffre d’affaires : ils servent au calcul PCAF une fois le rapport
                            validé.
                          </p>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Facultatif : le chiffre d’affaires et la valeur d’entreprise servent au calcul
                    PCAF une fois le rapport validé. Choisissez une devise pour les renseigner.
                  </p>
                )}
                <div className="flex justify-between gap-2 border-t pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate("/company/declarations/nouvelle/exercice")}
                  >
                    Précédent
                  </Button>
                  <Button type="submit" disabled={ouvrir.isPending}>
                    {ouvrir.isPending ? "Création…" : "Créer le brouillon"}
                  </Button>
                </div>
              </>
            )}
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
