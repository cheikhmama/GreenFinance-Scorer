from app.core.enums import (
    CanalDepot,
    CompanyStatus,
    DecisionAudit,
    DevisePosition,
    ExtractionStatus,
    MethodeDonnee,
    Pilier,
    ReportStatus,
    Role,
    TypeDureeInvestissement,
    TypeRapport,
)


def test_report_status_values() -> None:
    assert {s.value for s in ReportStatus} == {
        "DRAFT",
        "SUBMITTED",
        "PENDING_AUDIT",
        "PENDING_DECISION",
        "REVISION_REQUESTED",
        "VALIDATED",
        "REJECTED",
    }


def test_extraction_status_values() -> None:
    assert {s.value for s in ExtractionStatus} == {
        "NOT_STARTED",
        "QUEUED",
        "RUNNING",
        "DONE",
        "FAILED",
    }


def test_company_status_values() -> None:
    assert {s.value for s in CompanyStatus} == {"PENDING_ONBOARDING", "ACTIVE", "SUSPENDED"}


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
        "ADMIN",
        "ENTERPRISE",
        "AUDITOR",
        "INVESTOR",
        "RESEARCHER",
        "INSTITUTION",
    }


def test_devise_position_values() -> None:
    assert {d.value for d in DevisePosition} == {"MRU", "USD", "EUR"}


def test_type_duree_investissement_values() -> None:
    assert {t.value for t in TypeDureeInvestissement} == {"OUVERTE", "FIXE"}
