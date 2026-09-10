import { PageHeader } from "@/shared/ui/page-header";
import { ReportsInValidationSection } from "./ReportsInValidationSection";
import { ReportsToAssignSection } from "./ReportsToAssignSection";

export function AdminReportsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Rapports"
        description="Affectation à un auditeur, puis décision (valider, rejeter ou demander une correction)."
      />
      <ReportsToAssignSection />
      <ReportsInValidationSection />
    </div>
  );
}
