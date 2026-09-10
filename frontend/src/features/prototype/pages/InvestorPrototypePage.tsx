import {
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  Building2,
  Download,
  Leaf,
  Plus,
  Scale,
  WalletCards,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { Card, CardContent } from "@/shared/ui/card";
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

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

interface EvidenceSelection {
  company: string;
  page: number;
}

function InvestorDashboard() {
  const { companies, positions, reports } = usePrototype();
  const publishedCompanies = companies.filter((company) => company.published);
  const totalInvested = positions.reduce((total, position) => total + position.amount, 0);
  const weightedScore =
    totalInvested === 0
      ? 0
      : Math.round(
          positions.reduce((total, position) => {
            const company = companies.find((item) => item.id === position.companyId);
            return total + (company?.score ?? 0) * position.amount;
          }, 0) / totalInvested,
        );
  const financedFootprint = Math.round(
    positions.reduce((total, position) => {
      const company = companies.find((item) => item.id === position.companyId);
      const emissions = company ? company.scope1 + company.scope2 + company.scope3 : 0;
      return total + emissions * (position.amount / 100_000_000);
    }, 0),
  );

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Espace Investisseur"
        title="Pilotez vos décisions responsables"
        description="Consultez les entreprises publiées, comparez leurs performances et suivez l’impact ESG de votre portefeuille."
        action={
          <Button asChild>
            <Link to="/prototype/investor/companies">
              Explorer les entreprises
              <ArrowUpRight />
            </Link>
          </Button>
        }
      />

      <section
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Synthèse du portefeuille"
      >
        <StatCard
          label="Valeur du portefeuille"
          value={currencyFormatter.format(totalInvested)}
          hint={`${positions.length} position(s) active(s)`}
          icon={<WalletCards className="size-5" />}
        />
        <StatCard
          label="Score ESG agrégé"
          value={`${weightedScore}/100`}
          hint="Pondéré par les montants investis"
          icon={<BarChart3 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Empreinte financée"
          value={`${numberFormatter.format(financedFootprint)} tCO₂e`}
          hint="Estimation simulée du portefeuille"
          icon={<Leaf className="size-5" />}
          tone="amber"
        />
        <StatCard
          label="Univers publié"
          value={publishedCompanies.length}
          hint="Entreprises validées accessibles"
          icon={<Building2 className="size-5" />}
          tone="violet"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="font-semibold text-brand-blue">Positions principales</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Répartition du portefeuille de démonstration.
                </p>
              </div>
              <Button asChild variant="outline" size="sm">
                <Link to="/prototype/investor/portfolios">Tout voir</Link>
              </Button>
            </div>
            <div className="mt-6 space-y-5">
              {positions.map((position) => {
                const share =
                  totalInvested === 0 ? 0 : Math.round((position.amount / totalInvested) * 100);
                return (
                  <div key={position.id}>
                    <div className="mb-2 flex items-center justify-between gap-4 text-sm">
                      <span className="font-medium text-brand-blue">{position.company}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {currencyFormatter.format(position.amount)}
                      </span>
                    </div>
                    <ProgressBar value={share} label={`${share} % du portefeuille`} />
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-none">
          <CardContent className="px-5 sm:px-6">
            <h2 className="font-semibold text-brand-blue">Rapports de référence</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Seules les données validées et publiées alimentent cette vue.
            </p>
            <div className="mt-5 space-y-3">
              {reports
                .filter((report) => report.status === "PUBLIE")
                .map((report) => (
                  <div key={report.id} className="rounded-xl border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-brand-blue">{report.company}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{report.title}</p>
                      </div>
                      <StatusBadge status={report.status} />
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InvestorCompanies() {
  const { companies, reports, addPosition, showToast } = usePrototype();
  const [query, setQuery] = useState("");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const publishedCompanies = companies.filter(
    (company) =>
      company.published &&
      `${company.name} ${company.sector} ${company.country}`
        .toLocaleLowerCase("fr")
        .includes(query.toLocaleLowerCase("fr")),
  );

  function openEvidence(companyId: string, company: string) {
    const report = reports.find((item) => item.companyId === companyId && item.status === "PUBLIE");
    setEvidence({ company, page: report?.evidencePage ?? 1 });
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Univers d’investissement"
        title="Entreprises publiées"
        description="Explorez uniquement les entreprises dont les données ESG ont été validées et rendues accessibles."
        action={
          <Button
            variant="outline"
            onClick={() => showToast("Liste des entreprises exportée (simulation).")}
          >
            <Download />
            Exporter
          </Button>
        }
      />

      <div className="max-w-xl">
        <label
          className="block text-sm font-medium text-brand-blue"
          htmlFor="investor-company-search"
        >
          Rechercher une entreprise
        </label>
        <input
          id="investor-company-search"
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
            <Building2 className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold text-brand-blue">Aucune entreprise trouvée</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Modifiez votre recherche pour élargir les résultats.
            </p>
            <Button className="mt-4" variant="outline" onClick={() => setQuery("")}>
              Effacer la recherche
            </Button>
          </CardContent>
        </Card>
      ) : (
        <section
          className="grid gap-5 md:grid-cols-2 xl:grid-cols-3"
          aria-label="Entreprises accessibles"
        >
          {publishedCompanies.map((company) => (
            <Card key={company.id} className="shadow-none">
              <CardContent className="space-y-5 px-5 sm:px-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-green-light font-semibold text-brand-green">
                      {company.name.slice(0, 1)}
                    </span>
                    <div className="min-w-0">
                      <h2 className="truncate font-semibold text-brand-blue">{company.name}</h2>
                      <p className="truncate text-xs text-muted-foreground">
                        {company.sector} · {company.country}
                      </p>
                    </div>
                  </div>
                  <span className="text-2xl font-semibold tabular-nums text-brand-green">
                    {company.score}
                  </span>
                </div>

                <dl className="grid grid-cols-3 gap-2 text-center">
                  {[
                    ["E", company.environmental],
                    ["S", company.social],
                    ["G", company.governance],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-slate-50 p-2">
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

                <EvidenceCard onOpen={() => openEvidence(company.id, company.name)} />

                <Button className="w-full" onClick={() => addPosition(company.id)}>
                  <Plus />
                  Ajouter 100 000 € au portefeuille
                </Button>
              </CardContent>
            </Card>
          ))}
        </section>
      )}

      <Modal
        open={Boolean(evidence)}
        title={`Preuve — ${evidence?.company ?? "entreprise"}`}
        description="Source documentaire utilisée pour les indicateurs publiés."
        onClose={() => setEvidence(null)}
        size="xl"
      >
        {evidence ? <EvidencePreview company={evidence.company} page={evidence.page} /> : null}
      </Modal>
    </div>
  );
}

function InvestorCompare() {
  const { companies, reports, showToast } = usePrototype();
  const publishedCompanies = companies.filter((company) => company.published);
  const [selectedIds, setSelectedIds] = useState(() =>
    publishedCompanies.slice(0, 2).map((company) => company.id),
  );
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const selected = publishedCompanies.filter((company) => selectedIds.includes(company.id));

  function toggleCompany(id: string) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(-3),
    );
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Aide à la décision"
        title="Comparer les performances ESG"
        description="Sélectionnez jusqu’à trois entreprises pour comparer des données homogènes, publiées et sourcées."
        action={
          <Button variant="outline" onClick={() => showToast("Comparaison exportée (simulation).")}>
            <Download />
            Exporter la comparaison
          </Button>
        }
      />

      <fieldset className="rounded-xl border bg-white p-5">
        <legend className="px-1 text-sm font-semibold text-brand-blue">
          Entreprises comparées
        </legend>
        <div className="mt-2 flex flex-wrap gap-3">
          {publishedCompanies.map((company) => (
            <label
              key={company.id}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm"
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(company.id)}
                onChange={() => toggleCompany(company.id)}
                disabled={!selectedIds.includes(company.id) && selectedIds.length >= 3}
                className="size-4 accent-brand-green"
              />
              {company.name}
            </label>
          ))}
        </div>
      </fieldset>

      {selected.length === 0 ? (
        <Card className="shadow-none">
          <CardContent className="py-10 text-center">
            <Scale className="mx-auto size-8 text-muted-foreground" />
            <h2 className="mt-3 font-semibold text-brand-blue">Sélectionnez une entreprise</h2>
            <p className="mt-1 text-sm text-muted-foreground">La comparaison apparaîtra ici.</p>
          </CardContent>
        </Card>
      ) : (
        <section
          className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3"
          aria-label="Résultats de comparaison"
        >
          {selected.map((company) => {
            const report = reports.find(
              (item) => item.companyId === company.id && item.status === "PUBLIE",
            );
            const totalEmissions = company.scope1 + company.scope2 + company.scope3;
            return (
              <Card key={company.id} className="shadow-none">
                <CardContent className="space-y-5 px-5 sm:px-6">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="font-semibold text-brand-blue">{company.name}</h2>
                      <p className="text-xs text-muted-foreground">{company.sector}</p>
                    </div>
                    <span className="rounded-xl bg-brand-green-light px-3 py-2 text-xl font-semibold text-brand-green">
                      {company.score}
                    </span>
                  </div>
                  <dl className="space-y-3 text-sm">
                    {[
                      ["Environnement", company.environmental],
                      ["Social", company.social],
                      ["Gouvernance", company.governance],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <ProgressBar value={Number(value)} label={`${label} · ${value}/100`} />
                      </div>
                    ))}
                    <div className="flex justify-between gap-4 border-t pt-3">
                      <dt className="text-muted-foreground">Émissions totales</dt>
                      <dd className="font-medium tabular-nums text-brand-blue">
                        {numberFormatter.format(totalEmissions)} tCO₂e
                      </dd>
                    </div>
                  </dl>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() =>
                      setEvidence({ company: company.name, page: report?.evidencePage ?? 1 })
                    }
                  >
                    Voir la preuve
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
        onClose={() => setEvidence(null)}
        size="xl"
      >
        {evidence ? <EvidencePreview company={evidence.company} page={evidence.page} /> : null}
      </Modal>
    </div>
  );
}

function InvestorPortfolios() {
  const { companies, positions, addPosition, reports, showToast } = usePrototype();
  const publishedCompanies = companies.filter((company) => company.published);
  const [modalOpen, setModalOpen] = useState(false);
  const [companyId, setCompanyId] = useState(publishedCompanies[0]?.id ?? "");
  const [amount, setAmount] = useState("100000");
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const totalInvested = positions.reduce((total, position) => total + position.amount, 0);
  const weightedScore = useMemo(() => {
    if (totalInvested === 0) return 0;
    return Math.round(
      positions.reduce((total, position) => {
        const company = companies.find((item) => item.id === position.companyId);
        return total + (company?.score ?? 0) * position.amount;
      }, 0) / totalInvested,
    );
  }, [companies, positions, totalInvested]);

  function submitPosition(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedAmount = Number(amount);
    if (!companyId || !Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      showToast("Renseignez une entreprise et un montant supérieur à zéro.");
      return;
    }
    addPosition(companyId, parsedAmount);
    setModalOpen(false);
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Portefeuille principal"
        title="Positions et impact financé"
        description="Visualisez la composition, le score ESG agrégé et la contribution de chaque position."
        action={
          <Button onClick={() => setModalOpen(true)}>
            <Plus />
            Ajouter une position
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Synthèse du portefeuille">
        <StatCard
          label="Montant total"
          value={currencyFormatter.format(totalInvested)}
          hint="Portefeuille principal"
          icon={<WalletCards className="size-5" />}
        />
        <StatCard
          label="Score ESG"
          value={`${weightedScore}/100`}
          hint="Pondération par position"
          icon={<BarChart3 className="size-5" />}
          tone="blue"
        />
        <StatCard
          label="Positions"
          value={positions.length}
          hint="Entreprises publiées"
          icon={<BriefcaseBusiness className="size-5" />}
          tone="violet"
        />
      </section>

      <div className="space-y-4">
        {positions.map((position) => {
          const company = companies.find((item) => item.id === position.companyId);
          const report = reports.find(
            (item) => item.companyId === position.companyId && item.status === "PUBLIE",
          );
          const share =
            totalInvested === 0 ? 0 : Math.round((position.amount / totalInvested) * 100);
          return (
            <Card key={position.id} className="shadow-none">
              <CardContent className="grid gap-5 px-5 sm:px-6 lg:grid-cols-[1fr_1fr_auto] lg:items-center">
                <div>
                  <h2 className="font-semibold text-brand-blue">{position.company}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {company?.sector} · Score ESG {company?.score ?? "—"}/100
                  </p>
                </div>
                <div>
                  <div className="mb-2 flex justify-between text-sm">
                    <span className="font-medium tabular-nums text-brand-blue">
                      {currencyFormatter.format(position.amount)}
                    </span>
                    <span className="text-muted-foreground">{share} %</span>
                  </div>
                  <ProgressBar value={share} />
                </div>
                <div className="flex flex-wrap gap-2 lg:justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setEvidence({ company: position.company, page: report?.evidencePage ?? 1 })
                    }
                  >
                    Preuve
                  </Button>
                  <Button size="sm" onClick={() => addPosition(position.companyId, 50_000)}>
                    Renforcer de 50 000 €
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex justify-end">
        <Button
          variant="outline"
          onClick={() => showToast("Synthèse du portefeuille exportée (simulation).")}
        >
          <Download />
          Exporter la synthèse
        </Button>
      </div>

      <Modal
        open={modalOpen}
        title="Ajouter une position"
        description="Cette action met immédiatement à jour le portefeuille de démonstration."
        onClose={() => setModalOpen(false)}
      >
        <form className="space-y-5" onSubmit={submitPosition}>
          <Field label="Entreprise">
            <select
              className={fieldClassName}
              value={companyId}
              onChange={(event) => setCompanyId(event.target.value)}
              required
            >
              {publishedCompanies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Montant investi" hint="Montant simulé en euros.">
            <input
              className={fieldClassName}
              type="number"
              min="1"
              step="1000"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </Field>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>
              Annuler
            </Button>
            <Button type="submit">Ajouter au portefeuille</Button>
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

export function InvestorPrototypePage({ section }: { section: string }) {
  switch (section) {
    case "companies":
      return <InvestorCompanies />;
    case "compare":
      return <InvestorCompare />;
    case "portfolios":
      return <InvestorPortfolios />;
    default:
      return <InvestorDashboard />;
  }
}
