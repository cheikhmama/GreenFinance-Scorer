/**
 * Libellé lisible d'une cause d'échec d'extraction (RapportESG.extraction_erreur) — la valeur
 * brute est une chaîne de classification fixe posée par app/ingestion/extractor.py (jamais
 * str(exception), pour ne jamais fuiter de contenu sensible), pas un texte destiné à l'écran.
 * Record<string, ...> plutôt qu'un enum TS : ce n'est pas un type énuméré côté backend
 * (VARCHAR libre), une nouvelle étape peut s'y ajouter sans migration de schéma.
 */
const LIBELLES: Record<string, string> = {
  chargement_modele_embedding_echoue: "Échec du chargement du modèle de recherche sémantique",
  docling_conversion_echouee: "Échec de la conversion du document (PDF illisible ou corrompu)",
  indexation_semantique_echouee: "Échec de l'indexation sémantique du document",
  relance_llm_echouee: "Échec de la relance du modèle d'extraction sur les indicateurs manquants",
  appel_llm_echoue: "Échec de l'appel au modèle d'extraction (réseau ou fournisseur indisponible)",
  quota_llm_epuise:
    "Quota journalier des modèles d'extraction atteint — relancez l'analyse demain ou utilisez une clé API payante",
  persistance_echouee: "Échec de l'enregistrement des données extraites",
  erreur_inattendue: "Erreur inattendue",
  // Posée par la tâche planifiée du worker (tâche 4.1) : traitement interrompu au-delà du délai.
  delai_depasse: "Traitement interrompu (délai dépassé)",
};

export function libelleCauseExtraction(etape: string | null): string {
  if (etape === null) return "Cause inconnue";
  return LIBELLES[etape] ?? `Cause non répertoriée (${etape})`;
}
