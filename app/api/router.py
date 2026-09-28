"""Point de montage unique et versionné pour toutes les routes métier.

Sous-application FastAPI montée sous /api/v1 par app/main.py (voir
app.mount dans app/main.py). Une sous-application FastAPI — et non un
simple APIRouter — est nécessaire ici pour que /api/v1 dispose de son
propre schéma OpenAPI (/api/v1/openapi.json) et de sa propre
documentation, indépendants de l'endpoint d'infrastructure /health porté
par l'application racine.

Chaque module métier enregistre son router ici, même vide de route pour
l'instant — les routes réelles arrivent au fil des étapes 9 à 17.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin.router import router as admin_router
from app.audit.router import router as audit_router
from app.auth.csrf import CSRFMiddleware
from app.auth.router import router as auth_router
from app.company.router import router as company_router
from app.contact.router import router as contact_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import CorrelationIdMiddleware
from app.core.router import router as core_router
from app.institution.router import router as institution_router
from app.investor.router import router as investor_router
from app.researcher.router import router as researcher_router

# Catalogue explicite des tags : c'est ce qui permet à chaque module
# d'apparaître groupé dans /api/v1/openapi.json et /api/v1/docs dès
# maintenant, même sans route active à l'intérieur de son router.
OPENAPI_TAGS = [
    {"name": "contact", "description": "Contact public avec l'équipe de la plateforme."},
    {"name": "auth", "description": "Authentification et autorisation — Étape 9."},
    {
        "name": "admin",
        "description": (
            "Espace Administrateur — file d'attente, affectation, décision et publication "
            "(Étape 10 partielle)."
        ),
    },
    {
        "name": "audit",
        "description": (
            "Espace Auditeur — consultation des dossiers assignés et soumission d'avis (Étape 11)."
        ),
    },
    {
        "name": "company",
        "description": (
            "Espace Entreprise — dépôt de rapport, statut d'extraction et détail des données "
            "extraites (Étapes 5 et 10 partielles) ; reste de l'espace à l'Étape 10."
        ),
    },
    {
        "name": "notifications",
        "description": (
            "Notifications transverses, tous rôles confondus — consultation et marquage lu "
            "(Phase 5 §10)."
        ),
    },
    {"name": "investor", "description": "Espace Investisseur — Étape 16."},
    {"name": "researcher", "description": "Espace Chercheur — Étape 17."},
    {"name": "institution", "description": "Espace Institution — Étape 17."},
]

api_app = FastAPI(title="GreenFinance-Scorer API", version="v1", openapi_tags=OPENAPI_TAGS)
register_exception_handlers(api_app)
api_app.add_middleware(CorrelationIdMiddleware)
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Ajouté après CORS : middleware ajouté en dernier = le plus proche des routes, donc exécuté
# après CORS/CorrelationId côté requête entrante, et sa réponse traverse quand même CORS/
# CorrelationId au retour (voir app/auth/csrf.py pour la logique de vérification elle-même).
api_app.add_middleware(CSRFMiddleware)

api_app.include_router(auth_router)
api_app.include_router(contact_router)
api_app.include_router(core_router)
api_app.include_router(admin_router)
api_app.include_router(audit_router)
api_app.include_router(company_router)
api_app.include_router(investor_router)
api_app.include_router(researcher_router)
api_app.include_router(institution_router)
