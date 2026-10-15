import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { FileDrop } from "@/shared/ui/file-drop";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();

/** Correction demandée par l'auditeur : une nouvelle version, liée à celle-ci, pour le même
 * exercice par défaut (l'année courante n'est qu'un repli si l'exercice est inconnu). */
export function FormulaireCorrection({
  rapportId,
  exercice,
}: {
  rapportId: string;
  exercice: number | null;
}) {
  const submitCorrection = useSubmitCorrection(rapportId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CorrectionForm>({
    resolver: zodResolver(correctionSchema),
    defaultValues: { annee_reporting: exercice ?? ANNEE_COURANTE },
  });

  function onSubmit(values: CorrectionForm) {
    setServerError(null);
    submitCorrection.mutate(values, {
      onError: (error) => {
        setServerError(
          error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
        );
      },
    });
  }

  if (submitCorrection.isSuccess) {
    return (
      <Alert role="status" className="border-primary/20 bg-secondary/60">
        <AlertTitle>Nouvelle version déposée</AlertTitle>
        <AlertDescription>
          Votre correction a été envoyée et sera traitée comme un nouveau rapport.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="border-amber-300 dark:border-amber-900">
      <CardHeader>
        <CardTitle className="text-base">Correction demandée</CardTitle>
        <CardDescription>
          Déposez une nouvelle version de ce rapport. L’original reste conservé tel quel.
        </CardDescription>
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
            <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-[10rem_1fr]">
              <FormField
                control={form.control}
                name="annee_reporting"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exercice</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        className="h-11"
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
                render={({ field: { value, onChange, onBlur, name, ref } }) => (
                  <FormItem>
                    <FormLabel>Fichier PDF corrigé</FormLabel>
                    <FormControl>
                      <FileDrop
                        accept="application/pdf"
                        hint="PDF, 50 Mo au maximum"
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
            </div>
            <Button type="submit" disabled={submitCorrection.isPending}>
              {submitCorrection.isPending ? "Envoi en cours…" : "Envoyer la correction"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
