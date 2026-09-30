import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  FileSearch,
  FileText,
  Gauge,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import {
  EvidencePreview,
  fieldClassName,
  Modal,
  PageHeader,
  ProgressBar,
  StatCard,
  StatusBadge,
} from "../components/shared";
import { UserProvisioningModal } from "../components/UserProvisioningModal";
import { allRoleConfigs } from "../config";
import { usePrototype } from "../PrototypeContext";
import type {
  AccountStatus,
  Methodology,
  PrototypeCompany,
  PrototypeReport,
  PrototypeRole,
  PrototypeUser,
} from "../types";

interface AdminPrototypePageProps {
  section: string;
}

const roleLabels: Record<PrototypeRole, string> = {
  ADMIN: "Administrateur",
  ENTERPRISE: "Entreprise",
  AUDITOR: "Auditeur",
  INVESTOR: "Investisseur",
  RESEARCHER: "Chercheur",
  INSTITUTION: "Institution",
};

const accountStatusLabels: Record<AccountStatus, string> = {
  ACTIF: "Actif",
  INVITE: "Invité",
  DESACTIVE: "Désactivé",
};

const numberFormatter = new Intl.NumberFormat("fr-FR");
const NOMBRE_VISIBLE_PAR_DEFAUT = 5;

function getRoleHome(role: PrototypeRole) {
  const config = allRoleConfigs.find((item) => item.role === role);
  if (!config) return "/prototype/admin/dashboard";
  return `/prototype/${config.slug}/${config.navigation[0].section}`;
}

function nextMethodologyVersion(version: string) {
  const match = /^v(\d+)\.(\d+)$/.exec(version);
  if (!match) return `${version}.1`;
  return `v${match[1]}.${Number(match[2]) + 1}`;
}

