import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { libelleIdentifiantFiscal, nomDuPays } from "@/features/registration/referentiels";
import type { EntrepriseProfil } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useMyLeiVerification } from "../api";

/** Immatriculations de l'entreprise connectée (tâches 5.9, 5.10) — raison sociale, pays,
 * identifiant fiscal, LEI, ISIN, ticker, tels que déclarés. « GLEIF Validé » n'apparaît que si la
 * GLEIF confirme en direct l'enregistrement et le nom légal ; une donnée absente est dite « Non
 * renseigné », jamais remplacée par une valeur inventée. */
export function CompanyRegistrationsCard({ entreprise }: { entreprise: EntrepriseProfil }) {
  const verification = useMyLeiVerification(entreprise.lei);
  const resultat = verification.data?.result;

  return (
    <Card role="region" aria-label="Immatriculations">
      <CardHeader>
        <CardTitle className="text-base">Immatriculations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl aria-label="Identité de l’entreprise" className="divide-y divide-border text-sm">
          <Ligne libelle="Raison sociale" valeur={entreprise.name} />
          <Ligne libelle="Secteur" valeur={entreprise.sector} />
          <Ligne libelle="Pays" valeur={nomDuPays(entreprise.country)} />
          <Ligne
            libelle={
              entreprise.tax_id_type === "TAX_ID" || !entreprise.tax_id_type
                ? libelleIdentifiantFiscal(entreprise.country)
                : entreprise.tax_id_type
            }
            valeur={entreprise.tax_id}
            code
          />
          <Ligne libelle="LEI" valeur={entreprise.lei} code />
          <Ligne libelle="ISIN" valeur={entreprise.isin} code />
          <Ligne libelle="Ticker" valeur={entreprise.ticker} code />
        </dl>

        {resultat === "PASSED" ? (
          <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50/50 p-3 text-sm dark:border-emerald-800 dark:bg-emerald-950/30">
            <CheckCircle2
              className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
              aria-hidden="true"
            />
            <div>
              <Badge variant="success">GLEIF Validé</Badge>
              <p className="mt-1 text-xs text-muted-foreground">{verification.data?.detail}</p>
            </div>
          </div>
        ) : null}
        {resultat === "FAILED" ? (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50/50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950/30">
            <AlertTriangle
              className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400"
              aria-hidden="true"
            />
            <div>
              <Badge variant="warning">LEI non confirmé par la GLEIF</Badge>
              <p className="mt-1 text-xs text-muted-foreground">{verification.data?.detail}</p>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Ligne({
  libelle,
  valeur,
  code,
}: {
  libelle: string;
  valeur: string | null | undefined;
  code?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 first:pt-0 last:pb-0">
      <dt className="shrink-0 text-muted-foreground">{libelle}</dt>
      <dd className="min-w-0 truncate text-right font-medium text-foreground">
        {valeur ? (
          code ? (
            <code className="font-mono">{valeur}</code>
          ) : (
            valeur
          )
        ) : (
          <span className="font-normal text-muted-foreground">Non renseigné</span>
        )}
      </dd>
    </div>
  );
}
