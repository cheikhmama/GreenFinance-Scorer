import { type SyntheticEvent, useId, useState } from "react";
import { ApiError } from "@/shared/api/errors";
import {
  type CrossValidationReport,
  type ReferenceDatasetImportResult,
  UnmatchedReason,
} from "@/shared/api/generated/greenFinanceScorerAPI.schemas";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { useConfirm } from "@/shared/ui/confirm-dialog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { PageHeader } from "@/shared/ui/page-header";
import { Select } from "@/shared/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/ui/table";
import {
  useCrossValidationReport,
  useDeleteReferenceDataset,
  useImportReferenceDataset,
  useReferenceDatasets,
} from "../api";

const LIBELLES_SCORE: Record<string, string> = {
  ENVIRONMENTAL: "Environnement",
  SOCIAL: "Social",
  GOVERNANCE: "Gouvernance",
  GLOBAL: "Score global",
};

const LIBELLES_MOTIF: Record<UnmatchedReason, string> = {
  [UnmatchedReason.UNKNOWN]: "Aucune entreprise de votre périmètre",
  [UnmatchedReason.DUPLICATE]: "Entreprise déjà rapprochée plus haut",
  [UnmatchedReason.NO_PLATFORM_SCORE]: "Pas encore de score officiel",
};

function nombre(valeur: number | null | undefined, decimales = 1): string {
  return valeur == null
    ? "—"
    : valeur.toLocaleString("fr-FR", { maximumFractionDigits: decimales });
}

function FormulaireImport({ onImporte }: { onImporte: (datasetId: string) => void }) {
  const importer = useImportReferenceDataset();
  const [fichier, setFichier] = useState<File | null>(null);
  const [champs, setChamps] = useState({
    name: "",
    source_url: "",
    licence: "",
    scale_min: "0",
    scale_max: "100",
    higher_is_better: "true",
  });
  const [resultat, setResultat] = useState<ReferenceDatasetImportResult | null>(null);
  const ids = {
    fichier: useId(),
    name: useId(),
    source_url: useId(),
    licence: useId(),
    scale_min: useId(),
    scale_max: useId(),
    higher_is_better: useId(),
  };

  function envoyer(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fichier || importer.isPending) return;
    importer.mutate(
      {
        file: fichier,
        name: champs.name,
        source_url: champs.source_url,
        licence: champs.licence,
        scale_min: Number(champs.scale_min),
        scale_max: Number(champs.scale_max),
        higher_is_better: champs.higher_is_better === "true",
      },
      {
        onSuccess: (donnees) => {
          setResultat(donnees);
          onImporte(donnees.dataset.id);
        },
      },
    );
  }

  const erreur = importer.error;
  const texte = (champ: keyof typeof champs, libelle: string, type = "text") => (
    <div className="space-y-1">
      <Label htmlFor={ids[champ]}>{libelle}</Label>
      <Input
        id={ids[champ]}
        type={type}
        step={type === "number" ? "any" : undefined}
        value={champs[champ]}
        onChange={(event) => setChamps({ ...champs, [champ]: event.target.value })}
      />
    </div>
  );

  return (
    <form onSubmit={envoyer} className="space-y-4" noValidate>
      <p className="text-sm text-muted-foreground">
        Fichier CSV avec une colonne <code>isin</code> ou <code>lei</code> et au moins une colonne{" "}
        <code>environmental</code>, <code>social</code>, <code>governance</code> ou{" "}
        <code>total</code>. Les autres colonnes sont ignorées ; le rapprochement ne se fait jamais
        par le nom seul.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        {texte("name", "Nom du jeu de données")}
        {texte("source_url", "Adresse de la source")}
        {texte("licence", "Licence")}
        {texte("scale_min", "Échelle : minimum", "number")}
        {texte("scale_max", "Échelle : maximum", "number")}
        <div className="space-y-1">
          <Label htmlFor={ids.higher_is_better}>Sens des scores</Label>
          <Select
            id={ids.higher_is_better}
            value={champs.higher_is_better}
            onChange={(event) => setChamps({ ...champs, higher_is_better: event.target.value })}
          >
            <option value="true">Plus haut = meilleur</option>
            <option value="false">Plus bas = meilleur (score de risque)</option>
          </Select>
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor={ids.fichier}>Fichier CSV</Label>
        <Input
          id={ids.fichier}
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFichier(event.target.files?.[0] ?? null)}
        />
      </div>
      {erreur ? (
        <Alert variant="destructive">
          <AlertTitle>Import refusé</AlertTitle>
          <AlertDescription>
            {erreur instanceof ApiError && erreur.fields ? (
              <ul className="list-disc pl-4">
                {Object.entries(erreur.fields).map(([cle, message]) => (
                  <li key={cle}>
                    {cle.replace("line_", "Ligne ")} : {message}
                  </li>
                ))}
              </ul>
            ) : (
              erreur.message
            )}
          </AlertDescription>
        </Alert>
      ) : null}
      {resultat ? (
        <Alert role="status">
          <AlertTitle>
            {resultat.imported} ligne(s) importée(s), {resultat.skipped} écartée(s)
          </AlertTitle>
          {resultat.skipped_lines.length > 0 ? (
            <AlertDescription>
              <ul className="list-disc pl-4">
                {resultat.skipped_lines.map((ligne) => (
                  <li key={ligne.line}>
                    Ligne {ligne.line} : {ligne.reason}
                  </li>
                ))}
              </ul>
            </AlertDescription>
          ) : null}
        </Alert>
      ) : null}
      <Button type="submit" disabled={!fichier || importer.isPending}>
        {importer.isPending ? "Import en cours…" : "Importer"}
      </Button>
    </form>
  );
}

