"""Couverture des indicateurs cibles par rapport (Étape 8, statut à 3 valeurs depuis Phase 6).

Persiste, pour CHAQUE code de INDICATEURS_CIBLES, ce que le LLM d'extraction a réellement répondu
— y compris "non trouvé" — plutôt que de ne garder trace que des indicateurs effectivement présents
(voir app/ingestion/models.py::MetricCoverage). Sert deux besoins :
  - transparence à l'écran : une donnée absente doit être signalée comme telle, jamais laissée
    silencieusement invisible (décision produit, voir la conversation qui a motivé ce module) ;
  - diagnostic de couverture sémantique : distinguer TROUVE / NON_TROUVE / ABSENT_CONFIRME (voir
    MetricCoverageStatus, app/core/enums.py), utile pour juger si la sélection adaptative de
    pages (app/ingestion/extractor.py) fait manquer des indicateurs sur un rapport de plusieurs
    centaines de pages.
"""

import uuid

from app.core.enums import MetricCoverageStatus
from app.ingestion.models import MetricCoverage
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait

# Reçoit une liste de codes (pas app.ingestion.extractor.CibleIndicateur directement) pour éviter
# un import circulaire : extractor.py appelle ce module, celui-ci ne doit jamais importer
# extractor.py en retour.


def _absence_confirmee(extrait: IndicateurExtrait | None, recherche_exhaustive: bool) -> bool:
    """Un code ne passe à ABSENT_CONFIRME que sous l'une de ces deux conditions strictes, jamais
    l'inverse d'une simple absence silencieuse :
      (a) le LLM cite une déclaration EXPLICITE de non-divulgation, avec sa page — une citation
          sans page n'est pas vérifiable, ne compte pas (exige les deux champs) ;
      (b) la recherche sémantique pour ce code a examiné TOUTES les pages au-dessus de son propre
          plancher de pertinence sans rien trouver (recherche_exhaustive, calculé par
          app/ingestion/extractor.py::run_extraction_pipeline à partir de pages_par_code/
          pages_vues_par_code — jamais déduit du seul budget de tokens, qui peut avoir écarté des
          pages pertinentes pour CE code au profit d'autres codes dans le classement fusionné).
    Sinon le code reste NON_TROUVE : "pas encore trouvé" n'est jamais promu en "confirmé absent"
    sans preuve de l'une des deux conditions ci-dessus."""
    if extrait is not None and extrait.non_divulgation_citation and extrait.non_divulgation_page is not None:
        return True
    return recherche_exhaustive


def calculer_couverture(
    rapport_id: uuid.UUID,
    extraction: ExtractionEntreprise,
    codes: list[str],
    pages_examinees_par_code: dict[str, int],
    recherche_exhaustive_par_code: dict[str, bool],
) -> list[MetricCoverage]:
    """Une ligne par code cible — jamais seulement pour ceux trouvés. Si le LLM a omis un code de
    sa réponse (ne devrait pas arriver, le prompt l'exige explicitement, mais un fournisseur externe
    ne garantit rien), il compte comme non trouvé plutôt que de disparaître silencieusement.
    pages_examinees_par_code/recherche_exhaustive_par_code sont désormais par code (Phase 6) — un
    code peut avoir reçu un budget de pages différent d'un autre après la relance groupée (voir
    app/ingestion/extractor.py::run_extraction_pipeline), un entier partagé ne le représenterait
    plus correctement."""
    extraits_par_code = {i.code: i for i in extraction.indicateurs}
    couvertures = []
    for code in codes:
        extrait = extraits_par_code.get(code)
        # Même critère que l'enregistrement : une valeur sans page n'a pas de preuve, elle n'est
        # pas enregistrée — elle ne compte donc pas comme trouvée (tâche 5.11).
        trouve = bool(
            extrait
            and extrait.trouve
            and extrait.valeur is not None
            and extrait.page_source is not None
        )
        if trouve:
            statut = MetricCoverageStatus.TROUVE
        elif _absence_confirmee(extrait, recherche_exhaustive_par_code.get(code, False)):
            statut = MetricCoverageStatus.ABSENT_CONFIRME
        else:
            statut = MetricCoverageStatus.NON_TROUVE
        couvertures.append(
            MetricCoverage(
                report_id=rapport_id,
                metric_code=code,
                status=statut,
                pages_examined=pages_examinees_par_code.get(code, 0),
            )
        )
    return couvertures
