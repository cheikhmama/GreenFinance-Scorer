import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { useOpenDeclaration } from "../api";
import {
  DEVISES,
  type OuvrirDeclarationForm,
  ouvrirDeclarationSchema,
  TYPES_RAPPORT,
} from "../schemas";

const ANNEE_COURANTE = new Date().getFullYear();
/** Les exercices proposés : les cinq derniers, le plus récent clos en premier. */
const EXERCICES = Array.from({ length: 6 }, (_, i) => ANNEE_COURANTE - i);

/** Création d'un exercice fiscal (tâche 5.9) : l'exercice, le type de rapport et les données
 * financières de l'exercice. Ouvre un brouillon et mène à sa page, où le PDF se joint. */
export function NewDeclarationDialog({
  open,
  onOpenChange,
  exercicesExclus = [],
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Exercices déjà validés : ils ne se déclarent plus (tâche 5.9). */
  exercicesExclus?: number[];
}) {
  const exercices = EXERCICES.filter((annee) => !exercicesExclus.includes(annee));
  const navigate = useNavigate();
  const ouvrir = useOpenDeclaration();
  const [erreur, setErreur] = useState<string | null>(null);
  const form = useForm<OuvrirDeclarationForm>({
    resolver: zodResolver(ouvrirDeclarationSchema),
    defaultValues: {
      report_type: "RAPPORT_ESG",
      fiscal_year:
        EXERCICES.find((annee) => !exercicesExclus.includes(annee)) ?? ANNEE_COURANTE - 1,
      currency: "EUR",
    },
  });

  function onSubmit(values: OuvrirDeclarationForm) {
    setErreur(null);
    ouvrir.mutate(values, {
      onSuccess: (brouillon) => {
        onOpenChange(false);
        navigate(`/company/declarations/${brouillon.id}`);
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle déclaration</DialogTitle>
          <DialogDescription>
            Ouvrez l’exercice à déclarer. Le brouillon reste modifiable jusqu’à sa soumission ; rien
            n’est transmis avant.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {erreur ? (
              <Alert variant="destructive">
                <AlertDescription>{erreur}</AlertDescription>
              </Alert>
            ) : null}
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
                name="currency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Devise</FormLabel>
                    <FormControl>
                      <Select {...field}>
                        {DEVISES.map((devise) => (
                          <option key={devise} value={devise}>
                            {devise}
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
                      Trésorerie incluse, à la clôture de l’exercice. Facultatif, comme le chiffre
                      d’affaires : ils servent au calcul PCAF une fois le rapport validé.
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={ouvrir.isPending}>
                {ouvrir.isPending ? "Ouverture…" : "Ouvrir la déclaration"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
