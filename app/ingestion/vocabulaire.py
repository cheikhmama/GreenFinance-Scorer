"""Codes d'indicateurs partagés hors du pipeline d'extraction (tâche 4.2) : le PDF de synthèse
en a besoin dans un process qui n'importe pas app/ingestion/extractor.py."""

# Les 3 codes "score_{pilier}_declare" ci-dessus atterrissent comme des ESGMetric ordinaires
# (même branche indicateur_esg que n'importe quel autre code) -- rien ne les distingue en base
# des indicateurs réellement mesurés. Cette constante est le point unique de vérité pour les en
# exclure explicitement partout où "les indicateurs extraits" doivent rester séparés de "ce que
# l'entreprise prétend" (config/weights/default.yaml les exclut déjà par omission ; le PDF de
# synthèse et RapportESGDetail doivent les exclure/isoler activement, pas par omission silencieuse).
CODES_AUTO_DECLARES_PAR_PILIER = frozenset(
    {"score_environnement_declare", "score_social_declare", "score_gouvernance_declare"}
)
