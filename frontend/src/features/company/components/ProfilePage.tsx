import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { EntreprisePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { ApiError } from "@/shared/api/errors";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libellePays } from "@/shared/format/pays";
import { PageShell } from "@/shared/layout/PageShell";
import { ProfileIdentityCard } from "@/shared/profile/ProfileIdentityCard";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { Textarea } from "@/shared/ui/textarea";
import { useMyCompanyProfile, useUpdateMyCompanyProfile } from "../api";
import {
  DEVISES,
  type ModifierProfilEntrepriseForm,
  modifierProfilEntrepriseSchema,
} from "../schemas";
import { CompanyRegistrationsCard } from "./CompanyRegistrationsCard";

/** Nom, secteur, pays et logo restent gérés par l'Administrateur (gouvernance Phase 0) ; la
 * description, le site officiel et le montant minimum d'investissement sont modifiables ici par
 * l'Entreprise elle-même (tâche post-Phase-0, bascule depuis AdminCompanyDetailPage.tsx). Trois
 * sections en cartes : le compte et son contact, la fiche entreprise telle que les investisseurs
 * la voient une fois publiée, puis ses immatriculations (secteur, LEI, ISIN, contrôle GLEIF). */
export function ProfilePage() {
  const { data: entreprise, isPending, isError } = useMyCompanyProfile();

  return (
    <PageShell
      title="Profil entreprise"
      description="Votre compte et la fiche de votre entreprise."
    >
      <ProfileIdentityCard />

      {isPending ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-2" />
          <Skeleton className="h-64" />
        </div>
      ) : null}
      {isError ? (
        <p className="text-sm text-destructive">Impossible de charger la fiche entreprise.</p>
      ) : null}

      {entreprise ? (
        <div className="grid items-start gap-6 lg:grid-cols-3">
          <FicheEntreprise entreprise={entreprise} />
          <CompanyRegistrationsCard entreprise={entreprise} />
        </div>
      ) : null}
    </PageShell>
  );
}

function statutPublication(entreprise: EntreprisePublic) {
  if (!entreprise.published_at) return { variant: "secondary" as const, libelle: "Non publiée" };
  if (!entreprise.active) return { variant: "destructive" as const, libelle: "Suspendue" };
  return {
    variant: "success" as const,
    libelle: `Publiée le ${new Date(entreprise.published_at).toLocaleDateString("fr-FR")}`,
  };
}

/** Nom, secteur, pays et logo : lecture seule (Admin). Description, site officiel et montant
 * minimum : formulaire d'édition (Entreprise elle-même), même structure que l'ancien formulaire
 * Admin qu'il remplace (AdminCompanyDetailPage.tsx avant tâche post-Phase-0). */
function FicheEntreprise({ entreprise }: { entreprise: EntreprisePublic }) {
  const statut = statutPublication(entreprise);
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
        onError: (error) => {
          setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");
        },
      },
    );
  }

  return (
    <Card role="region" aria-label="Fiche entreprise" className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="text-base">Fiche entreprise</CardTitle>
        <CardAction>
          <Badge variant={statut.variant}>{statut.libelle}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-3">
          <CompanyAvatar nom={entreprise.name} logo={entreprise.logo} className="size-14" />
          <div className="min-w-0">
            <p className="font-semibold text-foreground">{entreprise.name}</p>
            <p className="text-sm text-muted-foreground">
              {entreprise.sector} — {libellePays(entreprise.country)}
            </p>
          </div>
        </div>

        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
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

            <Button type="submit" disabled={updateProfile.isPending}>
              {updateProfile.isPending ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
