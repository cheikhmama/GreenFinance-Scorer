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
import { useOpenDeclaration } from "../api";
import { type OuvrirDeclarationForm, ouvrirDeclarationSchema, TYPES_RAPPORT } from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();

/** Ouverture d'une déclaration (tâche 5.8) : un brouillon pour un type de rapport et un exercice.
 * Le PDF se joint ensuite sur la page du brouillon, où son analyse donne la liste de complétude
 * avant la soumission. */
export function CompanyDepositPage() {
  const navigate = useNavigate();
  const ouvrir = useOpenDeclaration();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<OuvrirDeclarationForm>({
    resolver: zodResolver(ouvrirDeclarationSchema),
    defaultValues: { report_type: TYPES_RAPPORT[0], fiscal_year: ANNEE_COURANTE - 1 },
  });

  function onSubmit(values: OuvrirDeclarationForm) {
    setServerError(null);
    ouvrir.mutate(values, {
      onSuccess: (brouillon) => navigate(`/company/rapports/${brouillon.id}`),
      onError: (error) => {
        setServerError(
          error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
        );
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Entreprise"
        title="Nouvelle déclaration"
        description="Ouvrez la déclaration d’un exercice, joignez votre rapport, vérifiez la liste de complétude, puis soumettez-le."
      />

      <Card>
        <CardHeader>
          <CardTitle>Exercice déclaré</CardTitle>
          <CardDescription>
            Le brouillon reste modifiable jusqu’à sa soumission ; rien n’est transmis avant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              {serverError ? (
                <Alert variant="destructive">
                  <AlertTitle>Ouverture impossible</AlertTitle>
                  <AlertDescription>{serverError}</AlertDescription>
                </Alert>
              ) : null}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                  name="fiscal_year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Exercice</FormLabel>
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
              </div>

              <Button type="submit" disabled={ouvrir.isPending}>
                {ouvrir.isPending ? "Ouverture…" : "Ouvrir la déclaration"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
