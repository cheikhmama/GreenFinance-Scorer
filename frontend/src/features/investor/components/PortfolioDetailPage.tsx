import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type {
  EntreprisePublieePublic,
  PositionDetail,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { CompanyIdentity } from "@/shared/esg/CompanyAvatar";
import {
  formatMontant,
  formatPourcentage,
  formatScore,
  libelleEtatPosition,
  variantEtatPosition,
} from "@/shared/format/etatPosition";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { BackLink } from "@/shared/ui/back-link";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import {
  exportPortfolioFile,
  useAddPosition,
  useArchivePortfolio,
  useClosePosition,
  useCompanyDetail,
  useDeletePortfolio,
  useDeletePosition,
  usePortfolioDetail,
  useRenamePortfolio,
  useRestorePortfolio,
  useUpdatePosition,
} from "../api";
import {
  type AjouterPositionForm,
  ajouterPositionSchema,
  DEVISES,
  DurationType,
  type RenommerPortefeuilleForm,
  renommerPortefeuilleSchema,
  TYPES_DUREE,
} from "../schemas";
import { EntrepriseCombobox } from "./EntrepriseCombobox";
import { ImportPositionsForm } from "./ImportPositionsForm";
import { PortfolioCarbonCard } from "./PortfolioCarbonCard";

export function PortfolioDetailPage() {
  const { portefeuilleId = "" } = useParams();
  const navigate = useNavigate();
  const { data: portefeuille, isLoading, isError } = usePortfolioDetail(portefeuilleId);
  const archiver = useArchivePortfolio(portefeuilleId);
  const restaurer = useRestorePortfolio(portefeuilleId);
  const supprimer = useDeletePortfolio();
  const confirm = useConfirm();
  const [ajoutOuvert, setAjoutOuvert] = useState(false);
  const [renommerOuvert, setRenommerOuvert] = useState(false);
  const [positionAModifier, setPositionAModifier] = useState<PositionDetail | null>(null);
  const [positionAFermer, setPositionAFermer] = useState<PositionDetail | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !portefeuille)
    return <p className="text-destructive">Portefeuille introuvable.</p>;

  async function supprimerPortefeuille() {
    if (!portefeuille || portefeuille.position_count > 0) return;
    const confirme = await confirm({
      title: "Supprimer ce portefeuille ?",
      description: `« ${portefeuille.name} » sera définitivement supprimé. Cette action est irréversible.`,
      confirmLabel: "Supprimer",
      destructive: true,
    });
    if (!confirme) return;
    supprimer.mutate(portefeuille.id, { onSuccess: () => navigate("/investor/portefeuilles") });
  }

  return (
    <div className="space-y-6">
      <BackLink to="/investor/portefeuilles">Portefeuilles</BackLink>
      <PageHeader
        title={portefeuille.name}
        description={`Créé le ${new Date(portefeuille.created_at).toLocaleDateString("fr-FR")}.`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setRenommerOuvert(true)}>
              Renommer
            </Button>
            {portefeuille.archived ? (
              <Button variant="outline" size="sm" onClick={() => restaurer.mutate()}>
                Restaurer
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => archiver.mutate()}>
                Archiver
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportPortfolioFile(portefeuille.id, portefeuille.name)}
            >
              Exporter (CSV)
            </Button>
            {portefeuille.position_count === 0 ? (
              <Button variant="destructive" size="sm" onClick={supprimerPortefeuille}>
                Supprimer
              </Button>
            ) : null}
          </div>
        }
      />

      {portefeuille.archived ? (
        <Alert>
          <AlertTitle>Portefeuille archivé</AlertTitle>
          <AlertDescription>Restaure-le pour ajouter de nouvelles positions.</AlertDescription>
        </Alert>
      ) : null}

      {portefeuille.position_count > 0 ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Synthese
              label="Montant total"
              value={formatMontant(portefeuille.total_amount, portefeuille.reference_currency)}
            />
            <Synthese
              label="Score ESG agrégé"
              value={formatScore(portefeuille.aggregated_esg_score)}
            />
            <Synthese label="Couverture ESG" value={formatPourcentage(portefeuille.esg_coverage)} />
            <Synthese
              label="Positions"
              value={`${portefeuille.active_position_count} actives · ${portefeuille.planned_position_count} planifiées · ${portefeuille.closed_position_count} clôturées`}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Synthese
              label="Environnement (E)"
              value={formatScore(portefeuille.aggregated_environmental_score)}
            />
            <Synthese
              label="Social (S)"
              value={formatScore(portefeuille.aggregated_social_score)}
            />
            <Synthese
              label="Gouvernance (G)"
              value={formatScore(portefeuille.aggregated_governance_score)}
            />
          </div>

          <PortfolioCarbonCard portefeuilleId={portefeuille.id} />
        </>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Positions</CardTitle>
          {!portefeuille.archived && portefeuille.position_count > 0 ? (
            <Button size="sm" onClick={() => setAjoutOuvert(true)}>
              Créer une position
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {portefeuille.positions.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="text-brand-grey">Ce portefeuille ne contient encore aucune position.</p>
              {!portefeuille.archived ? (
                <>
                  <Button onClick={() => setAjoutOuvert(true)}>Créer une position</Button>
                  <ImportPositionsForm portefeuilleId={portefeuille.id} />
                </>
              ) : null}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <p className="pb-2 text-xs text-brand-grey">
                « Modifier » et « Supprimer » ne sont proposés que pour une position encore
                planifiée (non commencée) — une position déjà active fait partie de l'historique
                réel du portefeuille et ne peut plus être effacée.
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Entreprise</th>
                    <th className="py-2 pr-4 font-medium">Montant</th>
                    <th className="py-2 pr-4 font-medium">Poids</th>
                    <th className="py-2 pr-4 font-medium">Durée</th>
                    <th className="py-2 pr-4 font-medium">État</th>
                    <th className="py-2 pr-4 font-medium">Date de fermeture</th>
                    <th className="py-2 pr-4 font-medium">Score ESG</th>
                    <th className="py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {portefeuille.positions.map((position) => (
                    <tr key={position.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        {position.company ? (
                          <CompanyIdentity
                            nom={position.company.name}
                            logo={position.company.logo}
                            secteur={position.company.sector}
                          />
                        ) : (
                          // Ligne importée qu'aucune entreprise publiée ne reconnaît (tâche 2.2).
                          <div className="space-y-1">
                            <p className="font-mono text-sm">{position.identifier}</p>
                            <Badge variant="outline">
                              {position.match_status === "AMBIGUOUS"
                                ? "Plusieurs entreprises possibles"
                                : "Entreprise non reconnue"}
                            </Badge>
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-4">
                        <p>{formatMontant(position.outstanding_amount, position.currency)}</p>
                        {position.fx_rate_used ? (
                          <p className="text-xs text-brand-grey">
                            ={" "}
                            {formatMontant(
                              position.converted_amount,
                              portefeuille.reference_currency,
                            )}
                          </p>
                        ) : null}
                      </td>
                      <td className="py-2 pr-4 tabular-nums">
                        {formatPourcentage(position.weight * 100)}
                      </td>
                      <td className="py-2 pr-4">
                        {position.duration_type === DurationType.FIXE ? "Fixe" : "Ouverte"}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={variantEtatPosition(position.state)}>
                          {libelleEtatPosition(position.state)}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">
                        {position.end_date
                          ? new Date(position.end_date).toLocaleDateString("fr-FR")
                          : "—"}
                      </td>
                      <td className="py-2 pr-4">{formatScore(position.score.global_score)}</td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-2">
                          {position.company ? (
                            <Button size="sm" variant="outline" asChild>
                              <Link to={`/investor/entreprises/${position.company.id}`}>
                                Détails
                              </Link>
                            </Button>
                          ) : null}
                          {position.state === "PLANIFIEE" && position.company ? (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setPositionAModifier(position)}
                              >
                                Modifier
                              </Button>
                              <SupprimerPositionButton
                                portefeuilleId={portefeuille.id}
                                positionId={position.id}
                                onError={setActionError}
                              />
                            </>
                          ) : null}
                          {position.duration_type === DurationType.OUVERTE &&
                          position.end_date === null ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setPositionAFermer(position)}
                            >
                              Fermer
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={renommerOuvert} onOpenChange={setRenommerOuvert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Renommer le portefeuille</DialogTitle>
          </DialogHeader>
          <FormulaireRenommer
            portefeuilleId={portefeuille.id}
            nomActuel={portefeuille.name}
            onDone={() => setRenommerOuvert(false)}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={ajoutOuvert} onOpenChange={setAjoutOuvert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ajouter une position</DialogTitle>
          </DialogHeader>
          <FormulairePosition
            portefeuilleId={portefeuille.id}
            onDone={() => setAjoutOuvert(false)}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={positionAModifier !== null} onOpenChange={() => setPositionAModifier(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier la position</DialogTitle>
          </DialogHeader>
          {positionAModifier ? (
            <FormulairePosition
              portefeuilleId={portefeuille.id}
              position={positionAModifier}
              onDone={() => setPositionAModifier(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={positionAFermer !== null} onOpenChange={() => setPositionAFermer(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fermer la position</DialogTitle>
          </DialogHeader>
          {positionAFermer ? (
            <FormulaireFermeture
              portefeuilleId={portefeuille.id}
              position={positionAFermer}
              onDone={() => setPositionAFermer(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Synthese({ label, value }: { label: string; value: string }) {
  return (
    <Card className="gap-2 py-4 shadow-none">
      <CardContent className="px-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 text-lg font-semibold text-brand-blue">{value}</p>
      </CardContent>
    </Card>
  );
}

function SupprimerPositionButton({
  portefeuilleId,
  positionId,
  onError,
}: {
  portefeuilleId: string;
  positionId: string;
  onError: (message: string) => void;
}) {
  const deletePosition = useDeletePosition(portefeuilleId);
  const confirm = useConfirm();
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={deletePosition.isPending}
      onClick={async () => {
        const confirme = await confirm({
          title: "Supprimer cette position ?",
          description:
            "Cette position planifiée sera définitivement supprimée. Cette action est irréversible.",
          confirmLabel: "Supprimer",
          destructive: true,
        });
        if (!confirme) return;
        deletePosition.mutate(positionId, {
          onError: (error) =>
            onError(error instanceof ApiError ? error.message : "Échec de la suppression."),
        });
      }}
    >
      Supprimer
    </Button>
  );
}

function FormulaireRenommer({
  portefeuilleId,
  nomActuel,
  onDone,
}: {
  portefeuilleId: string;
  nomActuel: string;
  onDone: () => void;
}) {
  const renommer = useRenamePortfolio(portefeuilleId);
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<RenommerPortefeuilleForm>({
    resolver: zodResolver(renommerPortefeuilleSchema),
    defaultValues: { name: nomActuel },
  });

  function onSubmit(values: RenommerPortefeuilleForm) {
    setServerError(null);
    renommer.mutate(values, {
      onSuccess: onDone,
      onError: (error) =>
        setServerError(error instanceof ApiError ? error.message : "Échec du renommage."),
    });
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Renommage impossible</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nom du portefeuille</FormLabel>
              <FormControl>
                <Input autoFocus {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onDone}>
            Annuler
          </Button>
          <Button type="submit" disabled={renommer.isPending}>
            {renommer.isPending ? "Enregistrement..." : "Confirmer"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

function FormulaireFermeture({
  portefeuilleId,
  position,
  onDone,
}: {
  portefeuilleId: string;
  position: PositionDetail;
  onDone: () => void;
}) {
  const closePosition = useClosePosition(portefeuilleId);
  const [dateFin, setDateFin] = useState(new Date().toISOString().slice(0, 10));
  const [serverError, setServerError] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <p className="text-sm text-brand-grey">
        Position sur <strong>{position.company?.name ?? position.identifier}</strong>, ouverte le{" "}
        {new Date(position.start_date).toLocaleDateString("fr-FR")}.
      </p>
      {serverError ? (
        <Alert variant="destructive">
          <AlertTitle>Fermeture impossible</AlertTitle>
          <AlertDescription>{serverError}</AlertDescription>
        </Alert>
      ) : null}
      <div className="block space-y-1 text-sm">
        <label htmlFor="date-fermeture" className="font-medium">
          Date de fermeture
        </label>
        <Input
          id="date-fermeture"
          type="date"
          value={dateFin}
          onChange={(event) => setDateFin(event.target.value)}
        />
      </div>
      <Button
        className="w-full"
        disabled={closePosition.isPending}
        onClick={() =>
          closePosition.mutate(
            { positionId: position.id, payload: { end_date: new Date(dateFin).toISOString() } },
            {
              onSuccess: onDone,
              onError: (error) =>
                setServerError(
                  error instanceof ApiError ? error.message : "Échec de la fermeture.",
                ),
            },
          )
        }
      >
        {closePosition.isPending ? "Fermeture..." : "Confirmer la fermeture"}
      </Button>
    </div>
  );
}

function FormulairePosition({
  portefeuilleId,
  position,
  onDone,
}: {
  portefeuilleId: string;
  position?: PositionDetail;
  onDone: () => void;
}) {
  const addPosition = useAddPosition(portefeuilleId);
  const updatePosition = useUpdatePosition(portefeuilleId);
  const [entrepriseSelectionnee, setEntrepriseSelectionnee] =
    useState<EntreprisePublieePublic | null>(null);
  // En modification, l'entreprise est figée sur la position existante (jamais changeable, voir
  // le formulaire plus bas) — on récupère son montant minimum pré-converti via la même route que
  // la fiche détaillée, plutôt que de le dupliquer dans PositionDetail.entreprise.
  const { data: entrepriseDetail } = useCompanyDetail(position?.company?.id ?? "");
  const entrepriseActive = position ? entrepriseDetail : entrepriseSelectionnee;
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<AjouterPositionForm>({
    // Même schéma en modification : entreprise_id reste rempli (figé sur position.entreprise.id,
    // jamais affiché ni modifiable, voir plus bas) — seul le champ change, jamais sa présence.
    resolver: zodResolver(ajouterPositionSchema),
    defaultValues: position
      ? {
          // Formulaire jamais ouvert pour une ligne non rapprochée (bouton masqué plus haut).
          company_id: position.company?.id ?? "",
          amount: position.outstanding_amount,
          currency: position.currency,
          duration_type: position.duration_type,
          start_date: position.start_date.slice(0, 10),
          end_date: position.end_date?.slice(0, 10) ?? "",
        }
      : {
          company_id: "",
          amount: 0,
          currency: DEVISES[0],
          duration_type: TYPES_DUREE[0],
          start_date: new Date().toISOString().slice(0, 10),
          end_date: "",
        },
  });
  const typeDuree = form.watch("duration_type");
  const deviseChoisie = form.watch("currency");
  const montantSaisi = form.watch("amount");
  const minimumPourDevise = entrepriseActive?.minimum_amount_by_currency?.[deviseChoisie] ?? null;
  const montantInsuffisant = minimumPourDevise !== null && montantSaisi < minimumPourDevise;

  function onSubmit(values: AjouterPositionForm) {
    setServerError(null);
    const payload = {
      amount: values.amount,
      currency: values.currency,
      duration_type: values.duration_type,
      start_date: new Date(values.start_date).toISOString(),
      end_date: values.end_date ? new Date(values.end_date).toISOString() : undefined,
    };
    const onError = (error: unknown) =>
      setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");

    if (position) {
      updatePosition.mutate(
        { positionId: position.id, payload: { ...payload, end_date: payload.end_date ?? null } },
        { onSuccess: onDone, onError },
      );
    } else {
      addPosition.mutate(
        { ...payload, company_id: values.company_id },
        { onSuccess: onDone, onError },
      );
    }
  }

  const enCours = addPosition.isPending || updatePosition.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <Alert variant="destructive">
            <AlertTitle>Échec</AlertTitle>
            <AlertDescription>{serverError}</AlertDescription>
          </Alert>
        ) : null}

        {!position ? (
          <FormField
            control={form.control}
            name="company_id"
            render={() => (
              <FormItem>
                <FormLabel>Entreprise publiée</FormLabel>
                <FormControl>
                  <EntrepriseCombobox
                    onSelect={(entreprise) => {
                      form.setValue("company_id", entreprise.id, { shouldValidate: true });
                      setEntrepriseSelectionnee(entreprise);
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}

        {entrepriseActive ? (
          <div className="space-y-2 rounded-md bg-muted/50 px-3 py-2">
            <CompanyIdentity
              nom={entrepriseActive.name}
              logo={entrepriseActive.logo}
              avatarClassName="size-8"
            />
            <p className="text-sm text-brand-grey">
              Montant minimum requis :{" "}
              <strong className={montantInsuffisant ? "text-destructive" : "text-brand-blue"}>
                {minimumPourDevise === null
                  ? "aucun minimum imposé"
                  : formatMontant(minimumPourDevise, deviseChoisie)}
              </strong>
            </p>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="amount"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Montant</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    step="0.01"
                    min={0}
                    aria-invalid={montantInsuffisant}
                    value={field.value}
                    onKeyDown={(event) => {
                      // Bloque la frappe du signe moins à la source — le clamp ci-dessous reste
                      // le filet de sécurité pour les autres façons d'entrer une valeur négative
                      // (collage, flèches, molette).
                      if (event.key === "-") event.preventDefault();
                    }}
                    onChange={(event) => {
                      // Math.max(0, NaN) vaut NaN (champ vidé, laissé tel quel pour le message
                      // "requis" de FormMessage) — jamais une valeur négative propagée au form.
                      field.onChange(Math.max(0, event.target.valueAsNumber));
                    }}
                  />
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
        </div>

        <FormField
          control={form.control}
          name="duration_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Type de durée</FormLabel>
              <FormControl>
                <Select {...field}>
                  <option value={DurationType.OUVERTE}>Ouverte</option>
                  <option value={DurationType.FIXE}>Fixe</option>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="start_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date de début</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          {typeDuree === DurationType.FIXE ? (
            <FormField
              control={form.control}
              name="end_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date de fin</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          ) : null}
        </div>

        <Button type="submit" className="w-full" disabled={enCours || montantInsuffisant}>
          {enCours ? "Enregistrement..." : position ? "Enregistrer les modifications" : "Ajouter"}
        </Button>
      </form>
    </Form>
  );
}
