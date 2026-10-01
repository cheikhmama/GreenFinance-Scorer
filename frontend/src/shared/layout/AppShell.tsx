import { ChevronRight, LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useMatches } from "react-router-dom";
import { useCurrentUser, useLogout } from "@/features/auth/api";
import { NotificationBell } from "@/shared/notifications/NotificationBell";
import { UserAvatar } from "@/shared/profile/UserAvatar";
import { useTheme } from "@/shared/theme/ThemeProvider";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/ui/cn";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { roleNavConfig } from "./roleNav";

/**
 * Contenant applicatif réel (sidebar + navigation + en-tête), monté par chaque `routes.tsx` en
 * route parente au-dessus de `RequireRole` : `<RequireRole ...><AppShell /></RequireRole>`, les
 * pages de l'espace arrivant via `<Outlet />`. Repris du design validé lors de l'atelier
 * prototype (`features/prototype/components/PrototypeShell.tsx`), sans les mécanismes propres à
 * la démonstration (changement de rôle à la volée, prévisualisation d'un autre compte,
 * réinitialisation) : dans une interface adossée à la vraie authentification, ces mécanismes
 * seraient une porte d'usurpation, pas une commodité.
 */
export function AppShell() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const confirm = useConfirm();
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  // Une route peut demander toute la largeur via `handle: { pleineLargeur: true }` (tâche 5.7).
  const pleineLargeur = useMatches().some(
    (match) => (match.handle as { pleineLargeur?: boolean } | undefined)?.pleineLargeur,
  );

  // RequireRole a déjà garanti une session valide avant de monter ce composant ; ce garde-fou ne
  // couvre que l'instant très bref entre le montage et le premier rendu avec les données en cache.
  if (!user) return null;

  const config = roleNavConfig[user.role];

  // Commun aux 6 espaces (Admin, Entreprise, Auditeur, Investisseur, Chercheur, Institution) :
  // AppShell est le contenant partagé par tous, jamais dupliqué par espace — une seule popup de
  // confirmation ici suffit à couvrir la plateforme entière. Pas de style "destructive" (voir
  // shared/ui/confirm-dialog.tsx) : se déconnecter est réversible, contrairement à une suppression.
  async function seDeconnecter() {
    const confirme = await confirm({
      title: "Se déconnecter ?",
      description: "Vous devrez vous reconnecter pour accéder à nouveau à votre espace.",
      confirmLabel: "Confirmer la déconnexion",
      cancelLabel: "Annuler",
    });
    if (!confirme) return;
    logout.mutate();
  }

  const sidebar = (
    <>
      <div className="flex h-20 items-center justify-between border-b border-white/10 px-5">
        <span className="flex items-center gap-3">
          <img src="/favicon.svg" alt="GreenFinance-Scorer" className="size-10 rounded-xl" />
          <span>
            <span className="block text-sm font-semibold tracking-tight text-white">
              GreenFinance
            </span>
            <span className="block text-xs text-slate-400">ESG Scorer</span>
          </span>
        </span>
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

      <nav className="flex-1 space-y-1 px-3 py-6" aria-label={`Navigation ${config.label}`}>
        <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Espace {config.label}
        </p>
        {config.items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
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

      {config.profilDansNavigation ? null : (
        <div className="border-t border-white/10 p-3">
          <NavLink
            to={config.profilTo}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-xl p-3 transition",
                isActive
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-slate-300 hover:bg-white/5 hover:text-white",
              )
            }
          >
            <UserAvatar
              nom={user.name ?? user.email}
              avatar={user.avatar}
              fallback="icone"
              className="size-9 shrink-0 text-xs"
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-semibold text-white">
                {user.name || user.email}
              </span>
              <span className="block truncate text-[11px] text-slate-400">Profil</span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-slate-500" />
          </NavLink>
        </div>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#app-content"
        className="fixed left-4 top-2 z-[70] -translate-y-20 rounded bg-card px-4 py-2 text-sm font-semibold text-brand-blue shadow focus:translate-y-0"
      >
        Aller au contenu
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col bg-brand-navy lg:flex">
        {sidebar}
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-brand-navy/50"
            aria-label="Fermer le menu"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative flex h-full w-72 flex-col bg-brand-navy shadow-2xl">
            {sidebar}
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex min-h-16 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Ouvrir le menu"
          >
            <Menu />
          </Button>

          <Link to="/dashboard" className="flex items-center gap-2 lg:hidden">
            <span className="grid size-8 place-items-center rounded-lg bg-brand-green text-xs font-bold text-white">
              GF
            </span>
          </Link>

          <div className="ml-auto flex items-center gap-3">
            <NotificationBell />
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Passer en mode clair" : "Passer en mode sombre"}
              title={theme === "dark" ? "Passer en mode clair" : "Passer en mode sombre"}
            >
              {theme === "dark" ? <Sun /> : <Moon />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={seDeconnecter}
              disabled={logout.isPending}
              aria-label="Se déconnecter"
              title="Se déconnecter"
            >
              <LogOut />
            </Button>
          </div>
        </header>

        <main
          id="app-content"
          className={cn("mx-auto p-4 sm:p-6 lg:p-8", pleineLargeur ? "max-w-none" : "max-w-6xl")}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
