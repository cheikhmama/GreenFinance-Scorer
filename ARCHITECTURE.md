# Architecture — GreenFinance-Scorer

Ce document décrit les conventions structurelles posées à l'Étape 2 et que le code doit respecter à partir de
l'Étape 3. Il est versionné avec le code : toute évolution de ces conventions doit être répercutée ici dans le
même commit, jamais dans un wiki externe.

## 1. Organisation des modules

Un package sous `app/` par grande partie fonctionnelle du projet. La liste et le rôle de chacun :

| Module | Rôle | Implémenté à |
|---|---|---|
| `app/core/` | Infrastructure transverse (config, DB, erreurs, logging, dépendances) | Étapes 1-2 |
| `app/api/` | Point de montage versionné de toutes les routes métier | Étape 2 |
| `app/auth/` | Authentification et autorisation | Étape 9 |
| `app/ingestion/` | Extraction documentaire, recherche sémantique, complétude | Étapes 4, 5, 7, 8 |
| `app/scoring/` | Moteur de scoring ESG | Étape 12 |
| `app/carbon/` | Calcul carbone (facteurs d'émission, PCAF) | Étape 13 |
| `app/explainability/` | Décomposition et justification du score | Étape 14 |
| `app/admin/` | Espace Administrateur | Étape 10 |
| `app/audit/` | Espace Auditeur | Étape 11 |
| `app/company/` | Espace Entreprise | Étape 10 |
| `app/investor/` | Espace Investisseur, modèle de portefeuille | Étapes 15-16 |
| `app/researcher/` | Espace Chercheur | Étape 17 |
| `app/institution/` | Espace Institution | Étape 17 |

Un module ne connaît pas les détails internes d'un autre module. Les échanges entre modules passent par des
fonctions/schémas explicitement exposés, jamais par un import direct dans un fichier interne d'un autre module
(ex. : `app/company` ne doit pas importer `app/scoring/engine.py` directement pour son détail d'implémentation,
mais passer par une interface stable exposée par le module scoring).

## 2. Convention de nommage interne à un module

À l'intérieur d'un module (`app/<module>/`), un nom de fichier a un rôle fixe :

| Fichier | Rôle |
|---|---|
| `models.py` | Entités de persistance (SQLModel) |
| `router.py` | Routes HTTP FastAPI (`router = APIRouter(tags=["<module>"])`) |
| `schemas.py` | Schémas Pydantic d'entrée/sortie (jamais réutilisés comme modèles de persistance) |
| `permissions.py` | Règles d'autorisation propres au module |
| Autres fichiers | Nommés par leur rôle métier explicite (ex. `engine.py`, `pcaf.py`, `assignment.py`) plutôt que par un nom générique type `utils.py` ou `helpers.py` |

Chaque module métier destiné à exposer des routes possède un `router.py` avec `router = APIRouter(tags=[...])`
— même vide de route, comme posé à l'Étape 2 (Prompt 2.2). Les modules qui ne sont pas des surfaces API directes
(`ingestion`, `scoring`, `carbon`, `explainability`) n'ont pas de `router.py` : leurs résultats sont exposés par
les modules « espace » qui les consomment (`company`, `investor`, `audit`, `admin`).

## 3. Point de montage API (`app/api/router.py`)

`app/api/router.py` définit `api_app`, une **sous-application FastAPI** (pas un simple `APIRouter`), montée sous
`/api/v1` par `app.mount("/api/v1", api_app)` dans `app/main.py`. Ce choix — plutôt qu'un `APIRouter` inclus
directement dans l'app racine — est nécessaire pour que `/api/v1` dispose de son propre schéma OpenAPI
(`/api/v1/openapi.json`) et de sa propre documentation (`/api/v1/docs`), indépendants de l'endpoint
d'infrastructure `/health` porté par l'app racine (qui reste hors du préfixe `/api/v1`, car ce n'est pas une
route métier versionnée).

**Conséquence directe** : l'app racine et `api_app` sont deux applications FastAPI indépendantes, chacune avec sa
propre pile de middlewares et de gestionnaires d'exceptions. Tout ce qui doit s'appliquer aux deux (gestion des
erreurs, `CorrelationIdMiddleware`) doit être enregistré explicitement sur chacune — voir `app/main.py` et
`app/api/router.py`.

Chaque module métier enregistre son `router` dans `app/api/router.py` via `api_app.include_router(...)`, et son
tag dans `OPENAPI_TAGS` (pour apparaître groupé dans la documentation même sans route active).

## 4. Gestion des erreurs (`app/core/exceptions.py`)

Toute erreur métier hérite de `GreenFinanceError` (code + message), avec des sous-classes déjà disponibles :
`NotFoundError` (404), `ValidationError` (422), `PermissionDeniedError` (403). Une route lève l'exception
appropriée — jamais de formatage de réponse d'erreur ad hoc dans une route :

```python
from app.core.exceptions import NotFoundError

if company is None:
    raise NotFoundError("Entreprise introuvable")
```

`register_exception_handlers(app)` doit être appelé sur **toute** application FastAPI indépendante (l'app
racine et `api_app`). Il installe deux gestionnaires :

- `GreenFinanceError` → `{"error": {"code", "message", "correlation_id"}}`, code HTTP de l'exception.
- `Exception` (générique, filet de sécurité) → même structure, `code="internal_error"`, HTTP 500. La trace
  Python complète est journalisée côté serveur (`logger.error(..., exc_info=exc)`) mais **jamais** renvoyée dans
  la réponse HTTP.

## 5. Logging (`app/core/logging.py`)

Le projet utilise `structlog`, pas le module `logging` standard directement. `configure_logging(environment)`
est appelée une seule fois, au tout début de `app/main.py`, avant toute autre initialisation :

- `ENVIRONMENT=production` → sortie JSON structurée (une ligne par événement, exploitable par un agrégateur de
  logs).
- `ENVIRONMENT=development` (ou toute autre valeur) → sortie colorée lisible dans le terminal.

`CorrelationIdMiddleware` génère un `correlation_id` (UUID) par requête HTTP, le place dans
`request.state.correlation_id` (repris par `app/core/exceptions.py` dans la réponse d'erreur) et le lie aux
contextvars `structlog` pour la durée de la requête : tout `structlog.get_logger(__name__).info(...)` appelé
pendant le traitement de cette requête porte automatiquement ce `correlation_id`, sans avoir à le passer
explicitement. Comme pour les gestionnaires d'erreurs, ce middleware doit être ajouté sur chaque application
FastAPI indépendante.

Règle absolue : ne jamais logger un secret (mot de passe, clé API, jeton) — y compris implicitement via
`str(exception)` sur une exception qui embarquerait une URL de connexion complète. Voir
`tests/unit/test_logging.py::test_database_connection_error_never_leaks_the_password` pour l'exemple de test qui
vérifie ce point sur un cas réel du projet.

## 6. Dépendances transversales (`app/core/dependencies.py`)

Réexporte `get_session` (depuis `app/core/database.py`) pour centraliser les imports de dépendances FastAPI.
Expose `get_current_user`, qui lève `NotImplementedError("Authentification implémentée à l'Étape 9")` — un
placeholder explicite et bruyant, jamais un utilisateur factice silencieux. Les routes futures peuvent déjà
déclarer `user: ... = Depends(get_current_user)` dans leur signature ; seule l'implémentation de la fonction
changera à l'Étape 9, aucune signature de route n'aura à être réécrite.

## 7. Tests — `tests/unit/` vs `tests/integration/`

- **`tests/unit/`** : exerce un seul composant de façon isolée (appel direct d'une fonction, ou une application
  FastAPI jetable construite dans le test lui-même). Les assertions ne dépendent d'aucun état particulier de
  l'infrastructure externe — un test unitaire doit rester vert que la base de données soit démarrée ou non.
  Exemples : `test_error_handlers.py`, `test_logging.py`, `test_dependencies.py`.
- **`tests/integration/`** : exerce l'application réelle assemblée bout en bout, et/ou fait des assertions qui
  dépendent effectivement de l'infrastructure (une base de données joignable ou délibérément coupée, le
  câblage du router entre plusieurs modules). Exemples : `test_database.py`, `test_api_router.py`.

Un test qui importe `app.main` et vérifie un comportement variable selon que la base répond ou non
(`test_health.py`, qui accepte 200 **ou** 503 selon l'état réel) reste un test unitaire : son assertion ne
suppose aucun état d'infrastructure particulier, ce qui est le critère déterminant — pas le simple fait
d'importer l'application.
