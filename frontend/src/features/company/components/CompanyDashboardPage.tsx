import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { useCompanyReports, useSubmitReport } from "../api";
import {
  type DeposerRapportForm,
  deposerRapportSchema,
  TYPES_RAPPORT,
  type TypeRapport,
} from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();

/**
 * Espace Entreprise réel (Phase 4 §4.3) — dépôt d'un rapport et liste des rapports déjà déposés,
 * chacun avec un lien vers son détail (features/company/components/CompanyReportDetailPage.tsx).
 */
export function CompanyDashboardPage() {
  const { data: rapports, isLoading, isError } = useCompanyReports();
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
        onSuccess: () => {
          form.reset({
            type: TYPES_RAPPORT[0],
            annee_reporting: ANNEE_COURANTE,
            fichier: undefined,
          });
        },
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
        title="Mes rapports"
        description="Déposer un rapport et suivre son cycle d'extraction, d'audit et de décision."
      />

      <Card>
        <CardHeader>
          <CardTitle>Déposer un rapport</CardTitle>
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

      <Card>
        <CardHeader>
          <CardTitle>Mes rapports</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-brand-grey">Chargement...</p> : null}
          {isError ? <p className="text-destructive">Impossible de charger vos rapports.</p> : null}
          {!isLoading && !isError && rapports?.length === 0 ? (
            <p className="text-brand-grey">Aucun rapport déposé pour l'instant.</p>
          ) : null}
          {rapports && rapports.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Statut</th>
                    <th className="py-2 pr-4 font-medium">Type</th>
                    <th className="py-2 pr-4 font-medium">Année</th>
                    <th className="py-2 pr-4 font-medium">Déposé le</th>
                    <th className="py-2 pr-4 font-medium">Version</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {rapports.map((rapport) => (
                    <tr key={rapport.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        <div className="flex flex-col gap-1">
                          <Badge variant={variantStatutRapport(rapport.statut)}>
                            {libelleStatutRapport(rapport.statut)}
                          </Badge>
                          {rapport.extraction_erreur ? (
                            <span className="text-xs text-destructive">
                              Échec d'extraction récupérable — nouvelle version possible.
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="py-2 pr-4">{rapport.type}</td>
                      <td className="py-2 pr-4">{rapport.annee_reporting ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {new Date(rapport.date_depot).toLocaleDateString("fr-FR")}
                      </td>
                      <td className="py-2 pr-4">v{rapport.version}</td>
                      <td className="py-2">
                        <Link
                          to={`/company/rapports/${rapport.id}`}
                          className="text-brand-green underline underline-offset-2"
                        >
                          Voir le détail
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
