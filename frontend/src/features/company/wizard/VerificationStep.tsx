import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ApiError } from "@/shared/api/errors";
import type { RapportESGDetail } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { useReportChecklist, useSubmitDraft } from "../api";
import { CompletenessChecklist } from "../session/CompletenessChecklist";
import { dateHeure, totaux } from "../session/etat";

function Ligne({ libelle, children }: { libelle: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[10rem_1fr]">
      <dt className="text-brand-grey">{libelle}</dt>
      <dd className="min-w-0 text-brand-blue">{children}</dd>
    </div>
  );
}

/** Étape 4 (spec §3.1) : liste de complétude (des comptes, jamais de valeurs), récapitulatif,
 * confirmation explicite, puis reçu affiché sur place. */
export function VerificationStep({ rapport }: { rapport: RapportESGDetail }) {
  const liste = useReportChecklist(rapport.id, rapport.extraction_finished_at);
  const soumettre = useSubmitDraft(rapport.id);
  const [confirme, setConfirme] = useState(false);
  const recu = soumettre.data;
  const titreRecu = useRef<HTMLHeadingElement>(null);
  const recuAffiche = Boolean(recu?.submitted_at);
  // Le reçu remplace le formulaire : le focus clavier suit, sinon il serait perdu avec le bouton.
  useEffect(() => {
    if (recuAffiche) titreRecu.current?.focus();
  }, [recuAffiche]);

  if (recu?.submitted_at) {
    return (
      <Card role="region" aria-label="Reçu de soumission">
        <CardHeader>
          <h2 ref={titreRecu} tabIndex={-1} className="font-semibold leading-none outline-none">
            Reçu de soumission
          </h2>
          <CardDescription>
            Votre rapport est transmis et verrouillé. Conservez ce reçu : l’empreinte identifie
            exactement le fichier soumis.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="space-y-2 text-sm">
            <Ligne libelle="Rapport">
              {titreDeclaration({ type: recu.report_type, fiscal_year: recu.fiscal_year })}
            </Ligne>
            <Ligne libelle="Fichier">{recu.original_filename ?? "—"}</Ligne>
            <Ligne libelle="Soumis le">{dateHeure(recu.submitted_at)}</Ligne>
            <Ligne libelle="Empreinte SHA-256">
              <code className="break-all font-mono text-xs">{recu.checksum_sha256}</code>
            </Ligne>
            <Ligne libelle="Référence">
              <code className="break-all font-mono text-xs">{recu.id}</code>
            </Ligne>
          </dl>
          <Button asChild>
            <Link to="../.." relative="path">
              Terminer
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Déclaration déjà soumise, sans reçu à montrer (adresse retapée plus tard) : sa synthèse.
  if (rapport.submitted_at !== null) return <Navigate to="../.." relative="path" replace />;

  const groupes = liste.data ?? [];
  const total = totaux(groupes);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Vérification</CardTitle>
        <CardDescription>
          Une fois soumis, le rapport est verrouillé pendant l’examen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {liste.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <CompletenessChecklist groupes={groupes} />
        )}
        <dl className="space-y-2 text-sm">
          <Ligne libelle="Rapport">{titreDeclaration(rapport)}</Ligne>
          <Ligne libelle="Fichier">{rapport.original_filename ?? "—"}</Ligne>
          <Ligne libelle="Empreinte SHA-256">
            <code className="break-all font-mono text-xs">{rapport.checksum_sha256}</code>
          </Ligne>
          <Ligne libelle="Complétude">
            {total.found} indicateur(s) trouvé(s) sur {total.expected}
          </Ligne>
        </dl>
        {soumettre.isError ? (
          <Alert variant="destructive">
            <AlertDescription>
              {soumettre.error instanceof ApiError
                ? soumettre.error.message
                : "La soumission n’a pas abouti."}
            </AlertDescription>
          </Alert>
        ) : null}
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4"
            checked={confirme}
            onChange={(e) => setConfirme(e.target.checked)}
          />
          Je confirme ces informations : la déclaration sera verrouillée pendant l’examen.
        </label>
        <div className="flex justify-between gap-2 border-t pt-4">
          <Button asChild variant="outline">
            <Link to="../document" relative="path">
              Précédent
            </Link>
          </Button>
          <Button onClick={() => soumettre.mutate()} disabled={!confirme || soumettre.isPending}>
            {soumettre.isPending ? "Soumission…" : "Soumettre la déclaration"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
