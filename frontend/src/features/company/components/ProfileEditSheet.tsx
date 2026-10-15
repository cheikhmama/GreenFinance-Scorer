import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { EntreprisePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { RouteSheet } from "@/shared/ui/route-sheet";
import { Select } from "@/shared/ui/select";
import { SheetBody, SheetFooter } from "@/shared/ui/sheet";
import { Textarea } from "@/shared/ui/textarea";
import { useMyCompanyProfile, useUpdateMyCompanyProfile } from "../api";
import {
  DEVISES,
  type ModifierProfilEntrepriseForm,
  modifierProfilEntrepriseSchema,
} from "../schemas";

const RETOUR = "/company/profile";

/** Tiroir routé de modification de la fiche publique : description, site officiel et montant
 * minimum d'investissement (nom, secteur, pays et logo restent gérés par l'Administrateur). */
export function ProfileEditSheet() {
  const { data: entreprise } = useMyCompanyProfile();
  const navigate = useNavigate();
  if (!entreprise) return null;
  return (
    <RouteSheet retour={RETOUR} titre="Modifier la fiche publique" taille="large">
      <FormulaireFiche entreprise={entreprise} onEnregistre={() => navigate(RETOUR)} />
    </RouteSheet>
  );
}

function FormulaireFiche({
  entreprise,
  onEnregistre,
}: {
  entreprise: EntreprisePublic;
  onEnregistre: () => void;
}) {
  const updateProfile = useUpdateMyCompanyProfile();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<ModifierProfilEntrepriseForm>({
    resolver: zodResolver(modifierProfilEntrepriseSchema),
    // `values` n'arrive qu'après le premier rendu : sans valeurs de départ, chaque champ passait
    // de non contrôlé à contrôlé (avertissement React).
    defaultValues: {
      description: "",
      website: "",
      impose_minimum: false,
      minimum_investment_currency: DEVISES[0],
    },
    values: {
      description: entreprise.description ?? "",
      website: entreprise.website ?? "",
      impose_minimum: entreprise.minimum_investment_amount != null,
      minimum_investment_amount: entreprise.minimum_investment_amount ?? undefined,
      minimum_investment_currency: entreprise.minimum_investment_currency ?? DEVISES[0],
    },
  });
  const imposeMinimum = form.watch("impose_minimum");

  function onSubmit(values: ModifierProfilEntrepriseForm) {
    setServerError(null);
    updateProfile.mutate(
      {
        description: values.description || null,
        website: values.website || null,
        minimum_investment_amount: values.impose_minimum
          ? (values.minimum_investment_amount ?? null)
          : null,
        minimum_investment_currency: values.impose_minimum
          ? (values.minimum_investment_currency ?? null)
          : null,
      },
      {
        onSuccess: onEnregistre,
        onError: (error) => {
          setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
        },
      },
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="flex min-h-0 flex-1 flex-col"
        noValidate
      >
        <SheetBody className="space-y-4">
          {serverError ? (
            <Alert variant="destructive">
              <AlertTitle>Échec</AlertTitle>
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          ) : null}

          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Description</FormLabel>
                <FormControl>
                  <Textarea
                    rows={3}
                    placeholder="Présentez votre entreprise en quelques phrases."
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
              <FormItem>
                <FormLabel>Site officiel</FormLabel>
                <FormControl>
                  <Input type="url" placeholder="https://..." {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="space-y-3 border-t pt-4">
            <FormField
              control={form.control}
              name="impose_minimum"
              render={({ field }) => (
                <FormItem>
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={field.value}
                      onChange={(event) => field.onChange(event.target.checked)}
                    />
                    Imposer un montant minimum d'investissement
                  </label>
                </FormItem>
              )}
            />
            {imposeMinimum ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="minimum_investment_amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Montant minimum</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.01"
                          min={0}
                          name={field.name}
                          value={field.value ?? ""}
                          onChange={(event) => field.onChange(event.target.valueAsNumber)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="minimum_investment_currency"
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
              </div>
            ) : null}
          </div>
        </SheetBody>
        <SheetFooter>
          <Button asChild variant="outline">
            <Link to={RETOUR}>Annuler</Link>
          </Button>
          <Button type="submit" disabled={updateProfile.isPending}>
            {updateProfile.isPending ? "Enregistrement..." : "Enregistrer"}
          </Button>
        </SheetFooter>
      </form>
    </Form>
  );
}
