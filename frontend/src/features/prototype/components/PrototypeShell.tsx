import { Bell, ChevronDown, FlaskConical, Leaf, LogOut, Menu, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, NavLink, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/ui/cn";
import { allRoleConfigs, isRoleSlug, prototypeRoleConfigs, sectionDescriptions } from "../config";
import { usePrototype } from "../PrototypeContext";
import { PrototypePageRouter } from "../pages/PrototypePageRouter";

export function PrototypeWorkspace() {
  const { role, section } = useParams();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const {
    affiliations,
    companies,
    previewCompanyId,
    previewUserId,
    reports,
    resetDemo,
    selectPreviewCompany,
    selectPreviewUser,
    toast,
    users,
  } = usePrototype();

  if (!isRoleSlug(role)) return <Navigate to="/prototype/admin/dashboard" replace />;

  const config = prototypeRoleConfigs[role];
  const previewUser = users.find((user) => user.id === previewUserId && user.role === config.role);
  const previewCompany =
    role === "company" ? companies.find((company) => company.id === previewCompanyId) : null;
  const persona = previewUser?.name ?? previewCompany?.contact ?? config.persona;
  const organization = previewUser?.organization ?? previewCompany?.name ?? config.organization;
  const activeSection = config.navigation.find((item) => item.section === section);
  if (!activeSection) {
    return <Navigate to={`/prototype/${role}/${config.navigation[0].section}`} replace />;
  }

  const pendingReports = reports.filter((report) =>
    ["SOUMIS", "A_AFFECTER", "CORRECTION_SOUMISE", "VALIDE"].includes(report.status),
  ).length;
  const pendingAffiliations = affiliations.filter((item) => item.status === "INVITE").length;

  function switchRole(nextRole: string) {
    if (!isRoleSlug(nextRole)) return;
    selectPreviewUser(null);
    selectPreviewCompany(null);
    navigate(`/prototype/${nextRole}/${prototypeRoleConfigs[nextRole].navigation[0].section}`);
  }

  const sidebar = (
    <>
      <div className="flex h-20 items-center justify-between border-b border-white/10 px-5">
        <Link to="/prototype/admin/dashboard" className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-brand-green text-white">
            <Leaf className="size-5" />
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-tight text-white">
              GreenFinance
            </span>
            <span className="block text-xs text-slate-400">ESG Scorer</span>
          </span>
        </Link>
        <Button
          variant="ghost"
          size="icon"
          className="text-white hover:bg-white/10 hover:text-white lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Fermer le menu"
        >
          <X />
        </Button>
      </div>

      <div className="mx-4 mt-5 rounded-xl border border-emerald-400/20 bg-emerald-400/10 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-200">
          <FlaskConical className="size-4" />
          MODE PROTOTYPE
        </div>
        <p className="mt-1.5 text-xs leading-5 text-slate-300">
          Données simulées, aucun appel backend
        </p>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-6" aria-label={`Navigation ${config.label}`}>
        <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Espace {config.label}
        </p>
        {config.navigation.map((item) => (
          <NavLink
            key={item.section}
            to={`/prototype/${role}/${item.section}`}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition",
                isActive
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-slate-300 hover:bg-white/5 hover:text-white",
              )
            }
          >
            <item.icon className="size-[18px]" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl bg-white/5 p-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-green text-xs font-semibold text-white">
            {persona
              .split(" ")
              .slice(0, 2)
              .map((part) => part[0])
              .join("")}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold text-white">{persona}</span>
            <span className="block truncate text-[11px] text-slate-400">{organization}</span>
          </span>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#f5f8f7]">
      <a
        href="#prototype-content"
        className="fixed left-4 top-2 z-[70] -translate-y-20 rounded bg-white px-4 py-2 text-sm font-semibold text-brand-blue shadow focus:translate-y-0"
      >
        Aller au contenu
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-brand-blue lg:flex">
        {sidebar}
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-brand-blue/50"
            aria-label="Fermer le menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-72 flex-col bg-brand-blue shadow-2xl">
            {sidebar}
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b bg-white/95 backdrop-blur">
          <div className="flex min-h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Ouvrir le menu"
            >
              <Menu />
            </Button>

            <div className="hidden min-w-0 flex-1 sm:block">
              <p className="truncate text-sm font-semibold text-brand-blue">
                {activeSection.label}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {sectionDescriptions[activeSection.section]}
              </p>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <label className="relative hidden sm:block">
                <span className="sr-only">Voir comme</span>
                <select
                  value={role}
                  onChange={(event) => switchRole(event.target.value)}
                  className="h-10 appearance-none rounded-lg border border-slate-300 bg-white pl-3 pr-9 text-sm font-semibold text-brand-blue outline-none focus:border-brand-green focus:ring-2 focus:ring-brand-green/15"
                  aria-label="Voir comme un autre acteur"
                >
                  {allRoleConfigs.map((item) => (
                    <option key={item.slug} value={item.slug}>
                      Voir comme : {item.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3 size-4 text-muted-foreground" />
              </label>

              <Button
                variant="ghost"
                size="icon"
                onClick={() => setNotificationsOpen((current) => !current)}
                aria-label="Notifications"
                className="relative"
              >
                <Bell />
                {pendingReports + pendingAffiliations > 0 ? (
                  <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-red-500 ring-2 ring-white" />
                ) : null}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={resetDemo}
                aria-label="Réinitialiser la démonstration"
                title="Réinitialiser la démonstration"
              >
                <RotateCcw />
              </Button>
              <Button asChild variant="ghost" size="icon" aria-label="Quitter le prototype">
                <Link to="/login">
                  <LogOut />
                </Link>
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between border-t bg-emerald-50 px-4 py-2 sm:hidden">
            <span className="text-xs font-semibold text-emerald-800">Mode prototype</span>
            <select
              value={role}
              onChange={(event) => switchRole(event.target.value)}
              className="rounded border border-emerald-200 bg-white px-2 py-1 text-xs font-semibold text-brand-blue"
              aria-label="Voir comme un autre acteur"
            >
              {allRoleConfigs.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          {notificationsOpen ? (
            <div className="absolute right-4 top-16 w-[min(24rem,calc(100vw-2rem))] rounded-xl border bg-white p-4 shadow-xl">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-brand-blue">Activité partagée</h2>
                <Button variant="ghost" size="icon-xs" onClick={() => setNotificationsOpen(false)}>
                  <X />
                </Button>
              </div>
              <div className="mt-3 space-y-2 text-sm">
                <p className="rounded-lg bg-amber-50 p-3 text-amber-900">
                  {pendingReports} rapport(s) demandent une action administrative.
                </p>
                <p className="rounded-lg bg-blue-50 p-3 text-blue-900">
                  {pendingAffiliations} invitation(s) Chercheur–Institution en attente.
                </p>
              </div>
            </div>
          ) : null}
        </header>

        <main id="prototype-content" className="mx-auto max-w-[1500px] p-4 sm:p-6 lg:p-8">
          <PrototypePageRouter role={role} section={activeSection.section} />
        </main>
      </div>

      <div
        className={cn(
          "fixed bottom-5 right-5 z-[60] max-w-sm translate-y-4 rounded-xl bg-brand-blue px-4 py-3 text-sm font-medium text-white opacity-0 shadow-xl transition",
          toast && "translate-y-0 opacity-100",
        )}
        role="status"
        aria-live="polite"
      >
        {toast}
      </div>
    </div>
  );
}
