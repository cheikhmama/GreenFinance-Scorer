import {
  ArrowUpRight,
  BookOpen,
  Building2,
  Database,
  Download,
  FileUp,
  FlaskConical,
  GraduationCap,
  Plus,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import {
  EvidencePreview,
  Field,
  fieldClassName,
  Modal,
  PageHeader,
  StatCard,
  StatusBadge,
} from "../components/shared";
import { usePrototype } from "../PrototypeContext";
import type { PrototypeAnalysis } from "../types";

interface EvidenceSelection {
  company: string;
  page: number;
}

function ResearcherDashboard({
  researcherName,
  researcherEmail,
}: {
  researcherName: string;
  researcherEmail: string;
}) {
  const { analyses, affiliations, companies, showToast } = usePrototype();
  const researcherAnalyses = analyses.filter((analysis) => analysis.author === researcherName);
  const researcherAffiliations = affiliations.filter(
    (affiliation) => affiliation.researcherEmail === researcherEmail,
  );
  const publishedCompanies = companies.filter((company) => company.published);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Espace Chercheur"
        title="Explorez des données ESG traçables"
        description="Construisez des analyses reproductibles à partir de données publiées, qualifiées et reliées à leurs sources."
        action={
          <Button asChild>
            <Link to="/prototype/researcher/analyses">
              Créer une analyse
              <ArrowUpRight />
            </Link>
          </Button>
        }
      />

      <section
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Synthèse de l’espace chercheur"
      >
        <StatCard
          label="Entreprises accessibles"
          value={publishedCompanies.length}
          hint="Données publiées et sourcées"
          icon={<Database className="size-5" />}
        />
        <StatCard
          label="Analyses"
          value={researcherAnalyses.length}
          hint="Études personnelles et institutionnelles"
          icon={<FlaskConical className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Rattachements actifs"
          value={researcherAffiliations.filter((item) => item.status === "ACTIF").length}
          hint="Institutions partenaires"
          icon={<GraduationCap className="size-5" />}
          tone="violet"
        />
        <StatCard
          label="Invitations"
          value={researcherAffiliations.filter((item) => item.status === "INVITE").length}
          hint="Réponse attendue"
          icon={<BookOpen className="size-5" />}
          tone="amber"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold text-brand-blue">Analyses récentes</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Vos derniers travaux sauvegardés.
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to="/prototype/researcher/analyses">Toutes les analyses</Link>
              </Button>
            </div>
            <div className="mt-5 space-y-3">
              {researcherAnalyses.map((analysis) => (
                <article key={analysis.id} className="rounded-xl border p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-brand-blue">{analysis.title}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {analysis.period} · {analysis.companies.join(", ")}
                      </p>
                    </div>
                    <StatusBadge status={analysis.status} />
                  </div>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <h2 className="font-semibold text-brand-blue">Actions rapides</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Poursuivez votre travail de recherche.
            </p>
            <div className="mt-5 grid gap-3">
              <Button asChild variant="outline" className="justify-start">
                <Link to="/prototype/researcher/data">
                  <Database />
                  Explorer les données
                </Link>
              </Button>
              <Button asChild variant="outline" className="justify-start">
                <Link to="/prototype/researcher/affiliations">
                  <GraduationCap />
                  Gérer les rattachements
                </Link>
              </Button>
              <Button
                variant="outline"
                className="justify-start"
                onClick={() => showToast("Catalogue méthodologique téléchargé (simulation).")}
              >
                <Download />
                Télécharger la méthodologie
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ResearcherData() {
  const { companies, reports, showToast } = usePrototype();
  const [query, setQuery] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importCompany, setImportCompany] = useState(companies[0]?.name ?? "");
  const [sourceUrl, setSourceUrl] = useState("");
  const [period, setPeriod] = useState("2025");
  const accessibleCompanies = companies.filter(
    (company) =>
      company.published &&
      `${company.name} ${company.sector} ${company.country}`
        .toLocaleLowerCase("fr")
        .includes(query.toLocaleLowerCase("fr")),
  );

  function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    showToast(`Import officiel de ${importCompany} (${period}) enregistré pour validation.`);
    setImportOpen(false);
    setSourceUrl("");
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Catalogue de données"
        title="Données ESG accessibles"
        description="Chaque jeu de données indique sa période, sa qualité et la preuve documentaire qui permet de le reproduire."
        action={
          <Button onClick={() => setImportOpen(true)}>
            <FileUp />
            Importer un rapport officiel
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-full max-w-xl">
          <label
            className="block text-sm font-medium text-brand-blue"
            htmlFor="research-data-search"
          >
            Rechercher dans le catalogue
          </label>
          <input
            id="research-data-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Entreprise, secteur ou pays"
            className={`${fieldClassName} mt-2`}
          />
        </div>
        <Button
          variant="outline"
          onClick={() => showToast("Jeu de données exporté en CSV (simulation).")}
        >
          <Download />
          Exporter la sélection
        </Button>
      </div>

      {accessibleCompanies.length === 0 ? (
        <Card className="shadow-none">
          <CardContent className="py-10 text-center">
            <Database className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold text-brand-blue">Aucune donnée trouvée</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Effacez la recherche pour retrouver le catalogue complet.
            </p>
            <Button className="mt-4" variant="outline" onClick={() => setQuery("")}>
              Effacer la recherche
            </Button>
          </CardContent>
        </Card>
      ) : (
        <section className="grid gap-5 md:grid-cols-2" aria-label="Jeux de données accessibles">
          {accessibleCompanies.map((company) => {
            const report = reports.find(
              (item) => item.companyId === company.id && item.status === "PUBLIE",
            );
            return (
              <Card key={company.id} className="shadow-none">
                <CardContent className="space-y-5 px-5 sm:px-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="font-semibold text-brand-blue">{company.name}</h2>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {company.sector} · {company.country}
                      </p>
                    </div>
                    <StatusBadge
                      status={company.quality === "Élevée" ? "VALIDE" : "A_AFFECTER"}
                      label={company.quality}
                    />
                  </div>
                  <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                    {[
                      ["Score ESG", `${company.score}/100`],
                      ["Scope 1", `${Math.round(company.scope1 / 1000)} kt`],
                      ["Scope 2", `${Math.round(company.scope2 / 1000)} kt`],
                      ["Scope 3", `${Math.round(company.scope3 / 1000)} kt`],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg bg-slate-50 p-3">
                        <dt className="text-xs text-muted-foreground">{label}</dt>
                        <dd className="mt-1 font-semibold tabular-nums text-brand-blue">{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() =>
                        setEvidence({ company: company.name, page: report?.evidencePage ?? 1 })
                      }
                    >
                      Consulter la preuve
                    </Button>
                    <Button
                      className="flex-1"
                      onClick={() => showToast(`${company.name} ajouté à la prochaine analyse.`)}
                    >
                      Ajouter à une analyse
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </section>
      )}

      <Modal
        open={importOpen}
        title="Importer un rapport officiel"
        description="Le prototype simule une demande d’import soumise à validation administrative."
        onClose={() => setImportOpen(false)}
      >
        <form className="space-y-5" onSubmit={submitImport}>
          <Field label="Entreprise">
            <select
              className={fieldClassName}
              value={importCompany}
              onChange={(event) => setImportCompany(event.target.value)}
              required
            >
              {companies.map((company) => (
                <option key={company.id} value={company.name}>
                  {company.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Période du rapport">
            <input
              className={fieldClassName}
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              required
            />
          </Field>
          <Field
            label="URL de la source officielle"
            hint="Une source publique et vérifiable est requise."
          >
            <input
              className={fieldClassName}
              type="url"
              placeholder="https://entreprise.example/rapport.pdf"
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              required
            />
          </Field>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setImportOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">Soumettre l’import</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(evidence)}
        title={`Preuve — ${evidence?.company ?? "entreprise"}`}
        onClose={() => setEvidence(null)}
        size="xl"
      >
        {evidence ? <EvidencePreview company={evidence.company} page={evidence.page} /> : null}
      </Modal>
    </div>
  );
}

function ResearcherAnalyses({ researcherName }: { researcherName: string }) {
  const { analyses, companies, createAnalysis, showToast } = usePrototype();
  const researcherAnalyses = analyses.filter((analysis) => analysis.author === researcherName);
  const publishedCompanies = companies.filter((company) => company.published);
  const [modalOpen, setModalOpen] = useState(false);
  const [detail, setDetail] = useState<PrototypeAnalysis | null>(null);
  const [title, setTitle] = useState("");
  const [period, setPeriod] = useState("2023–2025");
  const [companyName, setCompanyName] = useState(publishedCompanies[0]?.name ?? "");
  const [owner, setOwner] = useState<PrototypeAnalysis["owner"]>("Personnel");

  function submitAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAnalysis({
      title,
      author: researcherName,
      owner,
      companies: [companyName],
      period,
      status: "BROUILLON",
    });
    setTitle("");
    setModalOpen(false);
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Espace de travail"
        title="Analyses sauvegardées"
        description="Préparez des études personnelles ou institutionnelles et exportez leurs résultats simulés."
        action={
          <Button onClick={() => setModalOpen(true)}>
            <Plus />
            Nouvelle analyse
          </Button>
        }
      />

      <section className="grid gap-5 lg:grid-cols-2" aria-label="Analyses du chercheur">
        {researcherAnalyses.map((analysis) => (
          <Card key={analysis.id} className="shadow-none">
            <CardContent className="space-y-5 px-5 sm:px-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-brand-green">
                    {analysis.owner}
                  </p>
                  <h2 className="mt-1 font-semibold text-brand-blue">{analysis.title}</h2>
                </div>
                <StatusBadge status={analysis.status} />
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs text-muted-foreground">Période</dt>
                  <dd className="mt-1 font-medium text-brand-blue">{analysis.period}</dd>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <dt className="text-xs text-muted-foreground">Entreprises</dt>
                  <dd className="mt-1 font-medium text-brand-blue">{analysis.companies.length}</dd>
                </div>
              </dl>
              <p className="text-sm text-muted-foreground">Mise à jour : {analysis.updatedAt}</p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button variant="outline" className="flex-1" onClick={() => setDetail(analysis)}>
                  Ouvrir
                </Button>
                <Button
                  className="flex-1"
                  onClick={() => showToast(`Analyse « ${analysis.title} » exportée (simulation).`)}
                >
                  <Download />
                  Exporter
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      <Modal
        open={modalOpen}
        title="Créer une analyse"
        description="Définissez un périmètre initial ; il pourra évoluer après l’intégration backend."
        onClose={() => setModalOpen(false)}
      >
        <form className="space-y-5" onSubmit={submitAnalysis}>
          <Field label="Titre de l’analyse">
            <input
              className={fieldClassName}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </Field>
          <Field label="Entreprise de départ">
            <select
              className={fieldClassName}
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              required
            >
              {publishedCompanies.map((company) => (
                <option key={company.id} value={company.name}>
                  {company.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Période">
            <input
              className={fieldClassName}
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              required
            />
          </Field>
          <Field label="Propriétaire">
            <select
              className={fieldClassName}
              value={owner}
              onChange={(event) => setOwner(event.target.value as PrototypeAnalysis["owner"])}
            >
              <option value="Personnel">Personnel</option>
              <option value="Institut Climat & Finance">Institut Climat & Finance</option>
            </select>
          </Field>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">Créer l’analyse</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(detail)}
        title={detail?.title ?? "Analyse"}
        description="Aperçu simulé de l’analyse sélectionnée."
        onClose={() => setDetail(null)}
        size="lg"
      >
        {detail ? (
          <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                label="Entreprises"
                value={detail.companies.length}
                hint={detail.companies.join(", ")}
                icon={<Building2 className="size-5" />}
              />
              <StatCard
                label="Période"
                value={detail.period}
                hint="Périmètre temporel"
                icon={<BookOpen className="size-5" />}
                tone="blue"
              />
              <StatCard
                label="Statut"
                value={detail.status.replaceAll("_", " ")}
                hint={detail.owner}
                icon={<FlaskConical className="size-5" />}
                tone="violet"
              />
            </div>
            <div className="rounded-xl bg-brand-green-light p-5 text-sm leading-6 text-brand-blue">
              L’analyse combine les scores ESG publiés, les émissions Scope 1–3 et les indicateurs
              de qualité des données.
            </div>
            <div className="flex justify-end">
              <Button
                onClick={() => showToast(`Analyse « ${detail.title} » exportée (simulation).`)}
              >
                <Download />
                Exporter les résultats
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

function ResearcherAffiliations({ researcherEmail }: { researcherEmail: string }) {
  const { affiliations, updateAffiliation, showToast } = usePrototype();
  const researcherAffiliations = affiliations.filter(
    (affiliation) => affiliation.researcherEmail === researcherEmail,
  );

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Collaborations"
        title="Rattachements institutionnels"
        description="Acceptez les invitations reçues et visualisez les institutions pour lesquelles vous pouvez produire des analyses."
      />

      <section className="grid gap-5 lg:grid-cols-2" aria-label="Rattachements du chercheur">
        {researcherAffiliations.map((affiliation) => (
          <Card key={affiliation.id} className="shadow-none">
            <CardContent className="space-y-5 px-5 sm:px-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-11 place-items-center rounded-xl bg-violet-50 text-violet-700">
                    <GraduationCap className="size-5" />
                  </span>
                  <div>
                    <h2 className="font-semibold text-brand-blue">{affiliation.institution}</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {affiliation.primary
                        ? "Rattachement principal"
                        : "Collaboration institutionnelle"}
                    </p>
                  </div>
                </div>
                <StatusBadge status={affiliation.status} />
              </div>

              {affiliation.status === "INVITE" ? (
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button
                    className="flex-1"
                    onClick={() => updateAffiliation(affiliation.id, "ACTIF")}
                  >
                    Accepter
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => updateAffiliation(affiliation.id, "SUSPENDU")}
                  >
                    Décliner
                  </Button>
                </div>
              ) : null}
              {affiliation.status === "ACTIF" ? (
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() =>
                    showToast(`Export institutionnel préparé pour ${affiliation.institution}.`)
                  }
                >
                  <Download />
                  Préparer un export institutionnel
                </Button>
              ) : null}
              {affiliation.status === "SUSPENDU" ? (
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() =>
                    showToast(`Demande de réactivation envoyée à ${affiliation.institution}.`)
                  }
                >
                  Demander la réactivation
                </Button>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}

export function ResearcherPrototypePage({ section }: { section: string }) {
  const { previewUserId, users } = usePrototype();
  const researcher = users.find((user) => user.id === previewUserId && user.role === "CHERCHEUR");
  const researcherName = researcher?.name ?? "Dr. Noah Kim";
  const researcherEmail = researcher?.email ?? "noah@university.test";

  switch (section) {
    case "data":
      return <ResearcherData />;
    case "analyses":
      return <ResearcherAnalyses researcherName={researcherName} />;
    case "affiliations":
      return <ResearcherAffiliations researcherEmail={researcherEmail} />;
    default:
      return (
        <ResearcherDashboard researcherName={researcherName} researcherEmail={researcherEmail} />
      );
  }
}
