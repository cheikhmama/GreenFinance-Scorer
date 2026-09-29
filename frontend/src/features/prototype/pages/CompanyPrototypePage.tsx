import {
  Building2,
  CheckCircle2,
  Cloud,
  FileCheck2,
  FilePlus2,
  FileText,
  Gauge,
  Leaf,
  PencilLine,
  Search,
  Upload,
} from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import {
  EvidenceCard,
  EvidencePreview,
  Field,
  fieldClassName,
  Modal,
  PageHeader,
  ProgressBar,
  StatCard,
  StatusBadge,
} from "../components/shared";
import { usePrototype } from "../PrototypeContext";
import type { PrototypeReport } from "../types";

const numberFormatter = new Intl.NumberFormat("fr-FR");

function formatEmissions(value: number) {
  return `${numberFormatter.format(value)} tCO₂e`;
}

function CompanyDashboard({
  company,
  reports,
  onDeposit,
  onOpenReport,
  onCorrect,
}: {
  company: ReturnType<typeof usePrototype>["companies"][number];
  reports: PrototypeReport[];
  onDeposit: () => void;
  onOpenReport: (id: string) => void;
  onCorrect: (id: string) => void;
}) {
  const correctionReports = reports.filter((report) => report.status === "CORRECTION_DEMANDEE");
  const latestReport = reports[0];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={`Espace privé · ${company.name}`}
        title="Pilotez votre reporting ESG"
        description="Retrouvez vos rapports, vos résultats carbone et les demandes nécessitant une réponse."
        action={
          <Button onClick={onDeposit}>
            <FilePlus2 />
            Déposer un rapport
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicateurs clés">
        <StatCard
          label="Score ESG"
          value={company.published ? `${company.score}/100` : "—"}
          hint={company.published ? "Dernière version publiée" : "Aucun score publié"}
          icon={<Gauge className="size-5" />}
        />
        <StatCard
          label="Scope 1"
          value={company.published ? numberFormatter.format(company.scope1) : "—"}
          hint={company.published ? "tCO₂e · exercice 2025" : "En attente de validation"}
          icon={<Cloud className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Rapports"
          value={reports.length}
          hint={latestReport ? `Dernier : ${latestReport.year}` : "Aucun rapport"}
          icon={<FileText className="size-5" />}
          tone="violet"
        />
        <StatCard
          label="Actions requises"
          value={correctionReports.length}
          hint="Demandes de correction"
          icon={<PencilLine className="size-5" />}
          tone="amber"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-brand-blue">Rapports récents</CardTitle>
            <CardDescription>
              Le statut métier et l’action utile pour chaque version.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {reports.length > 0 ? (
              reports.slice(0, 3).map((report) => (
                <div
                  key={report.id}
                  className="flex flex-col gap-4 rounded-xl border p-4 sm:flex-row sm:items-center"
                >
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-green-light text-brand-green">
                    <FileText className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-brand-blue">{report.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Exercice {report.year} · Mis à jour {report.updatedAt}
                    </p>
                  </div>
                  <StatusBadge status={report.status} />
                  {report.status === "CORRECTION_DEMANDEE" ? (
                    <Button size="sm" onClick={() => onCorrect(report.id)}>
                      Corriger
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => onOpenReport(report.id)}>
                      Ouvrir
                    </Button>
                  )}
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed p-8 text-center">
                <FilePlus2 className="mx-auto size-8 text-muted-foreground" />
                <p className="mt-3 text-sm font-semibold text-brand-blue">Aucun rapport déposé</p>
                <Button className="mt-4" size="sm" onClick={onDeposit}>
                  Déposer le premier rapport
                </Button>
              </div>
            )}
            <Button asChild variant="outline" className="w-full">
              <Link to="/prototype/company/reports">Voir tous les rapports</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-brand-blue">Performance publiée</CardTitle>
            <CardDescription>Décomposition du score de référence.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <ProgressBar value={company.environmental} label="Environnement" />
            <ProgressBar value={company.social} label="Social" />
            <ProgressBar value={company.governance} label="Gouvernance" />
            <Button asChild variant="outline" className="w-full">
              <Link to="/prototype/company/results">Consulter les résultats et preuves</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CompanyReports({
  reports,
  onDeposit,
  onOpenReport,
  onCorrect,
}: {
  reports: PrototypeReport[];
  onDeposit: () => void;
  onOpenReport: (id: string) => void;
  onCorrect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filteredReports = reports.filter((report) =>
    `${report.title} ${report.year}`
      .toLocaleLowerCase("fr")
      .includes(query.toLocaleLowerCase("fr")),
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Documents officiels"
        title="Mes rapports"
        description="Déposez une nouvelle version, consultez son statut et répondez aux demandes de correction."
        action={
          <Button onClick={onDeposit}>
            <Upload />
            Déposer un rapport
          </Button>
        }
      />

      <Card className="gap-4 py-4 shadow-none">
        <CardContent className="px-4">
          <label className="relative block max-w-md">
            <span className="sr-only">Rechercher un rapport</span>
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              className={`${fieldClassName} pl-9`}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher par titre ou exercice"
            />
          </label>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {filteredReports.map((report) => (
          <Card key={report.id} className="gap-4 py-5 shadow-none">
            <CardContent className="flex flex-col gap-5 px-5 lg:flex-row lg:items-center">
              <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand-green-light text-brand-green">
                <FileText className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-brand-blue">{report.title}</h2>
                  <StatusBadge status={report.status} />
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  Exercice {report.year} · Complétude {report.completeness}% · {report.updatedAt}
                </p>
                {report.correctionNote ? (
                  <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    {report.correctionNote}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => onOpenReport(report.id)}>
                  Consulter
                </Button>
                {report.status === "CORRECTION_DEMANDEE" ? (
                  <Button onClick={() => onCorrect(report.id)}>Soumettre la correction</Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}
        {filteredReports.length === 0 ? (
          <Card className="py-12 text-center shadow-none">
            <CardContent>
              <p className="text-sm font-semibold text-brand-blue">Aucun rapport ne correspond.</p>
              <Button className="mt-4" variant="outline" onClick={() => setQuery("")}>
                Effacer la recherche
              </Button>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function CompanyResults({
  company,
  evidencePage,
  onOpenEvidence,
  onExport,
}: {
  company: ReturnType<typeof usePrototype>["companies"][number];
  evidencePage: number;
  onOpenEvidence: (page: number) => void;
  onExport: () => void;
}) {
  if (!company.published) {
    return (
      <div className="space-y-8">
        <PageHeader
          eyebrow="Résultats ESG"
          title="Aucun résultat publié"
          description="Les scores et émissions apparaîtront ici après l’audit, la validation et la publication du premier rapport."
        />
        <Card className="py-12 text-center shadow-none">
          <CardContent>
            <Gauge className="mx-auto size-10 text-slate-300" />
            <p className="mt-4 font-semibold text-brand-blue">Rapport en attente de revue</p>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              Les données simulées ne sont pas présentées comme validées avant la fin du workflow
              administratif.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const carbonRows = [
    { label: "Scope 1", value: company.scope1, method: "Émissions directes" },
    { label: "Scope 2", value: company.scope2, method: "Market-based" },
    { label: "Scope 3", value: company.scope3, method: "Chaîne de valeur" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Résultats validés"
        title="Résultats ESG et carbone"
        description="Chaque valeur est présentée avec sa période, son unité et un accès direct à sa preuve."
        action={
          <Button variant="outline" onClick={onExport}>
            <FileCheck2 />
            Exporter la synthèse
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Scores ESG">
        <StatCard
          label="Score global"
          value={`${company.score}/100`}
          hint="Méthodologie de référence v2.4"
          icon={<Gauge className="size-5" />}
        />
        <StatCard
          label="Environnement"
          value={company.environmental}
          hint="40 % du score"
          icon={<Leaf className="size-5" />}
        />
        <StatCard
          label="Social"
          value={company.social}
          hint="30 % du score"
          icon={<Building2 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Gouvernance"
          value={company.governance}
          hint="30 % du score"
          icon={<CheckCircle2 className="size-5" />}
          tone="violet"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-brand-blue">Empreinte carbone publiée</CardTitle>
            <CardDescription>Exercice 2025 · tonnes équivalent CO₂</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {carbonRows.map((row) => (
              <div
                key={row.label}
                className="grid gap-3 rounded-xl border p-4 sm:grid-cols-[1fr_auto_auto] sm:items-center"
              >
                <div>
                  <p className="font-semibold text-brand-blue">{row.label}</p>
                  <p className="text-xs text-muted-foreground">{row.method} · donnée publiée</p>
                </div>
                <p className="font-semibold tabular-nums text-brand-blue">
                  {formatEmissions(row.value)}
                </p>
                <Button variant="outline" size="sm" onClick={() => onOpenEvidence(evidencePage)}>
                  Voir la preuve
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardHeader>
            <CardTitle className="text-brand-blue">Traçabilité</CardTitle>
            <CardDescription>La preuve reste accessible sans quitter le contexte.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <EvidenceCard onOpen={() => onOpenEvidence(evidencePage)} />
            <dl className="grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4 text-sm">
              <dt className="text-muted-foreground">Qualité</dt>
              <dd className="text-right font-semibold text-brand-green">{company.quality}</dd>
              <dt className="text-muted-foreground">Période</dt>
              <dd className="text-right font-medium">2025</dd>
              <dt className="text-muted-foreground">Nature</dt>
              <dd className="text-right font-medium">Publiée</dd>
              <dt className="text-muted-foreground">Statut</dt>
              <dd className="text-right font-medium">Auditée</dd>
            </dl>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CompanyProfile({
  company,
  onSave,
}: {
  company: ReturnType<typeof usePrototype>["companies"][number];
  onSave: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Organisation"
        title="Profil de l’entreprise"
        description="Ces informations identifient le périmètre auquel les rapports et résultats sont rattachés."
      />
      <Card className="max-w-4xl shadow-none">
        <CardHeader>
          <CardTitle className="text-brand-blue">Informations générales</CardTitle>
          <CardDescription>Les modifications sont simulées dans cette maquette.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-5 sm:grid-cols-2" onSubmit={onSave}>
            <Field label="Raison sociale">
              <input className={fieldClassName} name="name" defaultValue={company.name} required />
            </Field>
            <Field label="Secteur">
              <input
                className={fieldClassName}
                name="sector"
                defaultValue={company.sector}
                required
              />
            </Field>
            <Field label="Pays">
              <input
                className={fieldClassName}
                name="country"
                defaultValue={company.country}
                required
              />
            </Field>
            <Field label="Responsable ESG">
              <input
                className={fieldClassName}
                name="contact"
                defaultValue={company.contact}
                required
              />
            </Field>
            <Field label="Site officiel">
              <input
                className={fieldClassName}
                name="website"
                type="url"
                defaultValue={company.website}
                required
              />
            </Field>
            <Field label="Exercice de reporting">
              <select className={fieldClassName} name="fiscalYear" defaultValue="calendar">
                <option value="calendar">Année civile</option>
                <option value="custom">Exercice décalé</option>
              </select>
            </Field>
            <Field label="Description">
              <textarea
                className={`${fieldClassName} min-h-28`}
                name="description"
                defaultValue={`${company.name} opère dans le secteur ${company.sector.toLocaleLowerCase("fr")} et publie ses informations ESG sur le périmètre déclaré.`}
              />
            </Field>
            <div className="flex items-end justify-end sm:col-span-2">
              <Button type="submit">
                <CheckCircle2 />
                Enregistrer les modifications
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export function CompanyPrototypePage({ section }: { section: string }) {
  const {
    companies,
    createReport,
    previewCompanyId,
    previewUserId,
    reports,
    showToast,
    updateReport,
    users,
  } = usePrototype();
  const previewUser = users.find((user) => user.id === previewUserId && user.role === "ENTERPRISE");
  const company =
    companies.find((item) => item.id === previewCompanyId) ??
    companies.find((item) => item.id === previewUser?.entityId) ??
    companies.find((item) => item.name === previewUser?.organization) ??
    companies.find((item) => item.id === "cmp-microsoft") ??
    companies[0];
  const companyReports = reports.filter((report) => report.companyId === company?.id);
  const [depositOpen, setDepositOpen] = useState(false);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [correctionReportId, setCorrectionReportId] = useState<string | null>(null);
  const [evidencePage, setEvidencePage] = useState<number | null>(null);

  if (!company) {
    return (
      <Card className="py-12 text-center shadow-none">
        <CardContent>
          <p className="font-semibold text-brand-blue">Aucune entreprise associée à ce compte.</p>
        </CardContent>
      </Card>
    );
  }

  const selectedReport = reports.find((report) => report.id === selectedReportId) ?? null;
  const correctionReport = reports.find((report) => report.id === correctionReportId) ?? null;
  const defaultEvidencePage = companyReports[0]?.evidencePage ?? 1;

  function handleDeposit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const title = String(formData.get("title") ?? "").trim();
    const year = Number(formData.get("year"));
    if (!title || !Number.isInteger(year)) return;
    const report = createReport({ companyId: company.id, company: company.name, title, year });
    setDepositOpen(false);
    setSelectedReportId(report.id);
  }

  function handleCorrection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!correctionReport) return;
    const formData = new FormData(event.currentTarget);
    const response = String(formData.get("response") ?? "").trim();
    if (!response) return;
    updateReport(
      correctionReport.id,
      {
        status: "CORRECTION_SOUMISE",
        correctionNote: `Réponse de l’entreprise : ${response}`,
      },
      "Correction soumise. Elle est maintenant visible par l’administrateur et l’auditeur.",
    );
    setCorrectionReportId(null);
  }

  let content: ReactNode;
  if (section === "reports") {
    content = (
      <CompanyReports
        reports={companyReports}
        onDeposit={() => setDepositOpen(true)}
        onOpenReport={setSelectedReportId}
        onCorrect={setCorrectionReportId}
      />
    );
  } else if (section === "results") {
    content = (
      <CompanyResults
        company={company}
        evidencePage={defaultEvidencePage}
        onOpenEvidence={setEvidencePage}
        onExport={() => showToast("Synthèse ESG générée dans le prototype.")}
      />
    );
  } else if (section === "profile") {
    content = (
      <CompanyProfile
        company={company}
        onSave={(event) => {
          event.preventDefault();
          showToast("Profil de l’entreprise mis à jour dans le prototype.");
        }}
      />
    );
  } else {
    content = (
      <CompanyDashboard
        company={company}
        reports={companyReports}
        onDeposit={() => setDepositOpen(true)}
        onOpenReport={setSelectedReportId}
        onCorrect={setCorrectionReportId}
      />
    );
  }

  return (
    <>
      {content}

      <Modal
        open={depositOpen}
        onClose={() => setDepositOpen(false)}
        title="Déposer un rapport"
        description="Le dépôt simulé sera immédiatement visible dans l’espace Administrateur."
        size="lg"
      >
        <form className="space-y-5" onSubmit={handleDeposit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Titre du rapport">
              <input
                className={fieldClassName}
                name="title"
                defaultValue="Rapport de durabilité 2026"
                required
              />
            </Field>
            <Field label="Exercice">
              <input
                className={fieldClassName}
                name="year"
                type="number"
                min="2000"
                max="2100"
                defaultValue="2026"
                required
              />
            </Field>
          </div>
          <Field
            label="Rapport PDF"
            hint="PDF officiel · 50 Mo maximum dans la future version connectée"
          >
            <input
              className={fieldClassName}
              name="report"
              type="file"
              accept="application/pdf"
              required
            />
          </Field>
          <Field label="Preuve complémentaire" hint="Facultatif">
            <input
              className={fieldClassName}
              name="evidence"
              type="file"
              accept="application/pdf"
            />
          </Field>
          <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
            Après confirmation, une version métier du rapport est créée avec le statut « À affecter
            ».
          </div>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setDepositOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">
              <Upload />
              Soumettre le rapport
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(selectedReport)}
        onClose={() => setSelectedReportId(null)}
        title={selectedReport?.title ?? "Détail du rapport"}
        description={
          selectedReport ? `Exercice ${selectedReport.year} · ${selectedReport.company}` : undefined
        }
        size="lg"
      >
        {selectedReport ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Statut actuel
                </p>
                <div className="mt-2">
                  <StatusBadge status={selectedReport.status} />
                </div>
              </div>
              <div className="min-w-52">
                <ProgressBar value={selectedReport.completeness} label="Complétude" />
              </div>
            </div>
            {selectedReport.correctionNote ? (
              <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
                <p className="font-semibold">Demande ou réponse de correction</p>
                <p className="mt-1">{selectedReport.correctionNote}</p>
              </div>
            ) : null}
            <EvidenceCard onOpen={() => setEvidencePage(selectedReport.evidencePage)} />
            <div className="flex flex-wrap justify-end gap-3">
              {selectedReport.status === "CORRECTION_DEMANDEE" ? (
                <Button
                  onClick={() => {
                    setSelectedReportId(null);
                    setCorrectionReportId(selectedReport.id);
                  }}
                >
                  <PencilLine />
                  Répondre à la demande
                </Button>
              ) : null}
              <Button variant="outline" onClick={() => setSelectedReportId(null)}>
                Fermer
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(correctionReport)}
        onClose={() => setCorrectionReportId(null)}
        title="Soumettre une correction"
        description={correctionReport?.title}
        size="lg"
      >
        {correctionReport ? (
          <form className="space-y-5" onSubmit={handleCorrection}>
            <div className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-semibold">Demande reçue</p>
              <p className="mt-1">{correctionReport.correctionNote}</p>
            </div>
            <Field label="Réponse de l’entreprise">
              <textarea
                className={`${fieldClassName} min-h-28`}
                name="response"
                placeholder="Expliquez la correction apportée et la preuve jointe."
                required
              />
            </Field>
            <Field label="Nouvelle preuve PDF">
              <input
                className={fieldClassName}
                name="proof"
                type="file"
                accept="application/pdf"
                required
              />
            </Field>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => setCorrectionReportId(null)}>
                Annuler
              </Button>
              <Button type="submit">
                <CheckCircle2 />
                Soumettre la correction
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <Modal
        open={evidencePage !== null}
        onClose={() => setEvidencePage(null)}
        title="Preuve documentaire"
        description="Passage source associé à la valeur sélectionnée."
        size="xl"
      >
        <EvidencePreview company={company.name} page={evidencePage ?? 1} />
      </Modal>
    </>
  );
}
