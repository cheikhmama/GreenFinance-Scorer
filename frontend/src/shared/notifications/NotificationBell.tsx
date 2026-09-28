import { Bell } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { NotificationPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  resolveNotificationLink,
  useMarkNotificationRead,
  useMyNotifications,
  useUnreadNotificationsCount,
} from "@/shared/notifications/api";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/ui/cn";

/** Cloche de notifications, commune aux 6 espaces (montée une fois dans AppShell, à côté du
 * bouton mode nuit et du bouton de déconnexion). Ouverture/fermeture sur le même principe que
 * EntrepriseCombobox.tsx : le déclencheur porte le focus et se ferme à son blur, le panneau
 * bloque le mousedown pour ne jamais perdre ce focus en cliquant dedans.
 *
 * Marquage lu strictement individuel, au clic sur CETTE notification précise — jamais toutes à
 * la fois à l'ouverture du panneau : ouvrir la liste n'est pas « consulter » chaque notification,
 * seul le clic dessus l'est. Le point rouge (useUnreadNotificationsCount, lu depuis le total
 * réel côté serveur) ne disparaît donc que lorsque la dernière notification non lue a été
 * cliquée individuellement, jamais avant. */
export function NotificationBell() {
  const [ouvert, setOuvert] = useState(false);
  const { data: nonLuesTotal } = useUnreadNotificationsCount();
  const { data: notifications } = useMyNotifications(10);
  const marquerLue = useMarkNotificationRead();
  const navigate = useNavigate();

  function onClicNotification(notification: NotificationPublic) {
    if (!notification.lu) {
      marquerLue.mutate(notification.id);
    }
    setOuvert(false);
    const lien = resolveNotificationLink(notification.type, notification.id_ressource);
    if (lien) navigate(lien);
  }

  const aDesNonLues = (nonLuesTotal ?? 0) > 0;

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOuvert((v) => !v)}
        onBlur={() => setOuvert(false)}
        aria-label={aDesNonLues ? `Notifications (${nonLuesTotal} non lues)` : "Notifications"}
        title="Notifications"
      >
        <span className="relative">
          <Bell />
          {aDesNonLues ? (
            <span
              className="absolute -right-0.5 -top-0.5 size-2.5 rounded-full bg-destructive ring-2 ring-background"
              aria-hidden="true"
            />
          ) : null}
        </span>
      </Button>

      {ouvert ? (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 z-40 mt-2 w-80 rounded-md border bg-card text-card-foreground shadow-md"
          onMouseDown={(event) => event.preventDefault()}
        >
          <p className="border-b px-4 py-3 text-sm font-semibold text-brand-blue">Notifications</p>
          <div className="max-h-80 overflow-y-auto">
            {!notifications || notifications.length === 0 ? (
              <p className="p-4 text-sm text-brand-grey">Aucune notification pour l'instant.</p>
            ) : (
              <ul className="divide-y">
                {notifications.map((notification) => {
                  const lien = resolveNotificationLink(notification.type, notification.id_ressource);
                  return (
                    <li key={notification.id}>
                      <button
                        type="button"
                        onClick={() => onClicNotification(notification)}
                        disabled={!lien}
                        className={cn(
                          "flex w-full items-start gap-2 px-4 py-3 text-left text-sm transition",
                          lien ? "hover:bg-muted" : "cursor-default",
                        )}
                      >
                        <span
                          className={cn(
                            "mt-1.5 size-1.5 shrink-0 rounded-full",
                            notification.lu ? "bg-transparent" : "bg-destructive",
                          )}
                          aria-hidden="true"
                        />
                        <span className="min-w-0 flex-1">
                          <span
                            className={cn(
                              "block",
                              notification.lu ? "text-brand-grey" : "font-medium text-brand-blue",
                            )}
                          >
                            {notification.message}
                          </span>
                          <span className="text-xs text-brand-grey">
                            {new Date(notification.date_envoi).toLocaleString("fr-FR")}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
