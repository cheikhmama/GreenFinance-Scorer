from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    DevisePosition,
    MethodeDonnee,
    Pilier,
    Role,
    StatutRapport,
    TypeDureeInvestissement,
    TypeRapport,
)


def test_statut_rapport_values() -> None:
    assert {s.value for s in StatutRapport} == {
        "ENVOYE",
        "EN_EXTRACTION",
        "AFFECTE_AUDITEUR",
        "EN_VALIDATION",
        "VALIDE",
        "REJETE",
        "DEMANDE_CORRECTION",
    }


def test_type_rapport_values() -> None:
    assert {t.value for t in TypeRapport} == {
        "RAPPORT_ANNUEL",
        "RAPPORT_ESG",
        "RAPPORT_CLIMAT",
    }


def test_canal_depot_values() -> None:
    assert {c.value for c in CanalDepot} == {"AUTOMATIQUE", "ENTREPRISE"}


def test_pilier_values() -> None:
    assert {p.value for p in Pilier} == {"ENVIRONNEMENT", "SOCIAL", "GOUVERNANCE"}


def test_methode_donnee_values() -> None:
    assert {m.value for m in MethodeDonnee} == {"RAPPORTEE", "ESTIMEE", "CALCULEE"}


def test_decision_audit_values() -> None:
    assert {d.value for d in DecisionAudit} == {
        "RECOMMANDE_VALIDATION",
        "RECOMMANDE_REJET",
        "DEMANDE_CLARIFICATION",
    }


def test_role_values() -> None:
    assert {r.value for r in Role} == {
        "ADMINISTRATEUR",
        "ENTREPRISE",
        "AUDITEUR",
        "INVESTISSEUR",
        "CHERCHEUR",
        "INSTITUTION",
    }


def test_devise_position_values() -> None:
    assert {d.value for d in DevisePosition} == {"MRU", "USD", "EUR"}


def test_type_duree_investissement_values() -> None:
    assert {t.value for t in TypeDureeInvestissement} == {"OUVERTE", "FIXE"}
