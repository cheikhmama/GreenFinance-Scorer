from app.core.enums import (
    AuditDecision,
    CompanyStatus,
    Currency,
    DataMethod,
    DurationType,
    Pillar,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)


def test_report_status_values() -> None:
    assert [s.value for s in ReportStatus] == [
        "DRAFT",
        "EXTRACTING",
        "EXTRACTION_FAILED",
        "AWAITING_ASSIGNMENT",
        "IN_AUDIT",
        "PENDING_DECISION",
        "REVISION_REQUESTED",
        "VALIDATED",
        "REJECTED",
    ]


def test_company_status_values() -> None:
    assert {s.value for s in CompanyStatus} == {"PENDING_ONBOARDING", "ACTIVE", "SUSPENDED"}


def test_type_rapport_values() -> None:
    assert {t.value for t in ReportType} == {
        "RAPPORT_ANNUEL",
        "RAPPORT_ESG",
        "RAPPORT_CLIMAT",
    }


def test_canal_depot_values() -> None:
    assert {c.value for c in SubmissionChannel} == {"AUTOMATIQUE", "ENTREPRISE"}


def test_pilier_values() -> None:
    assert {p.value for p in Pillar} == {"ENVIRONNEMENT", "SOCIAL", "GOUVERNANCE"}


def test_methode_donnee_values() -> None:
    assert {m.value for m in DataMethod} == {"RAPPORTEE", "ESTIMEE", "CALCULEE"}


def test_decision_audit_values() -> None:
    assert {d.value for d in AuditDecision} == {
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
    assert {d.value for d in Currency} == {"MRU", "USD", "EUR"}


def test_type_duree_investissement_values() -> None:
    assert {t.value for t in DurationType} == {"OUVERTE", "FIXE"}