function DashboardSection() {
  const navigate = useNavigate();
  const { companies, reports, users } = usePrototype();

  const activeUsers = users.filter((user) => user.status === "ACTIF").length;
  const reportsToAssign = reports.filter((report) =>
    ["SOUMIS", "A_AFFECTER"].includes(report.status),
  ).length;
  const decisionsToMake = reports.filter(
    (report) =>
      report.status === "CORRECTION_SOUMISE" ||
      report.status === "VALIDE" ||
      (report.status === "EN_AUDIT" && report.opinion),
  ).length;
  const workQueue = reports.filter((report) =>
    ["SOUMIS", "A_AFFECTER", "CORRECTION_SOUMISE", "VALIDE"].includes(report.status),
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Tableau de bord"
        description="Les actions qui nécessitent une intervention administrative, sans surcharge opérationnelle."
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicateurs clés">
        <StatCard
          label="Entreprises"
          value={companies.length}
          hint={`${companies.filter((company) => company.published).length} publiées`}
          icon={<Building2 className="size-5" />}
        />
        <StatCard
          label="Utilisateurs actifs"
          value={activeUsers}
          hint={`${users.length - activeUsers} accès à suivre`}
          icon={<Users className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Rapports sans auditeur"
          value={reportsToAssign}
          hint="Affectation nécessaire"
          icon={<ClipboardCheck className="size-5" />}
          tone="amber"
        />
        <StatCard
          label="Décisions à rendre"
          value={decisionsToMake}
          hint="Validation ou publication"
          icon={<FileCheck2 className="size-5" />}
          tone="violet"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_0.8fr]">
        <Card className="gap-0 py-0 shadow-none">
          <CardHeader className="flex-row items-center justify-between border-b px-5 py-5">
            <div>
              <CardTitle className="text-base text-brand-blue">Actions requises</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Dossiers prêts pour une intervention de l’administrateur.
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigate("/prototype/admin/reports")}>
              Tous les rapports
              <ArrowRight />
            </Button>
          </CardHeader>
          <CardContent className="divide-y px-0">
            {workQueue.length ? (
              workQueue.map((report) => (
                <div
                  key={report.id}
                  className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center"
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-green-light text-brand-green">
                    <FileText className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-brand-blue">{report.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {report.company} · {report.year}
                    </p>
                  </div>
                  <StatusBadge status={report.status} />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate("/prototype/admin/reports")}
                  >
                    Examiner
                  </Button>
                </div>
              ))
            ) : (
              <div className="px-5 py-10 text-center">
                <CheckCircle2 className="mx-auto size-8 text-brand-green" />
                <p className="mt-3 text-sm font-semibold text-brand-blue">Aucune action urgente</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  La file administrative est à jour.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="gap-0 py-0 shadow-none">
          <CardHeader className="border-b px-5 py-5">
            <CardTitle className="text-base text-brand-blue">Accès rapides</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-xl border p-4 text-left transition hover:border-brand-green/40 hover:bg-brand-green-light/30"
              onClick={() => navigate("/prototype/admin/methodology")}
            >
              <span className="grid size-10 place-items-center rounded-lg bg-violet-50 text-violet-700">
                <SlidersHorizontal className="size-5" />
              </span>
              <span className="flex-1">
                <span className="block text-sm font-semibold text-brand-blue">
                  Méthodologie ESG
                </span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  Vérifier les pondérations
                </span>
              </span>
              <ArrowRight className="size-4 text-muted-foreground" />
            </button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function UsersSection() {
  const navigate = useNavigate();
  const { selectPreviewCompany, selectPreviewUser, setUserStatus, showToast, users } =
    usePrototype();
  const [createOpen, setCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<PrototypeRole | "TOUS">("TOUS");
  const [statusFilter, setStatusFilter] = useState<AccountStatus | "TOUS">("TOUS");
  const [afficherTout, setAfficherTout] = useState(false);

  const filteredUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");
    return users.filter((user) => {
      const matchesQuery =
        !normalizedQuery ||
        `${user.name} ${user.email} ${user.organization}`
          .toLocaleLowerCase("fr")
          .includes(normalizedQuery);
      const matchesRole = roleFilter === "TOUS" || user.role === roleFilter;
      const matchesStatus = statusFilter === "TOUS" || user.status === statusFilter;
      return matchesQuery && matchesRole && matchesStatus;
    });
  }, [query, roleFilter, statusFilter, users]);

  const visibleUsers = afficherTout
    ? filteredUsers
    : filteredUsers.slice(0, NOMBRE_VISIBLE_PAR_DEFAUT);
  const nombreMasque = filteredUsers.length - NOMBRE_VISIBLE_PAR_DEFAUT;

  function updateStatus(userId: string, currentStatus: AccountStatus) {
    const nextStatus: AccountStatus = currentStatus === "ACTIF" ? "DESACTIVE" : "ACTIF";
    setUserStatus(userId, nextStatus);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Utilisateurs"
        description="Ajouter les comptes des différents acteurs, contrôler leur statut et prévisualiser leur espace."
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <UserPlus />
            Ajouter un utilisateur
          </Button>
        }
      />

      <Card className="gap-0 py-0 shadow-none">
        <CardContent className="p-5">
          <div className="grid gap-3 lg:grid-cols-[1fr_13rem_13rem]">
            <label className="relative">
              <span className="sr-only">Rechercher un utilisateur</span>
              <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className={`${fieldClassName} pl-9`}
                placeholder="Nom, e-mail ou organisation"
              />
            </label>
            <select
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value as PrototypeRole | "TOUS")}
              className={fieldClassName}
              aria-label="Filtrer par rôle"
            >
              <option value="TOUS">Tous les rôles</option>
              {allRoleConfigs.map((config) => (
                <option key={config.role} value={config.role}>
                  {config.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as AccountStatus | "TOUS")}
              className={fieldClassName}
              aria-label="Filtrer par statut"
            >
              <option value="TOUS">Tous les statuts</option>
              <option value="ACTIF">Actifs</option>
              <option value="INVITE">Invités</option>
              <option value="DESACTIVE">Désactivés</option>
            </select>
          </div>
        </CardContent>

        <div className="overflow-x-auto border-t">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-semibold">Utilisateur</th>
                <th className="px-5 py-3 font-semibold">Rôle</th>
                <th className="px-5 py-3 font-semibold">Organisation</th>
                <th className="px-5 py-3 font-semibold">Statut</th>
                <th className="px-5 py-3 font-semibold">Dernière activité</th>
                <th className="px-5 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {visibleUsers.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 place-items-center rounded-full bg-brand-green-light text-xs font-semibold text-brand-green">
                        {user.name
                          .split(" ")
                          .slice(0, 2)
                          .map((part) => part[0])
                          .join("")}
                      </span>
                      <div>
                        <p className="font-semibold text-brand-blue">{user.name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">{roleLabels[user.role]}</td>
                  <td className="px-5 py-4 text-muted-foreground">{user.organization}</td>
                  <td className="px-5 py-4">
                    <StatusBadge status={user.status} label={accountStatusLabels[user.status]} />
                  </td>
                  <td className="px-5 py-4 text-xs text-muted-foreground">{user.lastSeen}</td>
                  <td className="px-5 py-4">
                    <div className="flex justify-end gap-2">
                      {user.status === "INVITE" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => showToast(`Invitation renvoyée à ${user.email}.`)}
                        >
                          <Send />
                          Renvoyer
                        </Button>
                      ) : null}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => updateStatus(user.id, user.status)}
                      >
                        {user.status === "ACTIF" ? "Désactiver" : "Activer"}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          selectPreviewUser(user.id);
                          selectPreviewCompany(user.entityId ?? null);
                          navigate(getRoleHome(user.role));
                        }}
                      >
                        Prévisualiser
                        <ArrowRight />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredUsers.length ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">
              Aucun utilisateur ne correspond à ces filtres.
            </div>
          ) : null}
          {!afficherTout && nombreMasque > 0 ? (
            <div className="flex justify-center border-t px-5 py-4">
              <Button variant="outline" size="sm" onClick={() => setAfficherTout(true)}>
                Afficher les {nombreMasque} autre(s)
              </Button>
            </div>
          ) : null}
          {afficherTout && filteredUsers.length > NOMBRE_VISIBLE_PAR_DEFAUT ? (
            <div className="flex justify-center border-t px-5 py-4">
              <Button variant="ghost" size="sm" onClick={() => setAfficherTout(false)}>
                Réduire
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      <UserProvisioningModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

function CompaniesSection() {
  const navigate = useNavigate();
  const { companies, reports, selectPreviewCompany, selectPreviewUser, users } = usePrototype();
  const [query, setQuery] = useState("");
  const [selectedCompany, setSelectedCompany] = useState<PrototypeCompany | null>(null);
  const [afficherTout, setAfficherTout] = useState(false);

  const filteredCompanies = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");
    if (!normalizedQuery) return companies;
    return companies.filter((company) =>
      `${company.name} ${company.sector} ${company.country}`
        .toLocaleLowerCase("fr")
        .includes(normalizedQuery),
    );
  }, [companies, query]);

  const visibleCompanies = afficherTout
    ? filteredCompanies
    : filteredCompanies.slice(0, NOMBRE_VISIBLE_PAR_DEFAUT);
  const nombreCompaniesMasquees = filteredCompanies.length - NOMBRE_VISIBLE_PAR_DEFAUT;

  function openCompanySpace(company: PrototypeCompany) {
    const companyUser = users.find(
      (user) =>
        user.role === "ENTERPRISE" &&
        (user.entityId === company.id || user.organization === company.name),
    );
    selectPreviewUser(companyUser?.id ?? null);
    selectPreviewCompany(company.id);
    navigate("/prototype/company/dashboard");
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Entreprises"
        description="Consulter les organisations évaluées, leurs résultats principaux et leurs rapports associés."
      />

      <Card className="gap-0 py-0 shadow-none">
        <CardContent className="p-5">
          <label className="relative block max-w-lg">
            <span className="sr-only">Rechercher une entreprise</span>
            <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className={`${fieldClassName} pl-9`}
              placeholder="Rechercher par nom, secteur ou pays"
            />
          </label>
        </CardContent>
        <div className="overflow-x-auto border-t">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-semibold">Entreprise</th>
                <th className="px-5 py-3 font-semibold">Secteur</th>
                <th className="px-5 py-3 font-semibold">Score ESG</th>
                <th className="px-5 py-3 font-semibold">Qualité</th>
                <th className="px-5 py-3 font-semibold">Publication</th>
                <th className="px-5 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {visibleCompanies.map((company) => (
                <tr key={company.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4">
                    <p className="font-semibold text-brand-blue">{company.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {company.country} · Responsable : {company.contact || "À compléter"}
                    </p>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">{company.sector}</td>
                  <td className="px-5 py-4">
                    <span className="text-base font-semibold tabular-nums text-brand-blue">
                      {company.published ? `${company.score}/100` : "—"}
                    </span>
                  </td>
                  <td className="px-5 py-4">{company.quality}</td>
                  <td className="px-5 py-4">
                    <StatusBadge
                      status={company.published ? "PUBLIE" : "BROUILLON"}
                      label={company.published ? "Publiée" : "Non publiée"}
                    />
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelectedCompany(company)}
                      >
                        Voir le dossier
                      </Button>
                      <Button size="sm" onClick={() => openCompanySpace(company)}>
                        Prévisualiser
                        <ArrowRight />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!afficherTout && nombreCompaniesMasquees > 0 ? (
            <div className="flex justify-center border-t px-5 py-4">
              <Button variant="outline" size="sm" onClick={() => setAfficherTout(true)}>
                Afficher les {nombreCompaniesMasquees} autre(s)
              </Button>
            </div>
          ) : null}
          {afficherTout && filteredCompanies.length > NOMBRE_VISIBLE_PAR_DEFAUT ? (
            <div className="flex justify-center border-t px-5 py-4">
              <Button variant="ghost" size="sm" onClick={() => setAfficherTout(false)}>
                Réduire
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      <Modal
        open={Boolean(selectedCompany)}
        onClose={() => setSelectedCompany(null)}
        title={selectedCompany?.name ?? "Entreprise"}
        description={
          selectedCompany ? `${selectedCompany.sector} · ${selectedCompany.country}` : undefined
        }
        size="xl"
      >
        {selectedCompany ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Score ESG", selectedCompany.published ? `${selectedCompany.score}/100` : "—"],
                [
                  "Scope 1",
                  selectedCompany.published
                    ? `${numberFormatter.format(selectedCompany.scope1)} tCO₂e`
                    : "—",
                ],
                [
                  "Scope 2",
                  selectedCompany.published
                    ? `${numberFormatter.format(selectedCompany.scope2)} tCO₂e`
                    : "—",
                ],
                [
                  "Scope 3",
                  selectedCompany.published
                    ? `${numberFormatter.format(selectedCompany.scope3)} tCO₂e`
                    : "—",
                ],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border bg-slate-50 p-4">
                  <p className="text-xs font-medium text-muted-foreground">{label}</p>
                  <p className="mt-2 font-semibold tabular-nums text-brand-blue">{value}</p>
                </div>
              ))}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-brand-blue">Rapports associés</h3>
              <div className="mt-3 space-y-2">
                {reports
                  .filter((report) => report.companyId === selectedCompany.id)
                  .map((report) => (
                    <div key={report.id} className="flex items-center gap-3 rounded-xl border p-4">
                      <FileText className="size-5 text-brand-green" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-brand-blue">
                          {report.title}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">Exercice {report.year}</p>
                      </div>
                      <StatusBadge status={report.status} />
                    </div>
                  ))}
              </div>
            </div>
            <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => setSelectedCompany(null)}>
                Fermer
              </Button>
              <Button onClick={() => openCompanySpace(selectedCompany)}>
                Ouvrir l’espace Entreprise
                <ArrowRight />
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

function ReportsSection() {
  const navigate = useNavigate();
  const { reports, updateReport, users } = usePrototype();
  const [statusFilter, setStatusFilter] = useState("TOUS");
  const [selectedEvidence, setSelectedEvidence] = useState<PrototypeReport | null>(null);
  const [assigningReport, setAssigningReport] = useState<PrototypeReport | null>(null);

  const filteredReports = useMemo(
    () => reports.filter((report) => statusFilter === "TOUS" || report.status === statusFilter),
    [reports, statusFilter],
  );

  // Seule source valide pour l'affectation : des comptes Auditeur déjà enregistrés et actifs sur
  // la plateforme — jamais une identité saisie librement (règle appliquée à toute relation
  // acteur-à-acteur du système).
  const auditeursDisponibles = useMemo(
    () => users.filter((user) => user.role === "AUDITOR" && user.status === "ACTIF"),
    [users],
  );

  function assignReport(report: PrototypeReport, auditeur: PrototypeUser) {
    updateReport(
      report.id,
      { auditor: auditeur.name, status: "EN_AUDIT" },
      `${report.title} a été affecté à ${auditeur.name}.`,
    );
    setAssigningReport(null);
  }

  function validateReport(report: PrototypeReport) {
    updateReport(
      report.id,
      {
        status: "VALIDE",
        opinion: report.opinion ?? "Avis examiné : validation recommandée.",
        correctionNote: null,
      },
      `${report.title} est validé et prêt à être publié.`,
    );
  }

  function requestCorrection(report: PrototypeReport) {
    updateReport(
      report.id,
      {
        status: "CORRECTION_DEMANDEE",
        correctionNote: "Merci de compléter la justification et la preuve documentaire indiquées.",
      },
      `Une demande de correction est visible dans l’espace ${report.company}.`,
    );
  }

  function rejectReport(report: PrototypeReport) {
    updateReport(
      report.id,
      { status: "REJETE", correctionNote: "Rapport rejeté après décision administrative." },
      `${report.title} a été rejeté.`,
    );
  }

  function publishReport(report: PrototypeReport) {
    updateReport(
      report.id,
      { status: "PUBLIE", correctionNote: null },
      `${report.title} est maintenant visible par les acteurs autorisés.`,
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Rapports"
        description="Centraliser l’affectation, la décision administrative et la publication dans un seul dossier."
      />

      <Card className="gap-0 py-0 shadow-none">
        <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-blue">
              {filteredReports.length} rapport(s)
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Chaque action actualise immédiatement les autres espaces du prototype.
            </p>
          </div>
          <select
            className={`${fieldClassName} sm:w-56`}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            aria-label="Filtrer les rapports par statut"
          >
            <option value="TOUS">Tous les statuts</option>
            <option value="A_AFFECTER">À affecter</option>
            <option value="EN_AUDIT">En audit</option>
            <option value="CORRECTION_DEMANDEE">Correction demandée</option>
            <option value="CORRECTION_SOUMISE">Correction soumise</option>
            <option value="VALIDE">Validé</option>
            <option value="PUBLIE">Publié</option>
            <option value="REJETE">Rejeté</option>
          </select>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {filteredReports.map((report) => (
          <Card key={report.id} className="gap-0 py-0 shadow-none">
            <CardContent className="p-5 sm:p-6">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start">
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-green-light text-brand-green">
                  <FileText className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-base font-semibold text-brand-blue">{report.title}</h2>
                    <StatusBadge status={report.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {report.company} · Exercice {report.year} · Mis à jour {report.updatedAt}
                  </p>

                  <div className="mt-5 grid gap-4 sm:grid-cols-3">
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">Complétude</p>
                      <div className="mt-2">
                        <ProgressBar value={report.completeness} />
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">Auditeur</p>
                      <p className="mt-2 text-sm font-semibold text-brand-blue">
                        {report.auditor ?? "Non affecté"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-muted-foreground">Avis</p>
                      <p className="mt-2 line-clamp-2 text-sm text-brand-blue">
                        {report.opinion ?? "Aucun avis reçu"}
                      </p>
                    </div>
                  </div>

                  {report.correctionNote ? (
                    <div className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
                      <span className="font-semibold">Correction : </span>
                      {report.correctionNote}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap gap-2 xl:max-w-sm xl:justify-end">
                  <Button variant="outline" size="sm" onClick={() => setSelectedEvidence(report)}>
                    {report.completeness === 0 ? <FileText /> : <FileSearch />}
                    {report.completeness === 0 ? "Document" : "Preuve"}
                  </Button>

                  {report.status === "A_AFFECTER" || report.status === "SOUMIS" ? (
                    <Button size="sm" onClick={() => setAssigningReport(report)}>
                      <UserCheck />
                      Affecter
                    </Button>
                  ) : null}

                  {report.status === "EN_AUDIT" || report.status === "CORRECTION_SOUMISE" ? (
                    <>
                      <Button size="sm" onClick={() => validateReport(report)}>
                        <CheckCircle2 />
                        Valider
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => requestCorrection(report)}>
                        Demander correction
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => rejectReport(report)}>
                        Rejeter
                      </Button>
                    </>
                  ) : null}

                  {report.status === "VALIDE" ? (
                    <Button size="sm" onClick={() => publishReport(report)}>
                      <Send />
                      Publier
                    </Button>
                  ) : null}

                  {report.status === "CORRECTION_DEMANDEE" ? (
                    <Button size="sm" onClick={() => navigate("/prototype/company/reports")}>
                      Voir côté Entreprise
                      <ArrowRight />
                    </Button>
                  ) : null}

                  {report.status === "PUBLIE" ? (
                    <Button size="sm" onClick={() => navigate("/prototype/investor/companies")}>
                      Voir la publication
                      <ArrowRight />
                    </Button>
                  ) : null}

                  {report.status === "REJETE" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        updateReport(
                          report.id,
                          { status: "A_AFFECTER", auditor: null, correctionNote: null },
                          `${report.title} a été rouvert.`,
                        )
                      }
                    >
                      Réouvrir
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Modal
        open={Boolean(selectedEvidence)}
        onClose={() => setSelectedEvidence(null)}
        title={selectedEvidence?.completeness === 0 ? "Document soumis" : "Preuve documentaire"}
        description={selectedEvidence?.title}
        size="xl"
      >
        {selectedEvidence?.completeness === 0 ? (
          <div className="rounded-xl border bg-slate-50 px-6 py-12 text-center">
            <FileText className="mx-auto size-10 text-brand-green" />
            <p className="mt-4 font-semibold text-brand-blue">{selectedEvidence.title}</p>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              Le document est enregistré dans le parcours frontend. Son stockage, son extraction et
              les preuves page par page seront disponibles après connexion au backend documentaire.
            </p>
          </div>
        ) : selectedEvidence ? (
          <EvidencePreview
            company={selectedEvidence.company}
            page={selectedEvidence.evidencePage}
          />
        ) : null}
      </Modal>

      <Modal
        open={Boolean(assigningReport)}
        onClose={() => setAssigningReport(null)}
        title="Affecter un auditeur"
        description={assigningReport?.title}
      >
        {auditeursDisponibles.length ? (
          <div className="space-y-3">
            {auditeursDisponibles.map((auditeur) => (
              <button
                key={auditeur.id}
                type="button"
                className="flex w-full items-center gap-3 rounded-xl border p-4 text-left transition hover:border-brand-green/40 hover:bg-brand-green-light/30"
                onClick={() => assigningReport && assignReport(assigningReport, auditeur)}
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-green-light text-xs font-semibold text-brand-green">
                  {auditeur.name
                    .split(" ")
                    .slice(0, 2)
                    .map((part) => part[0])
                    .join("")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-brand-blue">
                    {auditeur.name}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                    {auditeur.email} · {auditeur.organization}
                  </span>
                </span>
                <ArrowRight className="size-4 text-muted-foreground" />
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Aucun compte Auditeur actif n’est enregistré sur la plateforme. Créez-en un depuis «
            Utilisateurs » avant d’affecter ce dossier.
          </p>
        )}
      </Modal>
    </div>
  );
}

function MethodologySection() {
  const { methodology, showToast, updateMethodology } = usePrototype();
  const [weights, setWeights] = useState(() => ({
    environmental: methodology.environmental,
    social: methodology.social,
    governance: methodology.governance,
  }));

  useEffect(() => {
    setWeights({
      environmental: methodology.environmental,
      social: methodology.social,
      governance: methodology.governance,
    });
  }, [methodology.environmental, methodology.governance, methodology.social]);

  const total = weights.environmental + weights.social + weights.governance;
  const validTotal = total === 100;

  function updateWeight(key: keyof typeof weights, value: number) {
    const normalizedValue = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
    setWeights((current) => ({ ...current, [key]: normalizedValue }));
  }

  function saveMethodology(status: Methodology["status"]) {
    if (status === "ACTIVE" && !validTotal) {
      showToast("Le total des pondérations doit être égal à 100 % avant activation.");
      return;
    }

    const version =
      methodology.status === "BROUILLON"
        ? methodology.version
        : nextMethodologyVersion(methodology.version);
    updateMethodology({ ...weights, version, status });
  }

  const weightFields: Array<{
    key: keyof typeof weights;
    label: string;
    description: string;
    tone: string;
  }> = [
    {
      key: "environmental",
      label: "Environnement",
      description: "Climat, énergie, ressources et biodiversité",
      tone: "bg-emerald-500",
    },
    {
      key: "social",
      label: "Social",
      description: "Capital humain, diversité et chaîne de valeur",
      tone: "bg-blue-500",
    },
    {
      key: "governance",
      label: "Gouvernance",
      description: "Éthique, conseil, transparence et contrôle",
      tone: "bg-violet-500",
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administration"
        title="Méthodologie ESG"
        description="Configurer une pondération explicite et versionnée pour le calcul des scores."
        action={
          <StatusBadge
            status={methodology.status}
            label={`${methodology.version} · ${methodology.status === "ACTIVE" ? "Active" : "Brouillon"}`}
          />
        }
      />

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <Card className="gap-0 py-0 shadow-none">
          <CardHeader className="border-b px-5 py-5 sm:px-6">
            <CardTitle className="text-base text-brand-blue">Pondérations des piliers</CardTitle>
            <p className="text-sm text-muted-foreground">
              Ajustez les poids. Une version ne peut être activée que si le total atteint 100 %.
            </p>
          </CardHeader>
          <CardContent className="space-y-7 p-5 sm:p-6">
            {weightFields.map((field) => (
              <div key={field.key}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <label
                      htmlFor={`weight-${field.key}`}
                      className="text-sm font-semibold text-brand-blue"
                    >
                      {field.label}
                    </label>
                    <p className="mt-1 text-xs text-muted-foreground">{field.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id={`weight-number-${field.key}`}
                      type="number"
                      min={0}
                      max={100}
                      value={weights[field.key]}
                      onChange={(event) => updateWeight(field.key, Number(event.target.value))}
                      className="h-10 w-20 rounded-lg border border-slate-300 px-3 text-right text-sm font-semibold tabular-nums outline-none focus:border-brand-green focus:ring-2 focus:ring-brand-green/15"
                      aria-label={`Poids ${field.label} en pourcentage`}
                    />
                    <span className="text-sm text-muted-foreground">%</span>
                  </div>
                </div>
                <input
                  id={`weight-${field.key}`}
                  type="range"
                  min={0}
                  max={100}
                  value={weights[field.key]}
                  onChange={(event) => updateWeight(field.key, Number(event.target.value))}
                  className="mt-4 h-2 w-full cursor-pointer accent-brand-green"
                  aria-label={`Ajuster le poids ${field.label}`}
                />
              </div>
            ))}

            <div className="flex flex-col gap-4 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-brand-blue">
                  Total : <span className="tabular-nums">{total} %</span>
                </p>
                <p className={`mt-1 text-xs ${validTotal ? "text-brand-green" : "text-amber-700"}`}>
                  {validTotal
                    ? "La répartition est prête à être activée."
                    : `Ajustez encore ${Math.abs(100 - total)} point(s) pour atteindre 100 %.`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => saveMethodology("BROUILLON")}>
                  Enregistrer le brouillon
                </Button>
                <Button onClick={() => saveMethodology("ACTIVE")} disabled={!validTotal}>
                  <ShieldCheck />
                  Activer cette version
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="gap-0 py-0 shadow-none">
            <CardHeader className="border-b px-5 py-5">
              <CardTitle className="text-base text-brand-blue">Aperçu du score</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5 p-5">
              <div className="grid place-items-center rounded-2xl bg-brand-green-light py-8">
                <Gauge className="size-7 text-brand-green" />
                <p className="mt-3 text-4xl font-semibold tabular-nums text-brand-blue">82</p>
                <p className="mt-1 text-xs text-muted-foreground">Score simulé / 100</p>
              </div>
              <div className="space-y-3">
                {weightFields.map((field) => (
                  <div key={field.key}>
                    <div className="mb-1.5 flex justify-between text-xs">
                      <span className="text-muted-foreground">{field.label}</span>
                      <span className="font-semibold tabular-nums text-brand-blue">
                        {weights[field.key]} %
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${field.tone}`}
                        style={{ width: `${weights[field.key]}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-950">
            <p className="font-semibold">Méthode transparente</p>
            <p className="mt-1 text-xs leading-5">
              La version et les poids actifs accompagneront chaque score affiché dans les autres
              espaces.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AdminPrototypePage({ section }: AdminPrototypePageProps) {
  switch (section) {
    case "users":
      return <UsersSection />;
    case "companies":
      return <CompaniesSection />;
    case "reports":
      return <ReportsSection />;
    case "methodology":
      return <MethodologySection />;
    default:
      return <DashboardSection />;
  }
}
