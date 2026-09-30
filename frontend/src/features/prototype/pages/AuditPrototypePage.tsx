import {
  AlertTriangle,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  FileSearch,
  FileText,
  MessageSquareText,
  Search,
  Send,
} from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import {
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
import type { PrototypeCompany, PrototypeReport } from "../types";

const numberFormatter = new Intl.NumberFormat("fr-FR");

interface AuditIndicator {
  code: string;
  label: string;
  value: string;
  source: string;
}

function indicatorsFor(company: PrototypeCompany): AuditIndicator[] {
  return [
    {
      code: "scope-1",
      label: "Émissions Scope 1",
      value: `${numberFormatter.format(company.scope1)} tCO₂e`,
      source: "Valeur publiée",
    },
    {
      code: "scope-2",
      label: "Émissions Scope 2",
      value: `${numberFormatter.format(company.scope2)} tCO₂e`,
      source: "Méthode market-based",
    },
    {
      code: "scope-3",
      label: "Émissions Scope 3",
      value: `${numberFormatter.format(company.scope3)} tCO₂e`,
      source: "Chaîne de valeur",
    },
    {
      code: "score-esg",
      label: "Score ESG calculé",
      value: `${company.score}/100`,
      source: "Méthodologie v2.4",
    },
  ];
}

function isActionable(report: PrototypeReport) {
  const finalOpinionSubmitted =
    report.status === "EN_AUDIT" && report.opinion?.startsWith("Avis final") === true;
  return (
    report.status === "CORRECTION_SOUMISE" ||
    (report.status === "EN_AUDIT" && !finalOpinionSubmitted)
  );
}

function hasSubmittedOpinion(report: PrototypeReport) {
  return report.opinion?.startsWith("Avis final") === true;
}

function AuditDashboard({
  activeReports,
  waitingReports,
  historyReports,
  onOpen,
}: {
  activeReports: PrototypeReport[];
  waitingReports: PrototypeReport[];
  historyReports: PrototypeReport[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Espace Auditeur"
        title="Contrôles à réaliser"
        description="Vérifiez les indicateurs, ouvrez leur preuve et transmettez un avis exploitable par l’administrateur."
        action={
          <Button asChild>
            <Link to="/prototype/audit/assignments">
              <ClipboardCheck />
              Voir mes dossiers
            </Link>
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Résumé des audits">
        <StatCard
          label="À contrôler"
          value={activeReports.length}
          hint="Dossiers disponibles"
          icon={<ClipboardCheck className="size-5" />}
        />
        <StatCard
          label="En attente de correction"
          value={waitingReports.length}
          hint="Action attendue de l’entreprise"
          icon={<Clock3 className="size-5" />}
          tone="amber"
        />
        <StatCard
          label="Avis transmis"
          value={historyReports.length}
          hint="Historique disponible"
          icon={<BookOpenCheck className="size-5" />}
          tone="blue"
        />
      </section>

      <Card className="shadow-none">
        <CardHeader>
          <CardTitle className="text-brand-blue">Dossiers prioritaires</CardTitle>
          <CardDescription>Les corrections soumises sont placées en tête de liste.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {activeReports.length > 0 ? (
            activeReports.map((report) => (
              <div
                key={report.id}
                className="flex flex-col gap-4 rounded-xl border p-4 sm:flex-row sm:items-center"
              >
                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-blue-50 text-brand-blue">
                  <FileText className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-brand-blue">{report.company}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {report.title} · {report.year}
                  </p>
                </div>
                <StatusBadge status={report.status} />
                <Button onClick={() => onOpen(report.id)}>
                  {report.status === "CORRECTION_SOUMISE" ? "Réexaminer" : "Contrôler"}
                </Button>
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-dashed p-8 text-center">
              <CheckCircle2 className="mx-auto size-8 text-brand-green" />
              <p className="mt-3 text-sm font-semibold text-brand-blue">
                Aucun contrôle disponible pour le moment
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Une nouvelle affectation administrative apparaîtra ici automatiquement.
              </p>
            </div>
          )}
          {waitingReports.map((report) => (
            <button
              type="button"
              key={report.id}
              className="flex w-full flex-col gap-3 rounded-xl bg-amber-50 p-4 text-left sm:flex-row sm:items-center"
              onClick={() => onOpen(report.id)}
            >
              <Clock3 className="size-5 shrink-0 text-amber-700" />
              <span className="flex-1 text-sm text-amber-950">
                <strong>{report.company}</strong> doit encore répondre à la correction demandée.
              </span>
              <span className="text-xs font-semibold text-amber-800">Consulter</span>
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function AssignmentsPage({
  reports,
  onOpen,
}: {
  reports: PrototypeReport[];
  onOpen: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filteredReports = reports.filter((report) =>
    `${report.company} ${report.title} ${report.year}`
      .toLocaleLowerCase("fr")
      .includes(query.toLocaleLowerCase("fr")),
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Missions affectées"
        title="Dossiers à auditer"
        description="L’auditeur accède uniquement aux rapports qui lui sont affectés."
      />

      <Card className="gap-4 py-4 shadow-none">
        <CardContent className="px-4">
          <label className="relative block max-w-md">
            <span className="sr-only">Rechercher un dossier</span>
            <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <input
              className={`${fieldClassName} pl-9`}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Entreprise, rapport ou exercice"
            />
          </label>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {filteredReports.map((report) => (
          <Card key={report.id} className="gap-4 py-5 shadow-none">
            <CardContent className="space-y-5 px-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand-green">
                    {report.company}
                  </p>
                  <h2 className="mt-1 font-semibold text-brand-blue">{report.title}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Exercice {report.year}</p>
                </div>
                <StatusBadge status={report.status} />
              </div>
              <ProgressBar value={report.completeness} label="Complétude documentaire" />
              {report.correctionNote ? (
                <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  {report.correctionNote}
                </p>
              ) : null}
              <Button className="w-full" onClick={() => onOpen(report.id)}>
                <FileSearch />
                {isActionable(report) ? "Ouvrir le contrôle" : "Consulter le dossier"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredReports.length === 0 ? (
        <Card className="py-12 text-center shadow-none">
          <CardContent>
            <p className="text-sm font-semibold text-brand-blue">Aucun dossier ne correspond.</p>
            <Button className="mt-4" variant="outline" onClick={() => setQuery("")}>
              Effacer la recherche
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function AuditHistory({
  reports,
  onOpen,
}: {
  reports: PrototypeReport[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Traçabilité"
        title="Historique de mes avis"
        description="Consultez les avis transmis et la décision finale associée à chaque rapport."
      />
      <Card className="overflow-hidden py-0 shadow-none">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-5 py-4 font-semibold">Entreprise</th>
                <th className="px-5 py-4 font-semibold">Rapport</th>
                <th className="px-5 py-4 font-semibold">Décision</th>
                <th className="px-5 py-4 font-semibold">Dernière mise à jour</th>
                <th className="px-5 py-4 text-right font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {reports.map((report) => (
                <tr key={report.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 font-semibold text-brand-blue">{report.company}</td>
                  <td className="px-5 py-4">
                    <p className="font-medium text-brand-blue">{report.title}</p>
                    <p className="text-xs text-muted-foreground">{report.year}</p>
                  </td>
                  <td className="px-5 py-4">
                    <StatusBadge
                      status={report.status}
                      label={hasSubmittedOpinion(report) ? "Avis transmis" : undefined}
                    />
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">{report.updatedAt}</td>
                  <td className="px-5 py-4 text-right">
                    <Button variant="outline" size="sm" onClick={() => onOpen(report.id)}>
                      Voir l’avis
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {reports.length === 0 ? (
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Aucun avis transmis pour le moment.
          </CardContent>
        ) : null}
      </Card>
    </div>
  );
}

export function AuditPrototypePage({ section }: { section: string }) {
  const { companies, previewUserId, reports, showToast, updateReport, users } = usePrototype();
  const auditorName =
    users.find((user) => user.id === previewUserId && user.role === "AUDITOR")?.name ??
    "Lucas Bernard";
  const assignedReports = reports.filter((report) => report.auditor === auditorName);
  const activeReports = assignedReports.filter(isActionable);
  const waitingReports = assignedReports.filter(
    (report) => report.status === "CORRECTION_DEMANDEE",
  );
  const historyReports = assignedReports.filter(
    (report) =>
      ["VALIDE", "PUBLIE", "REJETE"].includes(report.status) || hasSubmittedOpinion(report),
  );
  const visibleAssignments = assignedReports.filter(
    (report) =>
      !["VALIDE", "PUBLIE", "REJETE"].includes(report.status) && !hasSubmittedOpinion(report),
  );
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [evidencePage, setEvidencePage] = useState<number | null>(null);
  const [discrepancyOpen, setDiscrepancyOpen] = useState(false);
  const [opinionOpen, setOpinionOpen] = useState(false);
  const [confirmedIndicators, setConfirmedIndicators] = useState<string[]>([]);
  const selectedReport = reports.find((report) => report.id === selectedReportId) ?? null;
  const selectedCompany =
    companies.find((company) => company.id === selectedReport?.companyId) ?? null;
  const indicators = selectedCompany ? indicatorsFor(selectedCompany) : [];

  function confirmIndicator(code: string) {
    const key = `${selectedReportId}:${code}`;
    setConfirmedIndicators((current) => (current.includes(key) ? current : [...current, key]));
    showToast("Indicateur confirmé dans le contrôle en cours.");
  }

  function handleDiscrepancy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedReport) return;
    const formData = new FormData(event.currentTarget);
    const indicator = String(formData.get("indicator") ?? "");
    const note = String(formData.get("note") ?? "").trim();
    if (!note) return;
    updateReport(
      selectedReport.id,
      {
        opinion: `Écart signalé sur ${indicator}.`,
        correctionNote: note,
      },
      "Écart enregistré. Il est maintenant visible dans l’espace Administrateur.",
    );
    setDiscrepancyOpen(false);
  }

  function handleOpinion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedReport) return;
    const formData = new FormData(event.currentTarget);
    const recommendation = String(formData.get("recommendation") ?? "");
    const comment = String(formData.get("comment") ?? "").trim();
    if (!comment) return;
    updateReport(
      selectedReport.id,
      {
        status: "EN_AUDIT",
        opinion: `Avis final · ${recommendation} — ${comment}`,
        correctionNote: null,
      },
      "Avis d’audit transmis. Le rapport est visible dans la file de décision Administrateur.",
    );
    setOpinionOpen(false);
    setSelectedReportId(null);
  }

  let content: ReactNode;
  if (section === "assignments") {
    content = <AssignmentsPage reports={visibleAssignments} onOpen={setSelectedReportId} />;
  } else if (section === "history") {
    content = <AuditHistory reports={historyReports} onOpen={setSelectedReportId} />;
  } else {
    content = (
      <AuditDashboard
        activeReports={activeReports}
        waitingReports={waitingReports}
        historyReports={historyReports}
        onOpen={setSelectedReportId}
      />
    );
  }

  return (
    <>
      {content}

      <Modal
        open={Boolean(selectedReport)}
        onClose={() => setSelectedReportId(null)}
        title={selectedReport ? `Audit · ${selectedReport.company}` : "Dossier d’audit"}
        description={selectedReport?.title}
        size="xl"
      >
        {selectedReport && selectedCompany ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-xl border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Statut</p>
                <div className="mt-2">
                  <StatusBadge
                    status={selectedReport.status}
                    label={hasSubmittedOpinion(selectedReport) ? "Avis transmis" : undefined}
                  />
                </div>
              </div>
              <div className="rounded-xl border p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Exercice</p>
                <p className="mt-2 text-lg font-semibold text-brand-blue">{selectedReport.year}</p>
              </div>
              <div className="rounded-xl border p-4">
                <ProgressBar value={selectedReport.completeness} label="Complétude" />
              </div>
            </div>

            {selectedReport.status === "CORRECTION_DEMANDEE" ? (
              <div className="flex gap-3 rounded-xl bg-amber-50 p-4 text-sm text-amber-950">
                <Clock3 className="mt-0.5 size-5 shrink-0" />
                <div>
                  <p className="font-semibold">En attente de l’entreprise</p>
                  <p className="mt-1">{selectedReport.correctionNote}</p>
                </div>
              </div>
            ) : null}

            <section aria-labelledby="audit-indicators-title">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 id="audit-indicators-title" className="font-semibold text-brand-blue">
                    Indicateurs à contrôler
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Vérifiez la valeur, l’unité et la preuve avant de confirmer.
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {indicators.map((indicator) => {
                  const confirmationKey = `${selectedReport.id}:${indicator.code}`;
                  const confirmed = confirmedIndicators.includes(confirmationKey);
                  return (
                    <div
                      key={indicator.code}
                      className="grid gap-4 rounded-xl border p-4 lg:grid-cols-[1fr_auto_auto] lg:items-center"
                    >
                      <div>
                        <p className="font-semibold text-brand-blue">{indicator.label}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{indicator.source}</p>
                      </div>
                      <p className="font-semibold tabular-nums text-brand-blue">
                        {indicator.value}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEvidencePage(selectedReport.evidencePage)}
                        >
                          <FileSearch />
                          Preuve
                        </Button>
                        {isActionable(selectedReport) ? (
                          <Button
                            size="sm"
                            variant={confirmed ? "secondary" : "default"}
                            onClick={() => confirmIndicator(indicator.code)}
                            disabled={confirmed}
                          >
                            <Check />
                            {confirmed ? "Confirmé" : "Confirmer"}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {selectedReport.opinion ? (
              <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-950">
                <p className="font-semibold">Avis ou signalement enregistré</p>
                <p className="mt-1">{selectedReport.opinion}</p>
              </div>
            ) : null}

            <div className="flex flex-wrap justify-end gap-3 border-t pt-5">
              {isActionable(selectedReport) ? (
                <>
                  <Button variant="outline" onClick={() => setDiscrepancyOpen(true)}>
                    <AlertTriangle />
                    Signaler un écart
                  </Button>
                  <Button onClick={() => setOpinionOpen(true)}>
                    <Send />
                    Soumettre l’avis
                  </Button>
                </>
              ) : null}
              <Button variant="ghost" onClick={() => setSelectedReportId(null)}>
                Fermer
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={discrepancyOpen}
        onClose={() => setDiscrepancyOpen(false)}
        title="Signaler un écart"
        description="Le signalement sera immédiatement visible par l’administrateur."
        size="lg"
      >
        <form className="space-y-5" onSubmit={handleDiscrepancy}>
          <Field label="Indicateur concerné">
            <select className={fieldClassName} name="indicator" required>
              {indicators.map((indicator) => (
                <option key={indicator.code} value={indicator.label}>
                  {indicator.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Nature de l’écart">
            <select className={fieldClassName} name="type" defaultValue="source">
              <option value="source">Preuve insuffisante</option>
              <option value="value">Valeur incohérente</option>
              <option value="unit">Unité ou période ambiguë</option>
            </select>
          </Field>
          <Field label="Observation">
            <textarea
              className={`${fieldClassName} min-h-28`}
              name="note"
              placeholder="Décrivez précisément l’écart et la vérification attendue."
              required
            />
          </Field>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setDiscrepancyOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">
              <AlertTriangle />
              Enregistrer le signalement
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={opinionOpen}
        onClose={() => setOpinionOpen(false)}
        title="Soumettre l’avis d’audit"
        description="L’administrateur pourra ensuite valider, demander une correction ou rejeter le rapport."
        size="lg"
      >
        <form className="space-y-5" onSubmit={handleOpinion}>
          <Field label="Recommandation">
            <select className={fieldClassName} name="recommendation" defaultValue="Avis favorable">
              <option>Avis favorable</option>
              <option>Avis favorable avec réserves</option>
              <option>Correction recommandée</option>
            </select>
          </Field>
          <Field label="Commentaire de synthèse">
            <textarea
              className={`${fieldClassName} min-h-32`}
              name="comment"
              placeholder="Résumez les contrôles effectués et les réserves éventuelles."
              required
            />
          </Field>
          <div className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
            Le dépôt de cet avis place le rapport dans la file de décision de l’administrateur.
          </div>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setOpinionOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">
              <MessageSquareText />
              Transmettre l’avis
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={evidencePage !== null}
        onClose={() => setEvidencePage(null)}
        title="Preuve documentaire"
        description="Vérifiez la valeur dans son contexte documentaire."
        size="xl"
      >
        <EvidencePreview company={selectedCompany?.name ?? "Entreprise"} page={evidencePage ?? 1} />
      </Modal>
    </>
  );
}