function Rapport({ rapport }: { rapport: CrossValidationReport }) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {rapport.matched} entreprise(s) rapprochée(s), {rapport.unmatched} ligne(s) hors
        comparaison. Scores du jeu ramenés sur 0-100 avant l’écart moyen ; la corrélation de rang
        n’en dépend pas.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Score</TableHead>
            <TableHead>Paires</TableHead>
            <TableHead>Spearman</TableHead>
            <TableHead>Écart absolu moyen (/100)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rapport.agreement.map((accord) => (
            <TableRow key={accord.score} className="border-t">
              <TableCell>{LIBELLES_SCORE[accord.score] ?? accord.score}</TableCell>
              <TableCell className="tabular-nums">{accord.pairs}</TableCell>
              <TableCell className="tabular-nums">{nombre(accord.spearman, 2)}</TableCell>
              <TableCell className="tabular-nums">
                {nombre(accord.mean_absolute_difference)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {rapport.matches.length > 0 ? (
        <Table>
          <caption className="pb-2 text-left font-medium">
            Entreprises rapprochées (score global)
          </caption>
          <TableHeader>
            <TableRow>
              <TableHead>Ligne</TableHead>
              <TableHead>Entreprise</TableHead>
              <TableHead>Jeu de données</TableHead>
              <TableHead>Plateforme</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rapport.matches.map((correspondance) => (
              <TableRow key={correspondance.line} className="border-t">
                <TableCell className="tabular-nums">{correspondance.line}</TableCell>
                <TableCell>{correspondance.company_name}</TableCell>
                <TableCell className="tabular-nums">
                  {nombre(correspondance.dataset_scores.GLOBAL)}
                </TableCell>
                <TableCell className="tabular-nums">
                  {nombre(correspondance.platform_scores.GLOBAL)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      {rapport.unmatched_lines.length > 0 ? (
        <Table>
          <caption className="pb-2 text-left font-medium">Lignes hors comparaison</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Ligne</TableHead>
              <TableHead>Identifiant</TableHead>
              <TableHead>Nom (fichier)</TableHead>
              <TableHead>Motif</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rapport.unmatched_lines.map((ligne) => (
              <TableRow key={ligne.line} className="border-t">
                <TableCell className="tabular-nums">{ligne.line}</TableCell>
                <TableCell className="font-mono">{ligne.isin ?? ligne.lei}</TableCell>
                <TableCell>{ligne.company_name ?? "—"}</TableCell>
                <TableCell>{LIBELLES_MOTIF[ligne.reason]}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}

/** Validation croisée (tâche 3.3) : compare les scores officiels de la plateforme à un jeu de
 * données ESG public, sur les entreprises publiées du périmètre du Chercheur. Jeux de données
 * privés, jamais utilisés par le calcul des scores. */
export function CrossValidationPage() {
  const { data: jeux } = useReferenceDatasets();
  const supprimer = useDeleteReferenceDataset();
  const confirm = useConfirm();
  const [selection, setSelection] = useState<string | null>(null);
  const rapport = useCrossValidationReport(selection);

  async function retirer(datasetId: string, nom: string) {
    const ok = await confirm({
      title: "Supprimer ce jeu de données ?",
      description: `« ${nom} » et toutes ses lignes seront supprimés.`,
      confirmLabel: "Supprimer",
    });
    if (!ok) return;
    supprimer.mutate(datasetId, {
      onSuccess: () => setSelection((actuel) => (actuel === datasetId ? null : actuel)),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Validation croisée"
        description="Comparer les scores de la plateforme à un jeu de données public (Kaggle, CDP, GRI…)."
      />
      <Card>
        <CardHeader>
          <CardTitle>Importer un jeu de données</CardTitle>
        </CardHeader>
        <CardContent>
          <FormulaireImport onImporte={setSelection} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Mes jeux de données</CardTitle>
        </CardHeader>
        <CardContent>
          {jeux && jeux.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun jeu de données importé.</p>
          ) : null}
          <ul className="divide-y">
            {jeux?.map((jeu) => (
              <li key={jeu.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="text-sm">
                  <p className="font-medium">{jeu.name}</p>
                  <p className="text-muted-foreground">
                    {jeu.row_count} ligne(s) · {jeu.licence} ·{" "}
                    <a href={jeu.source_url} className="underline" target="_blank" rel="noreferrer">
                      source
                    </a>
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant={selection === jeu.id ? "default" : "outline"}
                    onClick={() => setSelection(jeu.id)}
                  >
                    Voir la comparaison
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => retirer(jeu.id, jeu.name)}>
                    Supprimer
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {selection ? (
        <Card>
          <CardHeader>
            <CardTitle>Comparaison</CardTitle>
          </CardHeader>
          <CardContent>
            {rapport.isLoading ? <p className="text-muted-foreground">Calcul…</p> : null}
            {rapport.isError ? <p className="text-destructive">Comparaison indisponible.</p> : null}
            {rapport.data ? <Rapport rapport={rapport.data} /> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
