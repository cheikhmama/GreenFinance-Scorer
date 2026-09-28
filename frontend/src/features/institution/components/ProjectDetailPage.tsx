import { Building2, FileText, Search, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libelleStatutAnalyse, variantStatutAnalyse } from "@/shared/format/statutAnalyse";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/shared/ui/dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { InitialsAvatar } from "@/shared/ui/initials-avatar";
import { Input } from "@/shared/ui/input";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import {
  useAddCompanyToScope,
  useAddDocument,
  useAssignResearcher,
  useCloseProject,
  useMyResearchers,
  useProjectDetail,
  usePublishedCompaniesForInstitution,
} from "../api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR");
}

export function ProjectDetailPage() {
  const { projetId = "" } = useParams();
  const { data: projet, isLoading, isError } = useProjectDetail(projetId);
  const { data: chercheursAcceptes } = useMyResearchers("ACCEPTE");
  const assigner = useAssignResearcher(projetId);
  const cloturer = useCloseProject(projetId);
  const confirm = useConfirm();
  const [chercheurASelectionner, setChercheurASelectionner] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [perimetreOuvert, setPerimetreOuvert] = useState(false);

  if (isLoading) return <p className="text-brand-grey">Chargement...</p>;
  if (isError || !projet) return <p className="text-destructive">Projet introuvable.</p>;

  const dejaAffectes = new Set(projet.affectations.map((a) => a.chercheur_id));
  const candidats = (chercheursAcceptes ?? []).filter((r) => !dejaAffectes.has(r.chercheur_id));
  const documentesIds = new Set(projet.documents.map((d) => d.entreprise_id));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Institution"
        title={projet.nom}
        description={projet.objectif ?? projet.description ?? "Aucune description."}
        action={
          <div className="flex items-center gap-2">
            <Badge variant={variantStatutProjet(projet.statut)}>{libelleStatutProjet(projet.statut)}</Badge>
            {projet.statut === "OUVERT" ? (
              <Button
                variant="outline"
                size="sm"
                disabled={cloturer.isPending}
                onClick={async () => {
                  const confirme = await confirm({
                    title: "Clôturer ce projet ?",
                    description: "Aucune nouvelle affectation de chercheur ne sera possible ensuite. Cette action est irréversible.",
                    confirmLabel: "Clôturer",
                    destructive: true,
                  });
                  if (confirme) cloturer.mutate();
                }}
              >
                Clôturer
              </Button>
            ) : null}
          </div>
        }
      />
      {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}

      {projet.date_debut || projet.date_fin_prevue || projet.date_limite ? (
        <Card>
          <CardContent className="flex flex-wrap gap-6 text-sm">
            {projet.date_debut ? <Champ label="Début" valeur={formatDate(projet.date_debut)} /> : null}
            {projet.date_fin_prevue ? (
              <Champ label="Fin prévue" valeur={formatDate(projet.date_fin_prevue)} />
            ) : null}
            {projet.date_limite ? (
              <Champ label="Date limite" valeur={formatDate(projet.date_limite)} />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <UserPlus className="size-4" />
            Chercheurs affectés
          </CardTitle>
          {projet.statut === "OUVERT" && candidats.length > 0 ? (
            <div className="flex items-center gap-2">
              <Select
                value={chercheurASelectionner}
                onChange={(event) => setChercheurASelectionner(event.target.value)}
                className="w-56"
              >
                <option value="">Sélectionner un chercheur accepté...</option>
                {candidats.map((rattachement) => (
                  <option key={rattachement.chercheur_id} value={rattachement.chercheur_id}>
                    {rattachement.chercheur_nom ?? rattachement.chercheur_email}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                disabled={!chercheurASelectionner || assigner.isPending}
                onClick={() =>
                  assigner.mutate(
                    { chercheur_id: chercheurASelectionner },
                    {
                      onSuccess: () => setChercheurASelectionner(""),
                      onError: (error) =>
                        setErreur(error instanceof ApiError ? error.message : "Échec de l'affectation."),
                    },
                  )
                }
              >
                Affecter
              </Button>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          {projet.affectations.length === 0 ? (
            <EmptyState icon={UserPlus} message="Aucun chercheur affecté pour l'instant." />
          ) : (
            projet.affectations.map((affectation) => (
              <div key={affectation.id} className="flex items-center gap-3 border-b py-2 text-sm last:border-0">
                <InitialsAvatar nom={affectation.chercheur_email} size="sm" />
                <span className="flex-1 font-medium text-brand-blue">{affectation.chercheur_email}</span>
                <span className="text-brand-grey">depuis le {formatDate(affectation.date_affectation)}</span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Building2 className="size-4" />
            Périmètre autorisé ({projet.perimetre.length})
          </CardTitle>
          {projet.statut === "OUVERT" ? (
            <Button size="sm" variant="outline" onClick={() => setPerimetreOuvert(true)}>
              Ajouter une entreprise
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-brand-grey">
            Seules ces entreprises pourront être comparées dans une analyse de ce projet.
          </p>
          {projet.perimetre.length === 0 ? (
            <EmptyState
              icon={Building2}
              message="Aucune entreprise n'est encore autorisée — les chercheurs affectés ne pourront créer aucune analyse tant que le périmètre est vide."
            />
          ) : (
            projet.perimetre.map((entreprise) => (
              <div key={entreprise.id} className="flex items-center gap-3 border-b py-2 text-sm last:border-0">
                <CompanyAvatar nom={entreprise.entreprise_nom} logo={null} className="size-8" />
                <Link
                  to={`/institution/entreprises/${entreprise.entreprise_id}`}
                  className="flex-1 font-medium text-brand-blue underline-offset-2 hover:underline"
                >
                  {entreprise.entreprise_nom}
                </Link>
                {documentesIds.has(entreprise.entreprise_id) ? (
                  <Badge variant="success">Document mis à disposition</Badge>
                ) : (
                  <BoutonMettreADisposition projetId={projet.id} entreprise={entreprise} />
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <FileText className="size-4" />
            Documents mis à disposition ({projet.documents.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {projet.documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              message="Aucun document mis à disposition — utilisez le bouton sur une entreprise du périmètre ci-dessus."
            />
          ) : (
            projet.documents.map((document) => (
              <div key={document.id} className="flex items-center gap-3 border-b py-2 text-sm last:border-0">
                <CompanyAvatar nom={document.entreprise_nom} logo={null} className="size-8" />
                <span className="flex-1 font-medium text-brand-blue">{document.entreprise_nom}</span>
                {document.annee_reporting ? (
                  <span className="text-brand-grey">{document.annee_reporting}</span>
                ) : null}
                <span className="text-xs text-brand-grey">ajouté le {formatDate(document.date_ajout)}</span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-brand-blue">Analyses reçues</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {projet.analyses.length === 0 ? (
            <EmptyState icon={FileText} message="Aucune analyse soumise pour l'instant." />
          ) : (
            projet.analyses.map((analyse) => (
              <Link
                key={analyse.id}
                to={`/institution/analyses/${analyse.id}`}
                className="flex items-center justify-between border-b py-2 text-sm last:border-0 hover:bg-muted"
              >
                <span className="font-medium text-brand-blue">
                  {analyse.titre} (v{analyse.version})
                </span>
                <Badge variant={variantStatutAnalyse(analyse.statut)}>
                  {libelleStatutAnalyse(analyse.statut)}
                </Badge>
              </Link>
            ))
          )}
        </CardContent>
      </Card>

      <SelectionEntrepriseDialog
        projetId={projet.id}
        open={perimetreOuvert}
        onOpenChange={setPerimetreOuvert}
        dejaDansLePerimetre={new Set(projet.perimetre.map((e) => e.entreprise_id))}
      />
    </div>
  );
}

function Champ({ label, valeur }: { label: string; valeur: string }) {
  return (
    <div>
      <p className="text-xs text-brand-grey">{label}</p>
      <p className="font-medium text-brand-blue">{valeur}</p>
    </div>
  );
}

function BoutonMettreADisposition({
  projetId,
  entreprise,
}: {
  projetId: string;
  entreprise: { entreprise_id: string; dernier_rapport_id: string | null };
}) {
  const ajouter = useAddDocument(projetId);
  const [erreur, setErreur] = useState<string | null>(null);
  const rapportId = entreprise.dernier_rapport_id;

  if (!rapportId) {
    return <span className="text-xs text-brand-grey">Aucun rapport publié à mettre à disposition.</span>;
  }

  return (
    <div className="flex items-center gap-2">
      {erreur ? <span className="text-xs text-destructive">{erreur}</span> : null}
      <Button
        size="sm"
        variant="outline"
        disabled={ajouter.isPending}
        onClick={() =>
          ajouter.mutate(
            { rapport_id: rapportId },
            {
              onError: (error) =>
                setErreur(error instanceof ApiError ? error.message : "Échec de l'ajout."),
            },
          )
        }
      >
        {ajouter.isPending ? "Ajout..." : "Mettre à disposition"}
      </Button>
    </div>
  );
}

/** Recherche parmi les entreprises publiées de la plateforme pour composer le périmètre — jamais
 * une saisie libre d'identité, toujours une sélection dans le catalogue réel (même principe que
 * l'invitation d'un chercheur). */
function SelectionEntrepriseDialog({
  projetId,
  open,
  onOpenChange,
  dejaDansLePerimetre,
}: {
  projetId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dejaDansLePerimetre: Set<string>;
}) {
  const [recherche, setRecherche] = useState("");
  const rechercheDebattue = useDebouncedValue(recherche);
  const { data } = usePublishedCompaniesForInstitution({ recherche: rechercheDebattue });
  const ajouter = useAddCompanyToScope(projetId);
  const [erreur, setErreur] = useState<string | null>(null);
  const entreprises = (data?.pages.flatMap((page) => page.items) ?? []).filter(
    (entreprise) => !dejaDansLePerimetre.has(entreprise.id),
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajouter une entreprise au périmètre</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <label htmlFor="recherche-perimetre" className="relative block">
            <span className="sr-only">Rechercher une entreprise publiée</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-grey" />
            <Input
              id="recherche-perimetre"
              value={recherche}
              onChange={(event) => setRecherche(event.target.value)}
              placeholder="Rechercher par nom ou secteur"
              className="pl-9"
            />
          </label>
          {erreur ? <p className="text-sm text-destructive">{erreur}</p> : null}
          <div className="max-h-72 space-y-1 overflow-y-auto">
            {entreprises.map((entreprise) => (
              <div key={entreprise.id} className="flex items-center gap-3 rounded-md border p-2">
                <CompanyAvatar nom={entreprise.nom} logo={entreprise.logo} className="size-8" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-brand-blue">{entreprise.nom}</p>
                  <p className="truncate text-xs text-brand-grey">{entreprise.secteur}</p>
                </div>
                <Button
                  size="sm"
                  disabled={ajouter.isPending}
                  onClick={() =>
                    ajouter.mutate(
                      { entreprise_id: entreprise.id },
                      {
                        onError: (error) =>
                          setErreur(error instanceof ApiError ? error.message : "Échec de l'ajout."),
                      },
                    )
                  }
                >
                  Ajouter
                </Button>
              </div>
            ))}
            {entreprises.length === 0 ? (
              <p className="p-2 text-sm text-brand-grey">Aucun résultat.</p>
            ) : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
