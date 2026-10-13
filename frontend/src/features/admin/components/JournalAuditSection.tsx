import { useMemo, useState } from "react";
import type { JournalAuditPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleActionJournal,
  libelleResultatJournal,
  libelleTypeRessource,
  libelleValeurJournal,
} from "@/shared/format/journal";
import { libelleRole } from "@/shared/format/role";
import { Badge } from "@/shared/ui/badge";
import { type ColonneTable, DataTable } from "@/shared/ui/data-table";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFields,
  SheetHeader,
  SheetSection,
  SheetTitle,
} from "@/shared/ui/sheet";
import { useTableJournal } from "../api";

function dateHeure(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR");
}

function acteur(e: JournalAuditPublic): string {
  return e.actor_name ?? e.actor_email ?? "Anonyme";
}

/** Un compte est désigné par son rôle (« Investisseur »), toute autre ressource par son type. */
function ressource(e: JournalAuditPublic): string {
  if (e.resource_type !== "User") return libelleTypeRessource(e.resource_type);
  return e.resource_user_role ? libelleRole(e.resource_user_role) : "Compte supprimé";
}

/** Deux catégories masquées à l'écran, jamais supprimées ni modifiées en base (le journal reste
 * immuable) : une ressource de type compte dont le rôle est introuvable (compte supprimé depuis),
 * et toute entrée sans acteur identifié — aucune action du code actuel n'en écrit plus (voir
 * app/core/audit.py), une telle ligne ne peut venir que d'un compte de test supprimé après coup.
 * Une entrée AVEC acteur connu reste affichée même en échec : c'est le signal le plus utile pour
 * repérer une activité suspecte sur un vrai compte. */
function affichable(e: JournalAuditPublic): boolean {
  return (
    (e.resource_type !== "User" || Boolean(e.resource_user_role)) &&
    Boolean(e.actor_name || e.actor_email)
  );
}

/** Journal d'audit (table de données, tâche 5.17) : ressource, action, acteur, résultat et date ;
 * avant / après, identifiants et corrélation dans le tiroir. `concerneId` restreint à l'historique
 * d'un compte ou d'une entreprise (actions faites ou subies). */
export function JournalAuditSection({ concerneId }: { concerneId?: string }) {
  const { data, isLoading, isError } = useTableJournal(concerneId);
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const lignes = useMemo(() => data?.lignes.filter(affichable), [data]);

  const colonnes = useMemo<ColonneTable<JournalAuditPublic>[]>(
    () => [
      {
        id: "ressource",
        entete: "Ressource",
        masquable: false,
        valeurTri: (e) => ressource(e),
        cellule: (e) => <span className="text-muted-foreground">{ressource(e)}</span>,
      },
      {
        id: "action",
        entete: "Action",
        valeurTri: (e) => libelleActionJournal(e.action),
        cellule: (e) => (
          <span className="font-medium text-foreground">{libelleActionJournal(e.action)}</span>
        ),
      },
      {
        id: "acteur",
        entete: "Par",
        valeurTri: (e) => acteur(e),
        cellule: (e) => (
          <span className="flex flex-col">
            <span title={e.actor_email ?? undefined}>{acteur(e)}</span>
            {/* Pas de doublon avec Ressource quand l'acteur agit sur lui-même (ex. connexion) :
             * Ressource montre déjà ce même rôle. */}
            {e.actor_role && e.actor_id !== e.resource_id ? (
              <span className="text-xs text-muted-foreground">{libelleRole(e.actor_role)}</span>
            ) : null}
          </span>
        ),
      },
      {
        id: "resultat",
        entete: "Résultat",
        valeurTri: (e) => libelleResultatJournal(e.result),
        cellule: (e) => (
          <Badge variant={e.result === "success" ? "success" : "destructive"}>
            {libelleResultatJournal(e.result)}
          </Badge>
        ),
      },
      {
        id: "date",
        entete: "Date",
        valeurTri: (e) => e.occurred_at,
        valeurExport: (e) => dateHeure(e.occurred_at),
        cellule: (e) => (
          <span className="font-mono whitespace-nowrap">{dateHeure(e.occurred_at)}</span>
        ),
      },
    ],
    [],
  );
  const ouvert = lignes?.find((e) => e.id === ouvertId) ?? null;

  return (
    <>
      <DataTable
        libelle="Journal d’audit"
        lignes={lignes}
        tronque={data?.tronque}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) =>
          `${libelleActionJournal(e.action)} ${acteur(e)} ${e.actor_email ?? ""} ${ressource(e)}`
        }
        placeholderRecherche="Action, personne, ressource…"
        filtres={[
          { id: "action", libelle: "Action", valeur: (e) => libelleActionJournal(e.action) },
          {
            id: "ressource",
            libelle: "Ressource",
            valeur: (e) => ressource(e),
          },
          { id: "resultat", libelle: "Résultat", valeur: (e) => libelleResultatJournal(e.result) },
        ]}
        triInitial={{ colonne: "date", sens: "desc" }}
        surOuvrir={(e) => setOuvertId(e.id)}
        libelleLigne={(e) => `${libelleActionJournal(e.action)} du ${dateHeure(e.occurred_at)}`}
        ligneActive={ouvertId}
        chargement={isLoading}
        erreur={isError}
        messageVide="Aucune entrée."
        nomExport="journal-audit"
        memoire="admin-journal"
      />
      <Sheet open={ouvert !== null} onOpenChange={(o) => !o && setOuvertId(null)}>
        {ouvert ? (
          <SheetContent>
            <SheetHeader>
              <SheetTitle>{libelleActionJournal(ouvert.action)}</SheetTitle>
              <SheetDescription>{dateHeure(ouvert.occurred_at)}</SheetDescription>
              <Badge
                variant={ouvert.result === "success" ? "success" : "destructive"}
                className="w-fit"
              >
                {libelleResultatJournal(ouvert.result)}
              </Badge>
            </SheetHeader>
            <SheetBody>
              <SheetSection titre="Événement">
                <SheetFields
                  champs={[
                    { libelle: "Par", valeur: acteur(ouvert) },
                    { libelle: "E-mail", valeur: ouvert.actor_email ?? null },
                    { libelle: "Ressource", valeur: ressource(ouvert) },
                    {
                      libelle: "Code de l’action",
                      valeur: <code className="font-mono text-xs">{ouvert.action}</code>,
                    },
                  ]}
                />
              </SheetSection>
              {ouvert.old_value || ouvert.new_value ? (
                <SheetSection titre="Changement">
                  <SheetFields
                    champs={[
                      {
                        libelle: "Avant",
                        valeur: ouvert.old_value ? libelleValeurJournal(ouvert.old_value) : null,
                      },
                      {
                        libelle: "Après",
                        valeur: ouvert.new_value ? libelleValeurJournal(ouvert.new_value) : null,
                      },
                    ]}
                  />
                </SheetSection>
              ) : null}
              <SheetSection titre="Identifiants techniques">
                <SheetFields
                  champs={[
                    {
                      libelle: "Ressource",
                      valeur: (
                        <code className="font-mono text-xs">{ouvert.resource_id ?? "—"}</code>
                      ),
                    },
                    {
                      libelle: "Acteur",
                      valeur: <code className="font-mono text-xs">{ouvert.actor_id ?? "—"}</code>,
                    },
                    {
                      libelle: "Corrélation",
                      valeur: (
                        <code className="font-mono text-xs">{ouvert.correlation_id ?? "—"}</code>
                      ),
                    },
                  ]}
                />
              </SheetSection>
            </SheetBody>
          </SheetContent>
        ) : null}
      </Sheet>
    </>
  );
}
