# Corpus de référence E2E

Distinct de `data_test/ground_truth.yaml` (rapports **réels**, utilisé pour valider la
**précision** d'extraction face à la vraie complexité documentaire : centaines de pages,
tableaux, ambiguïté). Ce corpus-ci contient des entreprises **synthétiques**, avec des rapports
courts et sans ambiguïté, pour valider le **workflow complet** — dépôt, extraction réelle, audit,
décision administrative, publication — sans dépendre de la difficulté d'extraction d'un rapport
réel. Les valeurs n'engagent aucune entreprise existante.

Chaque dossier contient :

- `scenario.json` — profil de l'entreprise, métadonnées du rapport, indicateurs attendus après
  extraction (mêmes 7 codes que `app/ingestion/extractor.py::INDICATEURS_CIBLES`), et le résultat
  attendu à chaque étape suivante du circuit (avis d'audit, décision administrative, publication) ;
- `rapport.pdf` — généré à partir de `scenario.json` par
  `scripts/generate_reference_e2e_reports.py` (ne pas éditer le PDF à la main, éditer le JSON puis
  régénérer).

Une extraction **réelle** (pas simulée) suppose une vraie clé `GEMINI_API_KEY` dans `.env` — un
placeholder fait toujours basculer le pipeline vers `_extraction_demo_synthetique`
(`app/ingestion/extractor.py`), qui ignore le contenu du PDF déposé.
