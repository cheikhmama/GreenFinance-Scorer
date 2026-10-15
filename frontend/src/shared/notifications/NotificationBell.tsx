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
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";

/** Cloche de notifications, commune aux 6 espaces (montée une fois dans AppShell, à côté du
 * bouton mode nuit et du bouton de déconnexion). Panneau Popover (Radix) : le focus entre dans la
 * liste à l'ouverture, Tab la parcourt, Échap ou un clic à côté la referme et rend le focus à la
 * cloche — utilisable entièrement au clavier (WCAG 2.1.1), contrairement à une fermeture au blur
 * du déclencheur, qui refermait le panneau avant que Tab n'atteigne une notification.
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
    if (!notification.read) {
      marquerLue.mutate(notification.id);
    }
    setOuvert(false);
    const lien = resolveNotificationLink(notification.type, notification.resource_id);
    if (lien) navigate(lien);
  }

  const aDesNonLues = (nonLuesTotal ?? 0) > 0;

  return (
    <Popover open={ouvert} onOpenChange={setOuvert}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-haspopup="dialog"
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
      </PopoverTrigger>
      <PopoverContent
        align="end"
        sideOffset={8}
        aria-label="Notifications"
        className="w-80 rounded-md bg-card p-0 text-card-foreground shadow-md"
      >
        <p className="border-b px-4 py-3 text-sm font-semibold text-brand-blue">Notifications</p>
        <div className="max-h-80 overflow-y-auto">
          {!notifications || notifications.length === 0 ? (
            <p className="p-4 text-sm text-brand-grey">Aucune notification pour l'instant.</p>
          ) : (
            <ul className="divide-y">
              {notifications.map((notification) => {
                const lien = resolveNotificationLink(notification.type, notification.resource_id);
                return (
                  <li key={notification.id}>
                    <button
                      type="button"
                      onClick={() => onClicNotification(notification)}
                      disabled={!lien}
                      className={cn(
                        "flex w-full items-start gap-2 px-4 py-3 text-left text-sm transition outline-none focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                        lien ? "hover:bg-muted" : "cursor-default",
                      )}
                    >
                      <span
                        className={cn(
                          "mt-1.5 size-1.5 shrink-0 rounded-full",
                          notification.read ? "bg-transparent" : "bg-destructive",
                        )}
                        aria-hidden="true"
                      />
                      <span className="min-w-0 flex-1">
                        {notification.read ? null : <span className="sr-only">Non lue : </span>}
                        <span
                          className={cn(
                            "block",
                            notification.read ? "text-brand-grey" : "font-medium text-brand-blue",
                          )}
                        >
                          {notification.message}
                        </span>
                        <span className="text-xs text-brand-grey">
                          {new Date(notification.sent_at).toLocaleString("fr-FR")}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
