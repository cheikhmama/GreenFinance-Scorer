import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  Download,
  FileSearch,
  MailPlus,
  RefreshCw,
  Search,
  UserCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
import {
  EvidencePreview,
  fieldClassName,
  Modal,
  PageHeader,
  ProgressBar,
  StatCard,
  StatusBadge,
} from "../components/shared";
import { usePrototype } from "../PrototypeContext";
import type { PrototypeAnalysis } from "../types";

const EXPORT_QUOTA = 25;
const NOMBRE_VISIBLE_PAR_DEFAUT = 5;

interface EvidenceSelection {
  company: string;
  page: number;
}

function InstitutionDashboard({
  exportsUsed,
  onExport,
  institutionName,
}: {
  exportsUsed: number;
  onExport: (title: string) => void;
  institutionName: string;
}) {
  const { affiliations, analyses, companies } = usePrototype();
  const institutionAffiliations = affiliations.filter(
    (affiliation) => affiliation.institution === institutionName,
  );
  const institutionAnalyses = analyses.filter((analysis) => analysis.owner === institutionName);
  const publishedCompanies = companies.filter((company) => company.published);
  const quotaPercentage = Math.round((exportsUsed / EXPORT_QUOTA) * 100);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Espace Institution"
        title="Supervisez vos recherches ESG"
        description="Suivez les chercheurs rattachés, les analyses produites pour votre institution et les données publiées accessibles."
        action={
          <Button asChild>
            <Link to="/prototype/institution/researchers">
              Gérer les chercheurs
              <ArrowUpRight />
            </Link>
          </Button>
        }
      />

      <section
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Synthèse institutionnelle"
      >
        <StatCard
          label="Chercheurs actifs"
          value={institutionAffiliations.filter((item) => item.status === "ACTIF").length}
          hint={`${institutionAffiliations.length} rattachement(s) au total`}
          icon={<UserCheck className="size-5" />}
        />
        <StatCard
          label="Invitations en attente"
          value={institutionAffiliations.filter((item) => item.status === "INVITE").length}
          hint="Réponse du chercheur attendue"
          icon={<MailPlus className="size-5" />}
          tone="amber"
        />
        <StatCard
          label="Analyses institutionnelles"
          value={institutionAnalyses.length}
          hint="Travaux partagés avec l’institution"
          icon={<BarChart3 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Entreprises accessibles"
          value={publishedCompanies.length}
          hint="Données validées et publiées"
          icon={<Building2 className="size-5" />}
          tone="violet"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold text-brand-blue">Analyses récentes</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Produites au nom de votre institution.
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to="/prototype/institution/analyses">Tout voir</Link>
              </Button>
            </div>
            <div className="mt-5 space-y-3">
              {institutionAnalyses.map((analysis) => (
                <article key={analysis.id} className="rounded-xl border p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-brand-blue">{analysis.title}</h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {analysis.author} · {analysis.updatedAt}
                      </p>
                    </div>
                    <StatusBadge status={analysis.status} />
                  </div>
                  <Button
                    className="mt-4"
                    size="sm"
                    variant="outline"
                    onClick={() => onExport(analysis.title)}
                  >
                    <Download />
                    Exporter
                  </Button>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <h2 className="font-semibold text-brand-blue">Quota d’exports</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Suivi simulé de la capacité institutionnelle.
            </p>
            <div className="mt-6 rounded-xl bg-slate-50 p-5">
              <p className="text-3xl font-semibold tabular-nums text-brand-blue">
                {exportsUsed}
                <span className="text-lg text-muted-foreground">/{EXPORT_QUOTA}</span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">exports utilisés ce mois</p>
              <div className="mt-5">
                <ProgressBar
                  value={quotaPercentage}
                  label={`${EXPORT_QUOTA - exportsUsed} export(s) restant(s)`}
                />
              </div>
            </div>
            <Button asChild className="mt-5 w-full" variant="outline">
              <Link to="/prototype/institution/analyses">Consulter les analyses</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InstitutionCompanies() {
  const { companies, reports, showToast } = usePrototype();
  const [query, setQuery] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const publishedCompanies = companies.filter(
    (company) =>
      company.published &&
      `${company.name} ${company.sector} ${company.country}`
        .toLocaleLowerCase("fr")
        .includes(query.toLocaleLowerCase("fr")),
  );

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Données autorisées"
        title="Entreprises et indicateurs publiés"
        description="Consultez les performances ESG validées et ouvrez la preuve associée à chaque entreprise."
        action={
          <Button
            variant="outline"
            onClick={() => showToast("Tableau institutionnel exporté (simulation).")}
          >
            <Download />
            Exporter le tableau
          </Button>
        }
      />

      <div className="max-w-xl">
        <label
          className="block text-sm font-medium text-brand-blue"
          htmlFor="institution-company-search"
        >
          Rechercher une entreprise
        </label>
        <input
          id="institution-company-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Nom, secteur ou pays"
          className={`${fieldClassName} mt-2`}
        />
      </div>

      {publishedCompanies.length === 0 ? (
        <Card className="shadow-none">
          <CardContent className="py-10 text-center">
            <FileSearch className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold text-brand-blue">Aucune entreprise trouvée</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Modifiez votre recherche pour afficher les données publiées.
            </p>
            <Button className="mt-4" variant="outline" onClick={() => setQuery("")}>
              Effacer la recherche
            </Button>
          </CardContent>
        </Card>
      ) : (
        <section
          className="grid gap-5 md:grid-cols-2"
          aria-label="Entreprises accessibles à l’institution"
        >
          {publishedCompanies.map((company) => {
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
                    <span className="rounded-xl bg-brand-green-light px-3 py-2 text-xl font-semibold tabular-nums text-brand-green">
                      {company.score}
                    </span>
                  </div>
                  <dl className="grid grid-cols-3 gap-2 text-center">
                    {[
                      ["E", company.environmental],
                      ["S", company.social],
                      ["G", company.governance],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg bg-slate-50 p-3">
                        <dt className="text-xs text-muted-foreground">{label}</dt>
                        <dd className="mt-1 font-semibold tabular-nums text-brand-blue">{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="text-muted-foreground">Qualité des données</span>
                    <StatusBadge
                      status={company.quality === "Élevée" ? "VALIDE" : "A_AFFECTER"}
                      label={company.quality}
                    />
                  </div>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={() =>
                      setEvidence({ company: company.name, page: report?.evidencePage ?? 1 })
                    }
                  >
                    <FileSearch />
                    Ouvrir la preuve
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </section>
      )}

      <Modal
        open={Boolean(evidence)}
        title={`Preuve — ${evidence?.company ?? "entreprise"}`}
        description="Document et page utilisés pour les données publiées."
        onClose={() => setEvidence(null)}
        size="xl"
      >
        {evidence ? <EvidencePreview company={evidence.company} page={evidence.page} /> : null}
      </Modal>
    </div>
  );
}

function InstitutionResearchers({ institutionName }: { institutionName: string }) {
  const { affiliations, inviteResearcher, updateAffiliation, showToast, users } = usePrototype();
  const institutionAffiliations = affiliations.filter(
    (affiliation) => affiliation.institution === institutionName,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [afficherTout, setAfficherTout] = useState(false);

  const visibleAffiliations = afficherTout
    ? institutionAffiliations
    : institutionAffiliations.slice(0, NOMBRE_VISIBLE_PAR_DEFAUT);
  const nombreMasque = institutionAffiliations.length - NOMBRE_VISIBLE_PAR_DEFAUT;

  // Seule source valide pour l'invitation : des comptes Chercheur déjà enregistrés sur la
  // plateforme — jamais un nom/e-mail saisi librement (règle appliquée à toute relation
  // acteur-à-acteur du système). On exclut aussi les chercheurs déjà rattachés à cette
  // institution, pour éviter les doublons de rattachement.
  const chercheursDisponibles = useMemo(() => {
    const dejaRattaches = new Set(institutionAffiliations.map((a) => a.researcherEmail));
    const normalizedQuery = query.trim().toLocaleLowerCase("fr");
    return users.filter((user) => {
      if (user.role !== "CHERCHEUR" || dejaRattaches.has(user.email)) return false;
      if (!normalizedQuery) return true;
      return `${user.name} ${user.email}`.toLocaleLowerCase("fr").includes(normalizedQuery);
    });
  }, [users, institutionAffiliations, query]);

  function submitInvitation(researcher: (typeof users)[number]) {
    inviteResearcher(researcher, institutionName);
    setQuery("");
    setModalOpen(false);
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Équipe de recherche"
        title="Chercheurs rattachés"
        description="Invitez des chercheurs et suivez immédiatement l’état de leur rattachement dans les deux espaces."
        action={
          <Button onClick={() => setModalOpen(true)}>
            <MailPlus />
            Inviter un chercheur
          </Button>
        }
      />

      <section className="grid gap-5 lg:grid-cols-2" aria-label="Chercheurs de l’institution">
        {visibleAffiliations.map((affiliation) => (
          <Card key={affiliation.id} className="shadow-none">
            <CardContent className="space-y-5 px-5 sm:px-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-11 shrink-0 place-items-center rounded-full bg-violet-50 text-sm font-semibold text-violet-700">
                    {affiliation.researcher
                      .split(" ")
                      .slice(0, 2)
                      .map((part) => part[0])
                      .join("")}
                  </span>
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold text-brand-blue">
                      {affiliation.researcher}
                    </h2>
                    <p className="truncate text-xs text-muted-foreground">
                      {affiliation.researcherEmail}
                    </p>
                  </div>
                </div>
                <StatusBadge status={affiliation.status} />
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                {affiliation.status === "INVITE" ? (
                  <Button
                    className="flex-1"
                    variant="outline"
                    onClick={() => showToast(`Invitation renvoyée à ${affiliation.researcher}.`)}
                  >
                    <RefreshCw />
                    Renvoyer
                  </Button>
                ) : null}
                {affiliation.status === "ACTIF" ? (
                  <Button
                    className="flex-1"
                    variant="outline"
                    onClick={() => updateAffiliation(affiliation.id, "SUSPENDU")}
                  >
                    Suspendre
                  </Button>
                ) : null}
                {affiliation.status === "SUSPENDU" ? (
                  <Button
                    className="flex-1"
                    onClick={() => updateAffiliation(affiliation.id, "ACTIF")}
                  >
                    Réactiver
                  </Button>
                ) : null}
                <Button
                  className="flex-1"
                  onClick={() =>
                    showToast(`Profil de ${affiliation.researcher} ouvert (simulation).`)
                  }
                >
                  Voir le profil
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </section>

      {!afficherTout && nombreMasque > 0 ? (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => setAfficherTout(true)}>
            Afficher les {nombreMasque} autre(s)
          </Button>
        </div>
      ) : null}
      {afficherTout && institutionAffiliations.length > NOMBRE_VISIBLE_PAR_DEFAUT ? (
        <div className="flex justify-center">
          <Button variant="ghost" size="sm" onClick={() => setAfficherTout(false)}>
            Réduire
          </Button>
        </div>
      ) : null}

      <Modal
        open={modalOpen}
        title="Inviter un chercheur"
        description="Sélectionnez un compte Chercheur déjà enregistré sur la plateforme — l’invitation apparaîtra immédiatement dans l’espace Chercheur."
        onClose={() => setModalOpen(false)}
      >
        <div className="space-y-5">
          <label className="relative block">
            <span className="sr-only">Rechercher un chercheur</span>
            <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className={`${fieldClassName} pl-9`}
              placeholder="Rechercher par nom ou e-mail"
            />
          </label>

          {chercheursDisponibles.length ? (
            <div className="max-h-80 space-y-3 overflow-y-auto">
              {chercheursDisponibles.map((chercheur) => (
                <button
                  key={chercheur.id}
                  type="button"
                  className="flex w-full items-center gap-3 rounded-xl border p-4 text-left transition hover:border-brand-green/40 hover:bg-brand-green-light/30"
                  onClick={() => submitInvitation(chercheur)}
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-violet-50 text-xs font-semibold text-violet-700">
                    {chercheur.name
                      .split(" ")
                      .slice(0, 2)
                      .map((part) => part[0])
                      .join("")}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-brand-blue">
                      {chercheur.name}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                      {chercheur.email} · {chercheur.organization}
                    </span>
                  </span>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucun compte Chercheur disponible ne correspond à cette recherche.
            </p>
          )}

          <div className="flex justify-end border-t pt-5">
            <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
              Annuler
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function InstitutionAnalyses({
  exportsUsed,
  onExport,
  institutionName,
}: {
  exportsUsed: number;
  onExport: (title: string) => void;
  institutionName: string;
}) {
  const { analyses } = usePrototype();
  const [detail, setDetail] = useState<PrototypeAnalysis | null>(null);
  const institutionAnalyses = analyses.filter((analysis) => analysis.owner === institutionName);
  const quotaPercentage = Math.round((exportsUsed / EXPORT_QUOTA) * 100);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Travaux institutionnels"
        title="Analyses et exports"
        description="Consultez les études produites pour l’institution et contrôlez l’utilisation du quota d’exports."
      />

      <Card className="shadow-none">
        <CardContent className="grid gap-5 px-5 sm:px-6 lg:grid-cols-[auto_1fr_auto] lg:items-center">
          <span className="grid size-12 place-items-center rounded-xl bg-brand-green-light text-brand-green">
            <Download className="size-5" />
          </span>
          <div>
            <div className="flex justify-between gap-4 text-sm">
              <span className="font-semibold text-brand-blue">Quota mensuel</span>
              <span className="tabular-nums text-muted-foreground">
                {exportsUsed}/{EXPORT_QUOTA}
              </span>
            </div>
            <div className="mt-3">
              <ProgressBar value={quotaPercentage} />
            </div>
          </div>
          <p className="text-sm font-medium text-brand-green">
            {EXPORT_QUOTA - exportsUsed} restant(s)
          </p>
        </CardContent>
      </Card>

      {institutionAnalyses.length === 0 ? (
        <Card className="shadow-none">
          <CardContent className="py-10 text-center">
            <BarChart3 className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold text-brand-blue">Aucune analyse institutionnelle</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Les travaux créés par un chercheur rattaché apparaîtront ici.
            </p>
          </CardContent>
        </Card>
      ) : (
        <section className="grid gap-5 lg:grid-cols-2" aria-label="Analyses institutionnelles">
          {institutionAnalyses.map((analysis) => (
            <Card key={analysis.id} className="shadow-none">
              <CardContent className="space-y-5 px-5 sm:px-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-semibold text-brand-blue">{analysis.title}</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {analysis.author} · {analysis.period}
                    </p>
                  </div>
                  <StatusBadge status={analysis.status} />
                </div>
                <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                  Entreprises étudiées :{" "}
                  <span className="font-medium text-brand-blue">
                    {analysis.companies.join(", ")}
                  </span>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button variant="outline" className="flex-1" onClick={() => setDetail(analysis)}>
                    Consulter
                  </Button>
                  <Button
                    className="flex-1"
                    onClick={() => onExport(analysis.title)}
                    disabled={exportsUsed >= EXPORT_QUOTA}
                  >
                    <Download />
                    Exporter
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </section>
      )}

      <Modal
        open={Boolean(detail)}
        title={detail?.title ?? "Analyse"}
        description="Synthèse institutionnelle simulée."
        onClose={() => setDetail(null)}
        size="lg"
      >
        {detail ? (
          <div className="space-y-5">
            <dl className="grid gap-4 sm:grid-cols-2">
              {[
                ["Auteur", detail.author],
                ["Période", detail.period],
                ["Statut", detail.status.replaceAll("_", " ")],
                ["Entreprises", detail.companies.join(", ")],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-slate-50 p-4">
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="mt-1 text-sm font-medium text-brand-blue">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="rounded-xl bg-brand-green-light p-5 text-sm leading-6 text-brand-blue">
              Cette synthèse réunit scores ESG, émissions carbone et qualité des preuves pour
              appuyer la décision institutionnelle.
            </div>
            <div className="flex justify-end">
              <Button onClick={() => onExport(detail.title)} disabled={exportsUsed >= EXPORT_QUOTA}>
                <Download />
                Exporter cette analyse
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

export function InstitutionPrototypePage({ section }: { section: string }) {
  const { previewUserId, showToast, users } = usePrototype();
  const institutionName =
    users.find((user) => user.id === previewUserId && user.role === "INSTITUTION")?.organization ??
    "Institut Climat & Finance";
  const [exportsUsed, setExportsUsed] = useState(8);

  function exportAnalysis(title: string) {
    if (exportsUsed >= EXPORT_QUOTA) {
      showToast("Quota d’exports atteint.");
      return;
    }
    setExportsUsed((current) => current + 1);
    showToast(`Analyse « ${title} » exportée. Quota mis à jour.`);
  }

  switch (section) {
    case "companies":
      return <InstitutionCompanies />;
    case "researchers":
      return <InstitutionResearchers institutionName={institutionName} />;
    case "analyses":
      return (
        <InstitutionAnalyses
          exportsUsed={exportsUsed}
          onExport={exportAnalysis}
          institutionName={institutionName}
        />
      );
    default:
      return (
        <InstitutionDashboard
          exportsUsed={exportsUsed}
          onExport={exportAnalysis}
          institutionName={institutionName}
        />
      );
  }
}
