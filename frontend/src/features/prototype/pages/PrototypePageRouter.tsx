import type { RoleSlug } from "../types";
import { AdminPrototypePage } from "./AdminPrototypePage";
import { AuditPrototypePage } from "./AuditPrototypePage";
import { CompanyPrototypePage } from "./CompanyPrototypePage";
import { InstitutionPrototypePage } from "./InstitutionPrototypePage";
import { InvestorPrototypePage } from "./InvestorPrototypePage";
import { ResearcherPrototypePage } from "./ResearcherPrototypePage";

export function PrototypePageRouter({ role, section }: { role: RoleSlug; section: string }) {
  if (role === "admin") return <AdminPrototypePage section={section} />;
  if (role === "company") return <CompanyPrototypePage section={section} />;
  if (role === "audit") return <AuditPrototypePage section={section} />;
  if (role === "investor") return <InvestorPrototypePage section={section} />;
  if (role === "researcher") return <ResearcherPrototypePage section={section} />;
  return <InstitutionPrototypePage section={section} />;
}
