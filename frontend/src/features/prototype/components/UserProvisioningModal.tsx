import {
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  FileText,
  FlaskConical,
  Globe2,
  GraduationCap,
  Landmark,
  LoaderCircle,
  Mail,
  Search,
  Upload,
  UserRound,
} from "lucide-react";
import { type FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { allRoleConfigs } from "../config";
import { slugByRole } from "../data";
import { usePrototype } from "../PrototypeContext";
import type { PrototypeRole } from "../types";
import { Field, fieldClassName, Modal, StatusBadge } from "./shared";

type ProvisionableRole = Exclude<PrototypeRole, "ADMINISTRATEUR">;
type SelectedRole = ProvisionableRole | "";
type DocumentMode = "URL" | "UPLOAD";
type DiscoveryStatus = "IDLE" | "LOADING" | "FOUND" | "PARTIAL";

interface ProvisioningDraft {
  role: SelectedRole;
  fullName: string;
  email: string;
  organization: string;
  companyName: string;
  website: string;
  logoUrl: string;
  sector: string;
  country: string;
  reportType: "ESG" | "DURABILITE" | "ANNUEL";
  reportYear: string;
  reportUrl: string;
  position: string;
  reference: string;
  investorType: string;
  investmentPreferences: string;
  researchDomain: string;
  institutionName: string;
  institutionWebsite: string;
  institutionCountry: string;
}

interface DiscoveryFixture {
  domains: string[];
  companyName: string;
  logoCandidates: string[];
  sector: string;
  country: string;
}

const discoveryFixtures: DiscoveryFixture[] = [
  {
    domains: ["microsoft.com"],
    companyName: "Microsoft",
    logoCandidates: ["https://www.microsoft.com/favicon.ico"],
    sector: "Technologies",
    country: "États-Unis",
  },
  {
    domains: ["orsted.com", "orsted.dk"],
    companyName: "Ørsted",
    logoCandidates: ["https://orsted.com/favicon.ico"],
    sector: "Énergies renouvelables",
    country: "Danemark",
  },
  {
    domains: ["apple.com"],
    companyName: "Apple",
    logoCandidates: [
      "https://www.apple.com/ac/structured-data/images/open_graph_logo.png",
      "https://www.apple.com/apple-touch-icon.png",
      "https://www.apple.com/favicon.ico",
    ],
    sector: "Technologies",
    country: "États-Unis",
  },
  {
    domains: ["snim.com"],
    companyName: "SNIM",
    logoCandidates: [
      "https://upload.wikimedia.org/wikipedia/commons/0/01/Snim_logo.svg",
      "https://snim.com/sites/default/files/logo_snim_final_0.jpg",
    ],
    sector: "Industrie minière",
    country: "Mauritanie",
  },
  {
    domains: ["ingka.com"],
    companyName: "Ingka Group",
    logoCandidates: [
      "https://assets.site.ingka.com/ingka-old/wp-content/uploads/2018/09/Ingka.com_Navicon.png",
      "https://assets.site.ingka.com/ingka-old/wp-content/uploads/2018/09/Ingka.com_Navicon-150x150.png",
      "https://www.ingka.com/favicon.ico",
    ],
    sector: "Commerce de détail",
    country: "Pays-Bas",
  },
];

function defaultLogoCandidates(website: URL) {
  return [
    `${website.origin}/apple-touch-icon.png`,
    `${website.origin}/favicon.ico`,
    `${website.origin}/favicon.png`,
  ];
}

const initialDraft: ProvisioningDraft = {
  role: "",
  fullName: "",
  email: "",
  organization: "",
  companyName: "",
  website: "",
  logoUrl: "",
  sector: "",
  country: "",
  reportType: "ESG",
  reportYear: String(new Date().getFullYear() - 1),
  reportUrl: "",
  position: "",
  reference: "",
  investorType: "Particulier",
  investmentPreferences: "",
  researchDomain: "",
  institutionName: "",
  institutionWebsite: "",
  institutionCountry: "",
};

const roleIntroductions: Record<
  ProvisionableRole,
  { title: string; description: string; icon: typeof UserRound }
> = {
  ENTREPRISE: {
    title: "Entreprise et responsable",
    description: "Ajout de l’entreprise, du compte responsable et de son premier rapport.",
    icon: Building2,
  },
  AUDITEUR: {
    title: "Compte auditeur",
    description: "Profil destiné au contrôle des indicateurs, preuves et rapports.",
    icon: BadgeCheck,
  },
  INVESTISSEUR: {
    title: "Compte investisseur",
    description: "Accès aux entreprises publiées, comparaisons et portefeuilles.",
    icon: BriefcaseBusiness,
  },
  CHERCHEUR: {
    title: "Compte chercheur",
    description: "Accès aux données autorisées et aux outils d’analyse.",
    icon: FlaskConical,
  },
  INSTITUTION: {
    title: "Institution et responsable",
    description: "Ajout de l’institution et de son compte responsable.",
    icon: Landmark,
  },
};

const submitLabels: Record<ProvisionableRole, string> = {
  ENTREPRISE: "Ajouter l’entreprise et inviter",
  INVESTISSEUR: "Ajouter l’investisseur et inviter",
  AUDITEUR: "Ajouter l’auditeur et inviter",
  INSTITUTION: "Ajouter l’institution et inviter",
  CHERCHEUR: "Ajouter le chercheur et inviter",
};

const provisionableRoles = [
  "ENTREPRISE",
  "INVESTISSEUR",
  "AUDITEUR",
  "INSTITUTION",
  "CHERCHEUR",
] as const satisfies readonly ProvisionableRole[];

const provisionableRoleConfigs = provisionableRoles.flatMap((role) => {
  const config = allRoleConfigs.find((item) => item.role === role);
  return config ? [config] : [];
});

function normalizeUrl(value: string) {
  const candidate = value.trim();
  if (!candidate) return null;
  try {
    const url = new URL(candidate.includes("://") ? candidate : `https://${candidate}`);
    if (!url.hostname.includes(".") || !["http:", "https:"].includes(url.protocol)) return null;
    return url;
  } catch {
    return null;
  }
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function formatFileSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo`;
}

function PersonFields({
  draft,
  update,
  organizationLabel,
  organizationPlaceholder,
  organizationRequired = false,
}: {
  draft: ProvisioningDraft;
  update: <Key extends keyof ProvisioningDraft>(key: Key, value: ProvisioningDraft[Key]) => void;
  organizationLabel?: string;
  organizationPlaceholder?: string;
  organizationRequired?: boolean;
}) {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <Field label="Nom complet *">
        <input
          className={fieldClassName}
          value={draft.fullName}
          onChange={(event) => update("fullName", event.target.value)}
          placeholder="Ex. Fatou Ahmed"
          autoComplete="name"
          required
        />
      </Field>
      <Field label="Adresse e-mail professionnelle *">
        <input
          className={fieldClassName}
          value={draft.email}
          onChange={(event) => update("email", event.target.value)}
          placeholder="nom@organisation.com"
          type="email"
          autoComplete="email"
          required
        />
      </Field>
      {organizationLabel ? (
        <div className="sm:col-span-2">
          <Field label={organizationLabel}>
            <input
              className={fieldClassName}
              value={draft.organization}
              onChange={(event) => update("organization", event.target.value)}
              placeholder={organizationPlaceholder}
              autoComplete="organization"
              required={organizationRequired}
            />
          </Field>
        </div>
      ) : null}
    </div>
  );
}

export function UserProvisioningModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const {
    companies,
    createCompany,
    createReport,
    createUser,
    selectPreviewCompany,
    selectPreviewUser,
    users,
  } = usePrototype();
  const [draft, setDraft] = useState<ProvisioningDraft>(initialDraft);
  const [documentMode, setDocumentMode] = useState<DocumentMode>("URL");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [discoveryStatus, setDiscoveryStatus] = useState<DiscoveryStatus>("IDLE");
  const [error, setError] = useState<string | null>(null);
  const [logoCandidates, setLogoCandidates] = useState<string[]>([]);
  const [logoFailed, setLogoFailed] = useState(false);
  const [logoLoaded, setLogoLoaded] = useState(false);
  const [created, setCreated] = useState<{
    name: string;
    role: PrototypeRole;
    userId: string;
    email: string;
    document?: string;
    companyId?: string;
  } | null>(null);
  const discoveryRequestRef = useRef(0);

  function update<Key extends keyof ProvisioningDraft>(key: Key, value: ProvisioningDraft[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setError(null);
  }

  function reset() {
    discoveryRequestRef.current += 1;
    setDraft(initialDraft);
    setDocumentMode("URL");
    setDocumentFile(null);
    setDiscoveryStatus("IDLE");
    setError(null);
    setLogoCandidates([]);
    setLogoFailed(false);
    setLogoLoaded(false);
    setCreated(null);
  }

  function close() {
    reset();
    onClose();
  }

  function selectRole(role: SelectedRole) {
    discoveryRequestRef.current += 1;
    setDraft({ ...initialDraft, role });
    setDocumentMode("URL");
    setDocumentFile(null);
    setDiscoveryStatus("IDLE");
    setError(null);
    setLogoCandidates([]);
    setLogoFailed(false);
    setLogoLoaded(false);
  }

  function analyzeWebsite() {
    const website = normalizeUrl(draft.website);
    if (!website) {
      setError("Saisissez une URL officielle valide, par exemple https://www.microsoft.com.");
      return;
    }

    setDraft((current) => ({ ...current, website: website.href.replace(/\/$/, "") }));
    setDiscoveryStatus("LOADING");
    setError(null);
    setLogoCandidates([]);
    setLogoFailed(false);
    setLogoLoaded(false);

    const requestId = ++discoveryRequestRef.current;
    window.setTimeout(() => {
      if (requestId !== discoveryRequestRef.current) return;
      const hostname = website.hostname.replace(/^www\./, "").toLocaleLowerCase("fr");
      const fixture = discoveryFixtures.find((item) =>
        item.domains.some((domain) => hostname === domain || hostname.endsWith(`.${domain}`)),
      );

      if (fixture) {
        setLogoCandidates(fixture.logoCandidates);
        setDraft((current) => ({
          ...current,
          companyName: current.companyName.trim() || fixture.companyName,
          logoUrl: fixture.logoCandidates[0],
          sector: fixture.sector,
          country: fixture.country,
        }));
        setDiscoveryStatus("FOUND");
        return;
      }

      const candidates = defaultLogoCandidates(website);
      setLogoCandidates(candidates);
      setDraft((current) => ({
        ...current,
        logoUrl: candidates[0],
      }));
      setDiscoveryStatus("PARTIAL");
    }, 900);
  }

  function changeCompanyWebsite(value: string) {
    discoveryRequestRef.current += 1;
    setDraft((current) => ({
      ...current,
      website: value,
      logoUrl: "",
      sector: "",
      country: "",
    }));
    setDiscoveryStatus("IDLE");
    setLogoCandidates([]);
    setLogoFailed(false);
    setLogoLoaded(false);
    setError(null);
  }

  function analyzeWebsiteIfReady() {
    if (discoveryStatus === "IDLE" && normalizeUrl(draft.website)) analyzeWebsite();
  }

  function tryNextLogoCandidate() {
    setLogoLoaded(false);
    const currentIndex = logoCandidates.indexOf(draft.logoUrl);
    const nextCandidate = logoCandidates[currentIndex + 1];

    if (nextCandidate) {
      setDraft((current) => ({ ...current, logoUrl: nextCandidate }));
      setLogoFailed(false);
      return;
    }

    setLogoFailed(true);
  }

  function validateIdentity(name: string, email: string) {
    if (!name.trim() || !email.trim()) {
      return "Complétez tous les champs obligatoires du compte.";
    }
    if (!isValidEmail(email.trim())) return "Saisissez une adresse e-mail professionnelle valide.";
    if (
      users.some(
        (user) => user.email.toLocaleLowerCase("fr") === email.toLocaleLowerCase("fr").trim(),
      )
    ) {
      return "Cette adresse e-mail est déjà associée à un compte.";
    }
    return null;
  }

  function submitCompany() {
    const website = normalizeUrl(draft.website);
    const reportUrl = documentMode === "URL" ? normalizeUrl(draft.reportUrl) : null;
    const reportYear = Number(draft.reportYear);
    if (!draft.companyName.trim()) return "Indiquez le nom légal de l’entreprise.";
    if (!website) return "Saisissez une URL officielle valide pour l’entreprise.";
    if (!draft.sector.trim() || !draft.country.trim()) {
      return "Confirmez le secteur d’activité et le pays avant l’ajout.";
    }
    if (
      !Number.isInteger(reportYear) ||
      reportYear < 2000 ||
      reportYear > new Date().getFullYear()
    ) {
      return "Indiquez une année de rapport valide.";
    }
    if (
      companies.some(
        (company) =>
          company.name.toLocaleLowerCase("fr") ===
            draft.companyName.trim().toLocaleLowerCase("fr") ||
          normalizeUrl(company.website)?.hostname === website.hostname,
      )
    ) {
      return "Cette entreprise ou ce domaine existe déjà dans le prototype.";
    }
    if (documentMode === "URL" && !reportUrl) {
      return "Ajoutez une URL valide vers le rapport officiel.";
    }
    if (documentMode === "UPLOAD" && !documentFile) return "Sélectionnez un fichier PDF.";
    if (documentFile && documentFile.size > 25 * 1024 * 1024) {
      return "Le PDF dépasse la taille maximale simulée de 25 Mo.";
    }

    const contactEmail = `contact@${website.hostname.replace(/^www\./, "")}`;
    if (
      users.some(
        (user) => user.email.toLocaleLowerCase("fr") === contactEmail.toLocaleLowerCase("fr"),
      )
    ) {
      return "Cette entreprise ou ce domaine existe déjà dans le prototype.";
    }

    const company = createCompany({
      name: draft.companyName.trim(),
      website: website.href.replace(/\/$/, ""),
      logoUrl: draft.logoUrl.trim() || null,
      sector: draft.sector.trim(),
      country: draft.country.trim(),
      contact: "",
    });
    createReport({
      companyId: company.id,
      company: company.name,
      title:
        documentFile?.name ??
        `Rapport ${draft.reportType === "DURABILITE" ? "de durabilité" : draft.reportType} ${draft.reportYear}`,
      year: reportYear,
    });
    const user = createUser({
      name: "Responsable ESG",
      email: contactEmail,
      organization: company.name,
      role: "ENTREPRISE",
      entityId: company.id,
      profile: {
        website: company.website,
        sector: company.sector,
        country: company.country,
        reportType: draft.reportType,
      },
    });
    setCreated({
      name: company.name,
      role: "ENTREPRISE",
      userId: user.id,
      email: user.email,
      document: documentFile?.name ?? reportUrl?.href,
      companyId: company.id,
    });
    return null;
  }

  function submitOtherRole(role: Exclude<ProvisionableRole, "ENTREPRISE">) {
    const organization =
      role === "INSTITUTION"
        ? draft.institutionName
        : role === "AUDITEUR"
          ? draft.organization
          : role === "CHERCHEUR"
            ? draft.organization.trim() || "Chercheur indépendant"
            : draft.organization.trim() || "Investisseur particulier";
    const commonError = validateIdentity(draft.fullName, draft.email);
    if (commonError) return commonError;
    if (role === "AUDITEUR" && !draft.organization.trim()) {
      return "Indiquez le cabinet ou l’organisation d’appartenance.";
    }
    if (role === "INSTITUTION") {
      if (!draft.institutionName.trim()) return "Indiquez le nom de l’institution.";
      if (!draft.institutionCountry.trim()) return "Indiquez le pays de l’institution.";
      if (!normalizeUrl(draft.institutionWebsite))
        return "Saisissez le site officiel de l’institution.";
    }

    const user = createUser({
      name: draft.fullName.trim(),
      email: draft.email.trim().toLocaleLowerCase("fr"),
      organization: organization.trim(),
      role,
      profile:
        role === "AUDITEUR"
          ? { position: draft.position.trim(), professionalReferences: draft.reference.trim() }
          : role === "INVESTISSEUR"
            ? {
                investorType: draft.investorType,
                investmentPreferences: draft.investmentPreferences.trim(),
              }
            : role === "CHERCHEUR"
              ? {
                  affiliation: draft.organization.trim(),
                  researchDomain: draft.researchDomain.trim(),
                }
              : {
                  country: draft.institutionCountry.trim(),
                  website: normalizeUrl(draft.institutionWebsite)?.href ?? "",
                },
    });
    setCreated({
      name: role === "INSTITUTION" ? organization.trim() : user.name,
      role,
      userId: user.id,
      email: user.email,
    });
    return null;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.role) {
      setError("Sélectionnez d’abord le rôle de l’utilisateur.");
      return;
    }
    const submissionError =
      draft.role === "ENTREPRISE" ? submitCompany() : submitOtherRole(draft.role);
    if (submissionError) setError(submissionError);
  }

  function previewSpace() {
    if (!created) return;
    const target = slugByRole[created.role];
    selectPreviewUser(created.userId);
    selectPreviewCompany(created.companyId ?? null);
    close();
    navigate(`/prototype/${target}/dashboard`);
  }

  const selectedIntroduction = draft.role ? roleIntroductions[draft.role] : null;
  const SelectedIcon = selectedIntroduction?.icon ?? UserRound;

  return (
    <Modal
      open={open}
      onClose={close}
      title={
        created
          ? created.role === "ENTREPRISE" || created.role === "INSTITUTION"
            ? "Ajout terminé"
            : "Création terminée"
          : "Ajouter un utilisateur"
      }
      description={
        created
          ? "Les données ont été ajoutées à l’état partagé du prototype."
          : "Commencez par sélectionner un rôle. Le formulaire adapté apparaîtra automatiquement."
      }
      size={draft.role === "ENTREPRISE" ? "xl" : "lg"}
    >
      {created ? (
        <div className="space-y-6 text-center">
          <span className="mx-auto grid size-16 place-items-center rounded-full bg-emerald-50 text-emerald-700">
            <CheckCircle2 className="size-8" />
          </span>
          <div>
            <h3 className="text-xl font-semibold text-brand-blue">{created.name} est prêt</h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
              Le compte est au statut Invité. L’invitation, la persistance et les traitements
              restent simulés dans cette version frontend.
            </p>
          </div>
          <div className="mx-auto grid max-w-lg gap-3 text-left sm:grid-cols-2">
            <div className="rounded-xl border bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Compte
              </p>
              <p className="mt-2 truncate text-sm font-semibold text-brand-blue">{created.email}</p>
              <p className="mt-1 text-xs text-muted-foreground">Statut : Invité</p>
            </div>
            <div className="rounded-xl border bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {created.role === "ENTREPRISE" ? "Entreprise" : "Organisation"}
              </p>
              <p className="mt-2 truncate text-sm font-semibold text-brand-blue">{created.name}</p>
              <p className="mt-1 text-xs text-muted-foreground">Ajoutée au prototype</p>
            </div>
            {created.document ? (
              <div className="rounded-xl border bg-slate-50 p-4 sm:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Document
                </p>
                <p className="mt-2 truncate text-sm font-semibold text-brand-blue">
                  {created.document}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Soumis · traitement non connecté
                </p>
              </div>
            ) : null}
          </div>
          <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:justify-center">
            <Button variant="outline" onClick={close}>
              Retour aux utilisateurs
            </Button>
            <Button onClick={previewSpace}>
              Prévisualiser l’espace{" "}
              {allRoleConfigs.find((item) => item.role === created.role)?.label}
            </Button>
          </div>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={submit} noValidate>
          <div className="rounded-xl border bg-slate-50 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-brand-blue">1. Sélectionner le rôle</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Ce choix détermine les informations demandées.
                </p>
              </div>
              <StatusBadge
                status={draft.role ? "ACTIF" : "BROUILLON"}
                label={draft.role ? "Rôle choisi" : "À choisir"}
              />
            </div>
            <Field label="Rôle de l’utilisateur">
              <select
                className={fieldClassName}
                value={draft.role}
                onChange={(event) => selectRole(event.target.value as SelectedRole)}
                required
              >
                <option value="">Sélectionner un rôle…</option>
                {provisionableRoleConfigs.map((config) => (
                  <option key={config.role} value={config.role}>
                    {config.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {draft.role && selectedIntroduction ? (
            <div className="space-y-6">
              <div className="border-b pb-5 text-center">
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-brand-green-light text-brand-green">
                  <SelectedIcon className="size-7" />
                </span>
                <p className="mt-3 text-sm font-semibold text-brand-blue">
                  2. {selectedIntroduction.title}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {selectedIntroduction.description}
                </p>
              </div>

              {draft.role === "ENTREPRISE" ? (
                <CompanyFields
                  draft={draft}
                  update={update}
                  discoveryStatus={discoveryStatus}
                  documentMode={documentMode}
                  documentFile={documentFile}
                  logoFailed={logoFailed}
                  logoLoaded={logoLoaded}
                  onAnalyze={analyzeWebsite}
                  onWebsiteBlur={analyzeWebsiteIfReady}
                  onWebsiteChange={changeCompanyWebsite}
                  onDocumentModeChange={setDocumentMode}
                  onFileChange={(file) => {
                    setDocumentFile(file);
                    setError(null);
                  }}
                  onFileError={(message) => setError(message)}
                  onLogoError={tryNextLogoCandidate}
                  onLogoLoad={() => setLogoLoaded(true)}
                />
              ) : null}

              {draft.role === "AUDITEUR" ? (
                <div className="space-y-5">
                  <PersonFields
                    draft={draft}
                    update={update}
                    organizationLabel="Cabinet ou organisation d’appartenance *"
                    organizationPlaceholder="Ex. Audit Climat Conseil"
                    organizationRequired
                  />
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Fonction ou poste">
                      <input
                        className={fieldClassName}
                        value={draft.position}
                        onChange={(event) => update("position", event.target.value)}
                        placeholder="Ex. Auditeur ESG senior"
                      />
                    </Field>
                    <Field label="Références professionnelles" hint="Facultatif">
                      <input
                        className={fieldClassName}
                        value={draft.reference}
                        onChange={(event) => update("reference", event.target.value)}
                        placeholder="Numéro ou organisme"
                      />
                    </Field>
                  </div>
                </div>
              ) : null}

              {draft.role === "INVESTISSEUR" ? (
                <div className="space-y-5">
                  <PersonFields
                    draft={draft}
                    update={update}
                    organizationLabel="Organisation ou entreprise d’appartenance (facultatif)"
                    organizationPlaceholder="Facultatif · Ex. Impact Capital"
                  />
                  <Field label="Type d’investisseur">
                    <select
                      className={fieldClassName}
                      value={draft.investorType}
                      onChange={(event) => update("investorType", event.target.value)}
                    >
                      <option>Particulier</option>
                      <option>Institutionnel</option>
                      <option>Fonds d’investissement</option>
                      <option>Gestionnaire d’actifs</option>
                    </select>
                  </Field>
                  <Field label="Préférences ou domaines d’investissement (facultatif)">
                    <input
                      className={fieldClassName}
                      value={draft.investmentPreferences}
                      onChange={(event) => update("investmentPreferences", event.target.value)}
                      placeholder="Ex. Énergies renouvelables, technologies propres"
                    />
                  </Field>
                </div>
              ) : null}

              {draft.role === "CHERCHEUR" ? (
                <div className="space-y-5">
                  <PersonFields
                    draft={draft}
                    update={update}
                    organizationLabel="Institution d’appartenance"
                    organizationPlaceholder="Université, laboratoire, centre de recherche…"
                  />
                  <Field label="Domaine de recherche">
                    <input
                      className={fieldClassName}
                      value={draft.researchDomain}
                      onChange={(event) => update("researchDomain", event.target.value)}
                      placeholder="Ex. Finance durable"
                    />
                  </Field>
                  <div className="flex gap-3 rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
                    <GraduationCap className="mt-0.5 size-5 shrink-0" />
                    <p>
                      Le rattachement à une institution sera proposé séparément après la création.
                    </p>
                  </div>
                </div>
              ) : null}

              {draft.role === "INSTITUTION" ? (
                <InstitutionFields draft={draft} update={update} />
              ) : null}
            </div>
          ) : null}

          {error ? (
            <div
              className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
              role="alert"
            >
              {error}
            </div>
          ) : null}

          <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={close}>
              Annuler
            </Button>
            <Button type="submit">
              <Mail />
              {draft.role ? submitLabels[draft.role] : "Ajouter un utilisateur"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function CompanyFields({
  draft,
  update,
  discoveryStatus,
  documentMode,
  documentFile,
  logoFailed,
  logoLoaded,
  onAnalyze,
  onWebsiteBlur,
  onWebsiteChange,
  onDocumentModeChange,
  onFileChange,
  onFileError,
  onLogoError,
  onLogoLoad,
}: {
  draft: ProvisioningDraft;
  update: <Key extends keyof ProvisioningDraft>(key: Key, value: ProvisioningDraft[Key]) => void;
  discoveryStatus: DiscoveryStatus;
  documentMode: DocumentMode;
  documentFile: File | null;
  logoFailed: boolean;
  logoLoaded: boolean;
  onAnalyze: () => void;
  onWebsiteBlur: () => void;
  onWebsiteChange: (value: string) => void;
  onDocumentModeChange: (mode: DocumentMode) => void;
  onFileChange: (file: File | null) => void;
  onFileError: (message: string) => void;
  onLogoError: () => void;
  onLogoLoad: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <Field label="Nom légal de l’entreprise *">
          <input
            className={fieldClassName}
            value={draft.companyName}
            onChange={(event) => update("companyName", event.target.value)}
            placeholder="Ex. Microsoft"
            autoComplete="organization"
            required
          />
        </Field>
        <Field label="Site officiel *">
          <input
            className={fieldClassName}
            value={draft.website}
            onChange={(event) => onWebsiteChange(event.target.value)}
            onBlur={onWebsiteBlur}
            placeholder="https://entreprise.com"
            type="url"
            required
          />
        </Field>
        <Button
          type="button"
          variant="outline"
          className="min-h-10"
          onClick={onAnalyze}
          disabled={discoveryStatus === "LOADING"}
        >
          {discoveryStatus === "LOADING" ? <LoaderCircle className="animate-spin" /> : <Search />}
          {discoveryStatus === "LOADING" ? "Analyse…" : "Analyser le site"}
        </Button>
      </div>

      {discoveryStatus === "LOADING" || discoveryStatus === "PARTIAL" ? (
        <div
          className={`rounded-xl border p-4 ${
            discoveryStatus === "LOADING"
              ? "border-emerald-200 bg-emerald-50/60"
              : "border-amber-200 bg-amber-50/60"
          }`}
          aria-live="polite"
          aria-busy={discoveryStatus === "LOADING"}
        >
          <div className="flex items-center gap-3">
            <span
              className={`grid size-10 place-items-center rounded-xl border bg-white ${
                discoveryStatus === "LOADING" ? "text-emerald-700" : "text-amber-700"
              }`}
            >
              {discoveryStatus === "LOADING" ? (
                <LoaderCircle className="size-5 animate-spin" />
              ) : (
                <Globe2 className="size-5" />
              )}
            </span>
            <div>
              <p
                className={`text-sm font-semibold ${
                  discoveryStatus === "LOADING" ? "text-emerald-900" : "text-amber-900"
                }`}
              >
                {discoveryStatus === "LOADING"
                  ? "Recherche des informations publiques…"
                  : "Certaines informations restent à compléter"}
              </p>
              {discoveryStatus === "PARTIAL" ? (
                <p className="mt-1 text-xs text-amber-800">
                  Vérifiez le secteur et le pays avant d’ajouter l’entreprise.
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {discoveryStatus === "FOUND" ? (
        <p className="sr-only" aria-live="polite">
          Logo, secteur et pays renseignés automatiquement.
        </p>
      ) : null}

      {draft.logoUrl && !logoFailed && !logoLoaded ? (
        <img
          src={draft.logoUrl}
          alt=""
          className="hidden"
          aria-hidden="true"
          data-testid="company-logo-loader"
          onLoad={onLogoLoad}
          onError={onLogoError}
        />
      ) : null}

      <div
        className={`grid items-end gap-5 ${
          logoLoaded && draft.logoUrl && !logoFailed
            ? "sm:grid-cols-[3.5rem_minmax(0,1fr)_minmax(0,1fr)]"
            : "sm:grid-cols-2"
        }`}
      >
        {logoLoaded && draft.logoUrl && !logoFailed ? (
          <div
            className="flex h-10 w-14 items-center justify-center overflow-hidden rounded-lg border border-slate-300 bg-white p-1.5"
            data-testid="company-logo"
          >
            <img
              src={draft.logoUrl}
              alt={`Logo officiel de ${draft.companyName || "l’entreprise"}`}
              className="max-h-7 max-w-full object-contain"
              onError={onLogoError}
            />
          </div>
        ) : null}
        <Field label="Secteur d’activité *">
          <input
            className={fieldClassName}
            value={draft.sector}
            onChange={(event) => update("sector", event.target.value)}
            placeholder="Ex. Technologies"
            required
          />
        </Field>
        <Field label="Pays *">
          <input
            className={fieldClassName}
            value={draft.country}
            onChange={(event) => update("country", event.target.value)}
            placeholder="Ex. France"
            required
          />
        </Field>
      </div>

      <div className="space-y-5 border-t pt-6">
        <div>
          <p className="text-sm font-semibold text-brand-blue">Premier document officiel</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Le fichier sera contrôlé visuellement ici, puis réellement stocké et traité après
            connexion au backend.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            className={`flex items-center gap-3 rounded-xl border p-4 text-left transition ${
              documentMode === "URL"
                ? "border-brand-green bg-brand-green-light/50 ring-2 ring-brand-green/10"
                : "hover:border-brand-green/40"
            }`}
            onClick={() => onDocumentModeChange("URL")}
          >
            <Globe2 className="size-5 text-brand-green" />
            <span>
              <span className="block text-sm font-semibold text-brand-blue">URL officielle</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                Lien vers le rapport publié
              </span>
            </span>
          </button>
          <button
            type="button"
            className={`flex items-center gap-3 rounded-xl border p-4 text-left transition ${
              documentMode === "UPLOAD"
                ? "border-brand-green bg-brand-green-light/50 ring-2 ring-brand-green/10"
                : "hover:border-brand-green/40"
            }`}
            onClick={() => onDocumentModeChange("UPLOAD")}
          >
            <Upload className="size-5 text-brand-green" />
            <span>
              <span className="block text-sm font-semibold text-brand-blue">Importer un PDF</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                Depuis cet ordinateur
              </span>
            </span>
          </button>
        </div>

        <div className="grid gap-5 sm:grid-cols-[1fr_9rem]">
          <Field label="Type de rapport">
            <select
              className={fieldClassName}
              value={draft.reportType}
              onChange={(event) =>
                update("reportType", event.target.value as ProvisioningDraft["reportType"])
              }
            >
              <option value="ESG">Rapport ESG</option>
              <option value="DURABILITE">Rapport de durabilité</option>
              <option value="ANNUEL">Rapport annuel</option>
            </select>
          </Field>
          <Field label="Année">
            <input
              className={fieldClassName}
              value={draft.reportYear}
              onChange={(event) => update("reportYear", event.target.value)}
              type="number"
              min="2000"
              max={new Date().getFullYear()}
              required
            />
          </Field>
        </div>

        {documentMode === "URL" ? (
          <Field label="URL officielle du rapport">
            <input
              className={fieldClassName}
              value={draft.reportUrl}
              onChange={(event) => update("reportUrl", event.target.value)}
              placeholder="https://entreprise.com/rapport-esg-2025.pdf"
              type="url"
              required
            />
          </Field>
        ) : (
          <label className="block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center transition hover:border-brand-green/50 hover:bg-brand-green-light/30">
            <input
              className="sr-only"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                if (
                  file &&
                  file.type !== "application/pdf" &&
                  !file.name.toLowerCase().endsWith(".pdf")
                ) {
                  onFileChange(null);
                  onFileError("Sélectionnez un fichier PDF valide.");
                  return;
                }
                onFileChange(file);
              }}
            />
            {documentFile ? (
              <span className="flex items-center justify-center gap-3">
                <FileText className="size-6 text-brand-green" />
                <span className="text-left">
                  <span className="block text-sm font-semibold text-brand-blue">
                    {documentFile.name}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {formatFileSize(documentFile.size)} · PDF sélectionné
                  </span>
                </span>
              </span>
            ) : (
              <span>
                <Upload className="mx-auto size-7 text-brand-green" />
                <span className="mt-2 block text-sm font-semibold text-brand-blue">
                  Choisir un rapport PDF
                </span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  Taille maximale simulée : 25 Mo
                </span>
              </span>
            )}
          </label>
        )}
      </div>
    </div>
  );
}

function InstitutionFields({
  draft,
  update,
}: {
  draft: ProvisioningDraft;
  update: <Key extends keyof ProvisioningDraft>(key: Key, value: ProvisioningDraft[Key]) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Nom de l’institution *">
          <input
            className={fieldClassName}
            value={draft.institutionName}
            onChange={(event) => update("institutionName", event.target.value)}
            placeholder="Ex. Institut Climat & Finance"
            required
          />
        </Field>
        <Field label="Pays *">
          <input
            className={fieldClassName}
            value={draft.institutionCountry}
            onChange={(event) => update("institutionCountry", event.target.value)}
            placeholder="Ex. France"
            required
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Site officiel *">
            <input
              className={fieldClassName}
              value={draft.institutionWebsite}
              onChange={(event) => update("institutionWebsite", event.target.value)}
              placeholder="https://institution.org"
              type="url"
              required
            />
          </Field>
        </div>
      </div>
      <div className="border-t pt-6">
        <p className="mb-4 text-sm font-semibold text-brand-blue">
          Responsable du compte Institution
        </p>
        <PersonFields draft={draft} update={update} />
      </div>
    </div>
  );
}
