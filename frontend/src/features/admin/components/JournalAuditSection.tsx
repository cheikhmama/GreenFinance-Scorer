import { useMemo, useState } from "react";
import type { JournalAuditPublic } from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import {
  libelleActionJournal,
  libelleResultatJournal,
  libelleTypeRessource,
  libelleValeurJournal,
} from "@/shared/format/journal";
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

/** Journal d'audit (table de données, tâche 5.17) : date, action, acteur, ressource et résultat ;
 * avant / après, identifiants et corrélation dans le tiroir. `concerneId` restreint à l'historique
 * d'un compte ou d'une entreprise (actions faites ou subies). */
export function JournalAuditSection({ concerneId }: { concerneId?: string }) {
  const { data, isLoading, isError } = useTableJournal(concerneId);
  const [ouvertId, setOuvertId] = useState<string | null>(null);

  const colonnes = useMemo<ColonneTable<JournalAuditPublic>[]>(
    () => [
      {
        id: "date",
        entete: "Date",
        masquable: false,
        valeurTri: (e) => e.occurred_at,
        valeurExport: (e) => dateHeure(e.occurred_at),
        cellule: (e) => (
          <span className="font-mono whitespace-nowrap">{dateHeure(e.occurred_at)}</span>
        ),
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
        cellule: (e) =>
          e.actor_name || e.actor_email ? (
            acteur(e)
          ) : (
            <span className="text-muted-foreground">Anonyme</span>
          ),
      },
      {
        id: "ressource",
        entete: "Ressource",
        valeurTri: (e) => libelleTypeRessource(e.resource_type),
        cellule: (e) => (
          <span className="text-muted-foreground">{libelleTypeRessource(e.resource_type)}</span>
        ),
      },
    ],
    [],
  );
  const ouvert = data?.find((e) => e.id === ouvertId) ?? null;

  return (
    <>
      <DataTable
        libelle="Journal d’audit"
        lignes={data}
        colonnes={colonnes}
        cle={(e) => e.id}
        rechercheDans={(e) =>
          `${libelleActionJournal(e.action)} ${acteur(e)} ${e.actor_email ?? ""} ${libelleTypeRessource(e.resource_type)}`
        }
        placeholderRecherche="Action, personne, ressource…"
        filtres={[
          { id: "action", libelle: "Action", valeur: (e) => libelleActionJournal(e.action) },
          {
            id: "ressource",
            libelle: "Ressource",
            valeur: (e) => libelleTypeRessource(e.resource_type),
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
                    { libelle: "Ressource", valeur: libelleTypeRessource(ouvert.resource_type) },
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
