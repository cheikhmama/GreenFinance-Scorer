import { CheckCircle2 } from "lucide-react";
import type { EntreprisePublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Badge } from "@/shared/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useMyLeiVerification } from "../api";

/** Immatriculations de l'entreprise connectée (tâche 5.9) — secteur, LEI, ISIN, tels que
 * déclarés. « GLEIF Validé » n'apparaît que si la GLEIF confirme en direct l'enregistrement et le
 * nom légal ; une donnée absente n'est jamais remplacée par une valeur inventée. Ces métadonnées
 * vivent dans le Profil, plus dans l'en-tête des pages de l'espace. */
export function CompanyRegistrationsCard({ entreprise }: { entreprise: EntreprisePublic }) {
  const verification = useMyLeiVerification(entreprise.lei);

  return (
    <Card role="region" aria-label="Immatriculations">
      <CardHeader>
        <CardTitle className="text-base">Immatriculations</CardTitle>
        <CardAction>
          {verification.data?.result === "PASSED" ? (
            <Badge variant="success" title={verification.data.detail}>
              <CheckCircle2 className="size-3" aria-hidden="true" />
              GLEIF Validé
            </Badge>
          ) : null}
          {verification.data?.result === "FAILED" ? (
            <Badge variant="warning" title={verification.data.detail}>
              LEI non confirmé par la GLEIF
            </Badge>
          ) : null}
        </CardAction>
      </CardHeader>
      <CardContent>
        <dl aria-label="Identité de l’entreprise" className="divide-y divide-border text-sm">
          <Ligne libelle="Raison sociale" valeur={entreprise.name} />
          <Ligne libelle="Secteur" valeur={entreprise.sector} />
          <Ligne libelle="Pays" valeur={entreprise.country} />
          {entreprise.lei ? <Ligne libelle="LEI" valeur={entreprise.lei} code /> : null}
          {entreprise.isin ? <Ligne libelle="ISIN" valeur={entreprise.isin} code /> : null}
        </dl>
      </CardContent>
    </Card>
  );
}

function Ligne({ libelle, valeur, code }: { libelle: string; valeur: string; code?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0">
      <dt className="text-muted-foreground">{libelle}</dt>
      <dd className="truncate text-right font-medium text-foreground">
        {code ? <code className="font-mono">{valeur}</code> : valeur}
      </dd>
    </div>
  );
}
