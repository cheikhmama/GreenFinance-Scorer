import { Building2, FileText } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { CompanyAvatar } from "@/shared/esg/CompanyAvatar";
import { libelleStatutProjet, variantStatutProjet } from "@/shared/format/statutProjet";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageHeader } from "@/shared/ui/page-header";
import { useMyAssignedProjects, useProjectDocuments, useProjectScope } from "../api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR");
}

/** Détail d'un projet affecté : objectif/échéances (posés par l'Institution), périmètre autorisé
 * (ProjetEntreprise — les seules entreprises comparables dans une analyse de ce projet) et
 * documents mis à disposition (ProjetDocument — un sous-ensemble du périmètre, jamais déduit
 * automatiquement). Aucun endpoint de détail dédié côté backend : le projet est retrouvé dans la
 * liste déjà chargée par useMyAssignedProjects, périmètre et documents ont chacun leur route. */
export function ProjetDetailPage() {
  const { projetId = "" } = useParams();
  const { data: projets, isLoading: chargementProjets } = useMyAssignedProjects();
  const { data: perimetre, isLoading: chargementPerimetre } = useProjectScope(projetId);
  const { data: documents, isLoading: chargementDocuments } = useProjectDocuments(projetId);

  const projet = projets?.find((p) => p.id === projetId);

  if (chargementProjets) return <p className="text-brand-grey">Chargement...</p>;
  if (!projet) return <p className="text-destructive">Projet introuvable.</p>;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={projet.institution_email}
        title={projet.name}
        description={projet.objective ?? "Aucun objectif renseigné par l'institution."}
        action={
          <Badge variant={variantStatutProjet(projet.status)}>{libelleStatutProjet(projet.status)}</Badge>
        }
      />

      {projet.start_date || projet.planned_end_date || projet.deadline ? (
        <Card>
          <CardContent className="flex flex-wrap gap-6 text-sm">
            {projet.start_date ? <Champ label="Début" valeur={formatDate(projet.start_date)} /> : null}
            {projet.planned_end_date ? (
              <Champ label="Fin prévue" valeur={formatDate(projet.planned_end_date)} />
            ) : null}
            {projet.deadline ? (
              <Champ label="Date limite" valeur={formatDate(projet.deadline)} />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <Building2 className="size-4" />
            Entreprises autorisées ({perimetre?.length ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementPerimetre ? <p className="text-brand-grey">Chargement...</p> : null}
          {!chargementPerimetre && perimetre?.length === 0 ? (
            <EmptyState
              icon={Building2}
              message="Aucune entreprise n'a encore été autorisée pour ce projet — contactez l'institution."
            />
          ) : null}
          {perimetre?.map((entreprise) => (
            <Link
              key={entreprise.id}
              to={`/researcher/entreprises/${entreprise.company_id}`}
              className="flex items-center gap-3 rounded-md border p-2 text-sm transition hover:border-brand-green"
            >
              <CompanyAvatar nom={entreprise.company_name} logo={null} className="size-8" />
              <span className="font-medium text-brand-blue">{entreprise.company_name}</span>
            </Link>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
            <FileText className="size-4" />
            Documents mis à disposition ({documents?.length ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {chargementDocuments ? <p className="text-brand-grey">Chargement...</p> : null}
          {!chargementDocuments && documents?.length === 0 ? (
            <EmptyState icon={FileText} message="Aucun document mis à disposition sur ce projet pour l'instant." />
          ) : null}
          {documents?.map((document) => (
            <Link
              key={document.id}
              to={`/researcher/entreprises/${document.company_id}`}
              className="flex items-center gap-3 rounded-md border p-2 text-sm transition hover:border-brand-green"
            >
              <CompanyAvatar nom={document.company_name} logo={null} className="size-8" />
              <span className="font-medium text-brand-blue">{document.company_name}</span>
              {document.fiscal_year ? (
                <span className="text-brand-grey"> — {document.fiscal_year}</span>
              ) : null}
            </Link>
          ))}
        </CardContent>
      </Card>
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
