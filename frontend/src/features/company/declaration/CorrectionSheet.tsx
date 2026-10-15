import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { idDepuisSlug } from "@/shared/format/slug";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { FileDrop } from "@/shared/ui/file-drop";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { RouteSheet } from "@/shared/ui/route-sheet";
import { SheetBody, SheetFooter } from "@/shared/ui/sheet";
import { rapportQueryOptions, useSubmitCorrection } from "../api";
import { type CorrectionForm, correctionSchema } from "../schemas";
import { presentationSession } from "../session/presentation";

const ANNEE_COURANTE = new Date().getFullYear();

/** Correction demandée (spec §3.2) : 1) ce qui est demandé, 2) exercice + PDF corrigé. Une
 * nouvelle version liée ; l'original reste conservé tel quel. */
export function CorrectionSheet() {
  const { rapportId: segment = "" } = useParams();
  const navigate = useNavigate();
  const retour = `/company/declarations/${segment}`;
  const { data: rapport } = useQuery(rapportQueryOptions(idDepuisSlug(segment)));
  const [etape, setEtape] = useState<1 | 2>(1);
  const correction = useSubmitCorrection(rapport?.id ?? "");
  const [erreur, setErreur] = useState<string | null>(null);
  const form = useForm<CorrectionForm>({
    resolver: zodResolver(correctionSchema),
    defaultValues: { annee_reporting: rapport?.fiscal_year ?? ANNEE_COURANTE },
  });

  if (!rapport) return null;
  if (rapport.status !== "REVISION_REQUESTED") return <Navigate to={retour} replace />;

  function envoyer(valeurs: CorrectionForm) {
    setErreur(null);
    correction.mutate(valeurs, {
      onSuccess: () => navigate(retour, { state: { correctionEnvoyee: true } }),
      onError: (error) =>
        setErreur(
          error instanceof ApiError ? error.message : "Une erreur inattendue est survenue.",
        ),
    });
  }

  return (
    <RouteSheet
      retour={retour}
      titre="Correction demandée"
      description={`Étape ${etape} sur 2`}
      taille="large"
    >
      {etape === 1 ? (
        <>
          <SheetBody>
            <p className="text-sm text-foreground">
              {presentationSession("REVISION_REQUESTED").description}
            </p>
            <p className="text-sm text-muted-foreground">
              Déposez une nouvelle version du rapport. L’original reste conservé tel quel.
            </p>
          </SheetBody>
          <SheetFooter>
            <Button onClick={() => setEtape(2)}>Continuer</Button>
          </SheetFooter>
        </>
      ) : (
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(envoyer)}
            className="flex min-h-0 flex-1 flex-col"
            noValidate
          >
            <SheetBody>
              {erreur ? (
                <Alert variant="destructive">
                  <AlertTitle>Dépôt impossible</AlertTitle>
                  <AlertDescription>{erreur}</AlertDescription>
                </Alert>
              ) : null}
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
            </SheetBody>
            <SheetFooter>
              <Button type="button" variant="outline" onClick={() => setEtape(1)}>
                Précédent
              </Button>
              <Button type="submit" disabled={correction.isPending}>
                {correction.isPending ? "Envoi en cours…" : "Envoyer la correction"}
              </Button>
            </SheetFooter>
          </form>
        </Form>
      )}
    </RouteSheet>
  );
}
