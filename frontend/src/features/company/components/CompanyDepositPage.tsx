import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { useSubmitReport } from "../api";
import { type DeposerRapportForm, deposerRapportSchema, TYPES_RAPPORT, type TypeRapport } from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();

/** Dépôt d'un nouveau rapport — action isolée sur sa propre page (voir CompanyReportsPage pour
 * le suivi des dépôts déjà faits) : une réussite renvoie directement vers la liste, où le nouveau
 * rapport apparaît aussitôt (useSubmitReport invalide déjà la requête, voir ../api.ts). */
export function CompanyDepositPage() {
  const navigate = useNavigate();
  const submitReport = useSubmitReport();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<DeposerRapportForm>({
    resolver: zodResolver(deposerRapportSchema),
    defaultValues: { type: TYPES_RAPPORT[0], annee_reporting: ANNEE_COURANTE },
  });

  function onSubmit(values: DeposerRapportForm) {
    setServerError(null);
    // Le <select> n'offre que les valeurs de TYPES_RAPPORT (dérivées de TypeRapport lui-même) —
    // cast sûr, zod ne valide ce champ qu'en chaîne non vide pour rester simple côté schéma.
    submitReport.mutate(
      { ...values, type: values.type as TypeRapport },
      {
        onSuccess: () => navigate("/company/rapports"),
        onError: (error) => {
          setServerError(
            error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
          );
        },
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Déposer un rapport"
        description="Transmettez votre rapport ESG/climat pour extraction et audit."
      />

      <Card>
        <CardHeader>
          <CardTitle>Nouveau dépôt</CardTitle>
          <CardDescription>PDF uniquement, 50 Mo maximum.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              {serverError ? (
                <Alert variant="destructive">
                  <AlertTitle>Dépôt impossible</AlertTitle>
                  <AlertDescription>{serverError}</AlertDescription>
                </Alert>
              ) : null}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <FormField
                  control={form.control}
                  name="type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Type de rapport</FormLabel>
                      <FormControl>
                        <Select {...field}>
                          {TYPES_RAPPORT.map((type) => (
                            <option key={type} value={type}>
                              {type}
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
                  name="annee_reporting"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Année</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          {...field}
                          onChange={(event) => field.onChange(event.target.valueAsNumber)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="fichier"
                  render={({ field: { onChange, onBlur, name, ref } }) => (
                    <FormItem>
                      <FormLabel>Fichier PDF</FormLabel>
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
              </div>

              <Button type="submit" disabled={submitReport.isPending}>
                {submitReport.isPending ? "Dépôt en cours..." : "Déposer"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
