import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/shared/ui/page-header";
import { JournalAuditSection } from "./JournalAuditSection";

export function AdminJournalAuditPage() {
  const [searchParams] = useSearchParams();
  const concerneId = searchParams.get("concerne") ?? undefined;

  return (
    <div className="space-y-8">
      <PageHeader title="Journal d'audit" />
      <JournalAuditSection concerneId={concerneId} />
    </div>
  );
}
