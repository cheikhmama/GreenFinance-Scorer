import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { CardListSkeleton } from "@/shared/ui/skeleton";
import { useUsersAwaitingActivation } from "../api";

/** Comptes actifs, tous rôles confondus, qui n'ont pas encore cliqué leur lien d'activation —
 * voir app/admin/utilisateurs.py::lister_utilisateurs_en_attente. Vue transverse
 * (UsersSection ci-dessous reste scopée à un rôle choisi manuellement) : destination de la carte
 * "Utilisateurs en attente" du tableau de bord. Repliée quand la liste est vide. */
export function UsersAwaitingActivationSection() {
  const { data: utilisateurs } = useUsersAwaitingActivation();

  if (utilisateurs !== undefined && utilisateurs.length === 0) return null;

  return (
    <Card id="en-attente" className="border-amber-300">
      <CardHeader>
        <CardTitle className="text-base text-amber-700">En attente d'activation</CardTitle>
      </CardHeader>
      <CardContent>
        {utilisateurs === undefined ? <CardListSkeleton count={2} /> : null}
        {utilisateurs && utilisateurs.length > 0 ? (
          <ul className="divide-y">
            {utilisateurs.map((utilisateur) => (
              <li key={utilisateur.id} className="flex items-center gap-3 py-2">
                <span className="text-brand-blue">{utilisateur.email}</span>
                <Badge variant="secondary">{utilisateur.role}</Badge>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
