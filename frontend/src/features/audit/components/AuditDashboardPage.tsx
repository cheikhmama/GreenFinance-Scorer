import { Link } from "react-router-dom";
import { libelleStatutRapport, variantStatutRapport } from "@/shared/format/statut";
import { titreDeclaration } from "@/shared/format/typeRapport";
import { PageShell } from "@/shared/layout/PageShell";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Skeleton } from "@/shared/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import { useAssignedReports } from "../api";

/** Espace Auditeur réel (Phase 4 §4.5) — dossiers affectés, en attente d'avis. */
export function AuditDashboardPage() {
  const { data: dossiers, isLoading, isError } = useAssignedReports();

  return (
    <PageShell
      title="Dossiers affectés"
      description="Rapports qui vous ont été affectés, en attente de votre avis."
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dossiers en attente d'avis</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <Skeleton className="h-32 w-full" /> : null}
          {isError ? (
            <p className="text-sm text-destructive">Impossible de charger vos dossiers.</p>
          ) : null}
          {!isLoading && !isError && dossiers?.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun dossier en attente d'avis pour l'instant.
            </p>
          ) : null}
          {dossiers && dossiers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Entreprise</TableHead>
                  <TableHead>Déclaration</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Déposé le</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dossiers.map((dossier) => (
                  <TableRow key={dossier.id}>
                    <TableCell>
                      <p className="font-medium text-foreground">{dossier.company_name}</p>
                      <p className="text-xs text-muted-foreground">{dossier.company_sector}</p>
                    </TableCell>
                    <TableCell className="text-foreground">{titreDeclaration(dossier)}</TableCell>
                    <TableCell>
                      <Badge variant={variantStatutRapport(dossier.status)}>
                        {libelleStatutRapport(dossier.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {dossier.submitted_at
                        ? new Date(dossier.submitted_at).toLocaleDateString("fr-FR")
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/audit/rapports/${dossier.id}`}>Examiner</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </PageShell>
  );
}
