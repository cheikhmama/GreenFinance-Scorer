import { PageHeader } from "@/shared/ui/page-header";
import { AllCompaniesSection } from "./AllCompaniesSection";
import { PublishableCompaniesSection } from "./PublishableCompaniesSection";

export function AdminCompaniesPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Entreprises"
        description="Suivi de toutes les entreprises, et publication de celles prêtes à l'être."
      />
      <AllCompaniesSection />
      <PublishableCompaniesSection />
    </div>
  );
}
