import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import {
  formatMontant,
  formatPourcentage,
  formatScore,
  libelleEtatPosition,
  variantEtatPosition,
} from "@/shared/format/etatPosition";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
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
  useDeletePortfolio,
  useDeletePosition,
  usePortfolioDetail,
  usePublishedCompanies,
  useRenamePortfolio,
  useRestorePortfolio,
  useUpdatePosition,
} from "../api";
import {
  type AjouterPositionForm,
  ajouterPositionSchema,
  DEVISES,
  TYPES_DUREE,
  TypeDureeInvestissement,
} from "../schemas";
import type { PositionDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";

export function PortfolioDetailPage() {
  const { portefeuilleId = "" } = useParams();
  const navigate = useNavigate();
  const { data: portefeuille, isLoading, isError } = usePortfolioDetail(portefeuilleId);
  const renommer = useRenamePortfolio(portefeuilleId);
  const archiver = useArchivePortfolio(portefeuilleId);
  const restaurer = useRestorePortfolio(portefeuilleId);
  const supprimer = useDeletePortfolio();
  const [ajoutOuvert, setAjoutOuvert] = useState(false);
  const [positionAModifier, setPositionAModifier] = useState<PositionDetail | null>(null);
  const [positionAFermer, setPositionAFermer] = useState<PositionDetail | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !portefeuille) return <p className="text-destructive">Portefeuille introuvable.</p>;

  function renommerPortefeuille() {
    if (!portefeuille) return;
    const nom = window.prompt("Nouveau nom du portefeuille", portefeuille.nom);
    if (!nom) return;
    renommer.mutate({ nom });
  }

  function supprimerPortefeuille() {
    if (!portefeuille || portefeuille.nombre_positions > 0) return;
    if (!window.confirm("Supprimer définitivement ce portefeuille ?")) return;
    supprimer.mutate(portefeuille.id, { onSuccess: () => navigate("/investor/portefeuilles") });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investisseur"
        title={portefeuille.nom}
        description={`Créé le ${new Date(portefeuille.date_creation).toLocaleDateString("fr-FR")}.`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={renommerPortefeuille}>
              Renommer
            </Button>
            {portefeuille.archive ? (
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
              onClick={() => exportPortfolioFile(portefeuille.id, portefeuille.nom)}
            >
              Exporter (CSV)
            </Button>
            {portefeuille.nombre_positions === 0 ? (
              <Button variant="destructive" size="sm" onClick={supprimerPortefeuille}>
                Supprimer
              </Button>
            ) : null}
          </div>
        }
      />

      {portefeuille.archive ? (
        <Alert>
          <AlertTitle>Portefeuille archivé</AlertTitle>
          <AlertDescription>Restaure-le pour ajouter de nouvelles positions.</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Synthese
          label="Montant total"
          value={formatMontant(portefeuille.montant_total, portefeuille.devise_reference)}
        />
        <Synthese label="Score ESG agrégé" value={formatScore(portefeuille.score_esg_agrege)} />
        <Synthese label="Couverture ESG" value={formatPourcentage(portefeuille.couverture_esg)} />
        <Synthese
          label="Positions"
          value={`${portefeuille.nombre_positions_actives} actives · ${portefeuille.nombre_positions_planifiees} planifiées · ${portefeuille.nombre_positions_cloturees} clôturées`}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Synthese label="Environnement (E)" value={formatScore(portefeuille.score_environnement_agrege)} />
        <Synthese label="Social (S)" value={formatScore(portefeuille.score_social_agrege)} />
        <Synthese label="Gouvernance (G)" value={formatScore(portefeuille.score_gouvernance_agrege)} />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Positions</CardTitle>
          {!portefeuille.archive ? (
            <Button size="sm" onClick={() => setAjoutOuvert(true)}>
              Ajouter une position
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {portefeuille.positions.length === 0 ? (
            <p className="text-brand-grey">Aucune position pour l'instant.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-brand-grey">
                    <th className="py-2 pr-4 font-medium">Entreprise</th>
                    <th className="py-2 pr-4 font-medium">Montant</th>
                    <th className="py-2 pr-4 font-medium">Poids</th>
                    <th className="py-2 pr-4 font-medium">Durée</th>
                    <th className="py-2 pr-4 font-medium">État</th>
                    <th className="py-2 pr-4 font-medium">Score ESG</th>
                    <th className="py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {portefeuille.positions.map((position) => (
                    <tr key={position.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">
                        <p className="font-medium text-brand-blue">{position.entreprise.nom}</p>
                        <p className="text-xs text-brand-grey">{position.entreprise.secteur}</p>
                      </td>
                      <td className="py-2 pr-4">
                        <p>{formatMontant(position.montant_investi, position.devise)}</p>
                        {position.taux_change_utilise ? (
                          <p className="text-xs text-brand-grey">
                            = {formatMontant(position.montant_converti, portefeuille.devise_reference)}
                          </p>
                        ) : null}
                      </td>
                      <td className="py-2 pr-4 tabular-nums">{formatPourcentage(position.poids * 100)}</td>
                      <td className="py-2 pr-4">
                        {position.type_duree === TypeDureeInvestissement.FIXE ? "Fixe" : "Ouverte"}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={variantEtatPosition(position.etat)}>
                          {libelleEtatPosition(position.etat)}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">{formatScore(position.score.valeur_globale)}</td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-2">
                          {position.etat === "PLANIFIEE" ? (
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
                          {position.type_duree === TypeDureeInvestissement.OUVERTE &&
                          position.etat !== "CLOTUREE" ? (
                            <Button size="sm" variant="outline" onClick={() => setPositionAFermer(position)}>
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
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={deletePosition.isPending}
      onClick={() => {
        if (!window.confirm("Supprimer cette position planifiée ?")) return;
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
        Position sur <strong>{position.entreprise.nom}</strong>, ouverte le{" "}
        {new Date(position.date_debut).toLocaleDateString("fr-FR")}.
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
            { positionId: position.id, payload: { date_fin: new Date(dateFin).toISOString() } },
            {
              onSuccess: onDone,
              onError: (error) =>
                setServerError(error instanceof ApiError ? error.message : "Échec de la fermeture."),
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
  const [rechercheEntreprise, setRechercheEntreprise] = useState("");
  const { data } = usePublishedCompanies({ recherche: rechercheEntreprise });
  const entreprisesDisponibles = data?.pages.flatMap((page) => page.items) ?? [];
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<AjouterPositionForm>({
    // Même schéma en modification : entreprise_id reste rempli (figé sur position.entreprise.id,
    // jamais affiché ni modifiable, voir plus bas) — seul le champ change, jamais sa présence.
    resolver: zodResolver(ajouterPositionSchema),
    defaultValues: position
      ? {
          entreprise_id: position.entreprise.id,
          montant: position.montant_investi,
          devise: position.devise,
          type_duree: position.type_duree,
          date_debut: position.date_debut.slice(0, 10),
          date_fin: position.date_fin?.slice(0, 10) ?? "",
        }
      : {
          entreprise_id: "",
          montant: 0,
          devise: DEVISES[0],
          type_duree: TYPES_DUREE[0],
          date_debut: new Date().toISOString().slice(0, 10),
          date_fin: "",
        },
  });
  const typeDuree = form.watch("type_duree");

  function onSubmit(values: AjouterPositionForm) {
    setServerError(null);
    const payload = {
      montant: values.montant,
      devise: values.devise,
      type_duree: values.type_duree,
      date_debut: new Date(values.date_debut).toISOString(),
      date_fin: values.date_fin ? new Date(values.date_fin).toISOString() : undefined,
    };
    const onError = (error: unknown) =>
      setServerError(error instanceof ApiError ? error.message : "Échec de l'enregistrement.");

    if (position) {
      updatePosition.mutate(
        { positionId: position.id, payload: { ...payload, date_fin: payload.date_fin ?? null } },
        { onSuccess: onDone, onError },
      );
    } else {
      addPosition.mutate(
        { ...payload, entreprise_id: values.entreprise_id },
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
            name="entreprise_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Entreprise publiée</FormLabel>
                <Input
                  placeholder="Rechercher une entreprise..."
                  value={rechercheEntreprise}
                  onChange={(event) => setRechercheEntreprise(event.target.value)}
                  className="mb-2"
                />
                <FormControl>
                  <Select {...field}>
                    <option value="">Sélectionner...</option>
                    {entreprisesDisponibles.map((entreprise) => (
                      <option key={entreprise.id} value={entreprise.id}>
                        {entreprise.nom} — {entreprise.secteur}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="montant"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Montant</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    step="0.01"
                    value={field.value}
                    onChange={(event) => field.onChange(event.target.valueAsNumber)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="devise"
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
          name="type_duree"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Type de durée</FormLabel>
              <FormControl>
                <Select {...field}>
                  <option value={TypeDureeInvestissement.OUVERTE}>Ouverte</option>
                  <option value={TypeDureeInvestissement.FIXE}>Fixe</option>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="date_debut"
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
          {typeDuree === TypeDureeInvestissement.FIXE ? (
            <FormField
              control={form.control}
              name="date_fin"
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

        <Button type="submit" className="w-full" disabled={enCours}>
          {enCours ? "Enregistrement..." : position ? "Enregistrer les modifications" : "Ajouter"}
        </Button>
      </form>
    </Form>
  );
}
