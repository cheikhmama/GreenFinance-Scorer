import { Cpu } from "lucide-react";
import type { ExtractionRunStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { libelleCauseExtraction } from "@/shared/format/causeExtraction";
import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useReportExtractionRuns } from "../api";

const STATUTS: Record<
  ExtractionRunStatus,
  { libelle: string; variante: "secondary" | "success" | "destructive" | "warning" }
> = {
  RUNNING: { libelle: "En cours", variante: "secondary" },
  SUCCEEDED: { libelle: "Réussie", variante: "success" },
  FAILED: { libelle: "Échouée", variante: "destructive" },
  RETRY_SCHEDULED: { libelle: "Reprise programmée", variante: "warning" },
};

/** Provenance de l'extraction d'un rapport (tâche 5.5) : chaque exécution du pipeline, avec la
 * version de Docling, le modèle LLM et la version du prompt qui ont produit les valeurs. */
export function ExtractionRunsCard({ rapportId }: { rapportId: string }) {
  const { data, isPending, isError } = useReportExtractionRuns(rapportId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base text-brand-blue">
          <Cpu className="size-4" aria-hidden="true" />
          Provenance de l’extraction
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-16 w-full" /> : null}
        {isError ? <p className="text-destructive">Impossible de charger les exécutions.</p> : null}
        {data && data.length === 0 ? (
          <p className="text-sm text-brand-grey">
            Aucune exécution enregistrée (rapport extrait avant le suivi de provenance).
          </p>
        ) : null}
        {data && data.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Début</TableHead>
                <TableHead>Issue</TableHead>
                <TableHead>Modèle</TableHead>
                <TableHead>Prompt</TableHead>
                <TableHead>Docling</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((execution) => (
                <TableRow key={execution.id}>
                  <TableCell className="whitespace-nowrap">
                    {new Date(execution.started_at).toLocaleString("fr-FR")}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUTS[execution.status].variante}>
                      {STATUTS[execution.status].libelle}
                    </Badge>
                    {execution.error ? (
                      <span className="ml-2 text-xs text-brand-grey" title={execution.error}>
                        {libelleCauseExtraction(execution.error)}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell>{execution.llm_model}</TableCell>
                  <TableCell>{execution.prompt_version}</TableCell>
                  <TableCell>{execution.docling_version}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : null}
      </CardContent>
    </Card>
  );
}
