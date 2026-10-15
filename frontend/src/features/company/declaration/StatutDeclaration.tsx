import { CheckCircle2, CircleAlert, FileText, Loader2, Lock, XCircle } from "lucide-react";
import type { ReportStatus } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { phaseDeclaration } from "@/shared/format/phaseDeclaration";
import { StatusBadge } from "@/shared/ui/status-badge";

/** Badge de phase d'une déclaration (spec §5.1) — remplace libelleStatutRapportEntreprise dans
 * l'espace Entreprise. */
export function StatutDeclaration({
  rapport,
}: {
  rapport: { status: ReportStatus; extraction_error: string | null };
}) {
  const phase = phaseDeclaration(rapport);
  const icone =
    phase.branche !== null
      ? CircleAlert
      : [FileText, Loader2, Lock, phase.ton === "danger" ? XCircle : CheckCircle2][phase.index];
  return (
    <StatusBadge
      libelle={phase.libelle}
      ton={phase.ton}
      icone={icone}
      enCours={rapport.status === "EXTRACTING"}
    />
  );
}
