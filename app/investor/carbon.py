"""Empreinte carbone PCAF d'un portefeuille (tâche 2.3, docs/WORKFLOWS.md §2.4).

Assemble les données (positions actives ; pour chaque entreprise, son dernier rapport validé :
ses émissions, et — depuis la tâche 5.4 — son EVIC et son chiffre d'affaires du même exercice,
convertis dans la devise du portefeuille) et délègue tout le calcul au moteur pur
app/carbon/pcaf.py. Lecture seule, calculée à la demande — les agrégats
mis en cache sur `portfolios` seront alimentés par le job de recalcul du worker (phase 4).

Seules les positions ACTIVES comptent : PCAF mesure les encours détenus à un instant donné, une
position planifiée ou clôturée n'en fait pas partie.
"""

import uuid
from decimal import Decimal

from sqlmodel import Session, col, select

from app.carbon import pcaf
from app.company.models import Company
from app.core.config import get_settings
from app.core.enums import Currency
from app.ingestion.models import CarbonEmission, ESGReport
from app.investor import entreprises as entreprises_investisseur
from app.investor import fx
from app.investor.models import Portfolio, PortfolioPosition
from app.investor.portfolio import etat_temporel
from app.investor.schemas import EtatPosition, PortfolioCarbon, PositionCarbon
from app.scoring.engine import valeur_effective


def _emissions(session: Session, rapport: ESGReport | None) -> pcaf.EmissionsEntreprise | None:
    if rapport is None:
        return None
    lignes = session.exec(
        select(CarbonEmission).where(col(CarbonEmission.report_id) == rapport.id)
    ).all()
    par_scope: dict[int, dict[str | None, pcaf.Emission]] = {1: {}, 2: {}, 3: {}}
    for ligne in lignes:
        # Revue de l'Auditeur (tâche 5.6) : valeur auditée si corrigée, ligne écartée si non
        # trouvée dans la source — jamais comptée comme zéro.
        tonnes = valeur_effective(ligne.review_status, ligne.tonnes_co2e, ligne.audited_value)
        if tonnes is None:
            continue
        par_scope[ligne.scope][ligne.ghg_category] = pcaf.Emission(
            tonnes_co2e=tonnes, qualite=ligne.pcaf_data_quality
        )
    scope_2, base_scope_2 = pcaf.choisir_scope_2(par_scope[2])
    return pcaf.EmissionsEntreprise(
        # Année des émissions elles-mêmes (celle du rapport, reportée sur chaque ligne).
        annee=lignes[0].year if lignes else rapport.fiscal_year,
        scope_1=par_scope[1].get(None),
        scope_2=scope_2,
        scope_2_base=base_scope_2,
        scope_3=par_scope[3].get(None),
    )


def _convertir(
    montant: Decimal | None, devise: Currency | None, vers: Currency, chemin_taux: str
) -> Decimal | None:
    if montant is None or devise is None:
        return None
    return fx.convertir(montant, devise, vers, chemin_taux)[0]


def empreinte_carbone(session: Session, portefeuille: Portfolio) -> PortfolioCarbon:
    devise = portefeuille.reference_currency
    chemin_taux = get_settings().fx_rates_path
    positions = [
        p
        for p in session.exec(
            select(PortfolioPosition).where(PortfolioPosition.portfolio_id == portefeuille.id)
        ).all()
        if etat_temporel(p) == EtatPosition.ACTIVE
    ]

    entreprises: dict[uuid.UUID, Company] = {}
    # Le dernier rapport validé de chaque entreprise : la même source pour les émissions et pour
    # les données financières qui les rapportent à la position.
    rapports: dict[uuid.UUID, ESGReport | None] = {}
    emissions: dict[uuid.UUID, pcaf.EmissionsEntreprise | None] = {}
    lignes: list[pcaf.LignePCAF] = []
    for position in positions:
        entreprise = None
        if position.company_id is not None:
            if position.company_id not in entreprises:
                trouvee = session.get(Company, position.company_id)
                assert trouvee is not None  # FK
                entreprises[position.company_id] = trouvee
                rapport = entreprises_investisseur.dernier_rapport_valide(session, position.company_id)
                rapports[position.company_id] = rapport
                emissions[position.company_id] = _emissions(session, rapport)
            entreprise = entreprises[position.company_id]
        rapport_retenu = rapports.get(entreprise.id) if entreprise else None
        lignes.append(
            pcaf.LignePCAF(
                position_id=position.id,
                montant=position.converted_amount,
                rapprochee=entreprise is not None,
                evic=_convertir(
                    rapport_retenu.enterprise_value,
                    rapport_retenu.enterprise_value_currency,
                    devise,
                    chemin_taux,
                )
                if rapport_retenu
                else None,
                chiffre_affaires=_convertir(
                    rapport_retenu.revenue, rapport_retenu.revenue_currency, devise, chemin_taux
                )
                if rapport_retenu
                else None,
                emissions=emissions[entreprise.id] if entreprise else None,
            )
        )

    resultat = pcaf.calculer_portefeuille(lignes)
    par_id = {position.id: position for position in positions}
    return PortfolioCarbon(
        portfolio_id=portefeuille.id,
        currency=devise,
        total_value=resultat.valeur_totale,
        financed_emissions_scope_1_2=resultat.emissions_financees_scope_1_2,
        financed_emissions_scope_3=resultat.emissions_financees_scope_3,
        carbon_footprint_scope_1_2=resultat.empreinte_carbone_scope_1_2,
        waci_scope_1_2=resultat.waci_scope_1_2,
        data_quality_scope_1_2=resultat.qualite_scope_1_2,
        data_quality_scope_3=resultat.qualite_scope_3,
        coverage_scope_1_2=resultat.couverture_scope_1_2,
        coverage_scope_3=resultat.couverture_scope_3,
        coverage_waci=resultat.couverture_waci,
        positions=[
            _position_carbone(par_id[r.position_id], r, entreprises, rapports, emissions)
            for r in resultat.lignes
        ],
    )


def _position_carbone(
    position: PortfolioPosition,
    resultat: pcaf.ResultatLigne,
    entreprises: dict[uuid.UUID, Company],
    rapports: dict[uuid.UUID, ESGReport | None],
    emissions: dict[uuid.UUID, pcaf.EmissionsEntreprise | None],
) -> PositionCarbon:
    entreprise = entreprises.get(position.company_id) if position.company_id else None
    rapport = rapports.get(position.company_id) if position.company_id else None
    donnees = emissions.get(position.company_id) if position.company_id else None
    return PositionCarbon(
        position_id=position.id,
        company_id=position.company_id,
        company_name=entreprise.name if entreprise else None,
        identifier=position.identifier_raw,
        amount=position.converted_amount,
        attribution_factor=resultat.facteur_attribution,
        financed_emissions_scope_1_2=resultat.emissions_financees_scope_1_2,
        financed_emissions_scope_3=resultat.emissions_financees_scope_3,
        carbon_intensity=resultat.intensite_carbone,
        data_quality=resultat.qualite,
        emissions_year=donnees.annee if donnees else None,
        scope_2_basis=donnees.scope_2_base if donnees else None,
        evic_date=rapport.evic_date if rapport else None,
        excluded_reason=resultat.motif_exclusion,
    )
