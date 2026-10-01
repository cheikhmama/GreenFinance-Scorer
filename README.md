# GreenFinance-Scorer

[![CI](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml/badge.svg)](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml)

Plateforme de notation ESG et carbone. Les entreprises déposent leurs rapports de durabilité ; la
plateforme en extrait les indicateurs **avec la page qui les prouve**, un auditeur vérifie, un
administrateur valide, et le score calculé — transparent, décomposable, reproductible — devient
consultable par les investisseurs et les chercheurs.

![Fiche entreprise vue par un investisseur : score, décomposition et preuves](docs/screenshots/07-investisseur-fiche-score.png)

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Rôles et permissions](#rôles-et-permissions)
- [Architecture](#architecture)
- [Captures d'écran](#captures-décran)
- [Démarrage local](#démarrage-local)
- [Tests et qualité](#tests-et-qualité)
- [Déploiement](#déploiement)
- [Documentation](#documentation)

## Fonctionnalités

**Du rapport au score**
- **Dépôt** d'un rapport PDF (ou import par URL) par l'entreprise, avec contrôle du fichier et
  détection des doublons ; brouillons et corrections versionnées.
- **Extraction** en arrière-plan : conversion Docling (OCR si besoin), recherche sémantique des
  pages pertinentes (bge-m3 + FAISS), extraction structurée par LLM (Gemini). Chaque valeur est
  rattachée à **sa page source**, découpée en extrait PDF consultable — aucune valeur sans preuve.
- **Couverture** : pour chaque indicateur attendu, la plateforme dit s'il a été trouvé, non trouvé
  ou confirmé absent.
- **Audit** : un auditeur affecté examine les indicateurs et leurs preuves, puis rend un avis
  (validation, rejet ou demande de clarification).
- **Décision** : l'administrateur valide, rejette ou demande une correction. La validation calcule
  le score **dans la même transaction** ; une configuration de pondération est figée par son
  empreinte SHA-256, donc un score ancien se recalcule toujours à l'identique.
- **Explicabilité** : décomposition exacte du score, indicateur par indicateur, face à une
  référence sectorielle (graphique en cascade).
- **Publication** : une entreprise n'est visible des autres rôles qu'avec un rapport validé et
  scoré.

**Investisseurs**
- Catalogue des entreprises publiées, fiches détaillées, comparaison jusqu'à quatre entreprises.
- Portefeuilles multi-devises (conversion à taux figé), import de positions par CSV
  (rapprochement ISIN / LEI / ticker), export CSV.
- **Empreinte carbone PCAF** : émissions financées Scopes 1+2 (Scope 3 à part), empreinte par
  million investi, WACI, qualité des données — une donnée manquante n'est jamais comptée zéro.

**Recherche**
- Les institutions créent des projets, invitent des chercheurs et définissent un périmètre
  d'entreprises et de documents.
- Les chercheurs rédigent des analyses comparatives, soumises à l'institution (validation ou
  correction, avec historique des versions) ; export CSV limité par quota.
- **Validation croisée** : import d'un jeu de notes externe (CSV), rapprochement par ISIN/LEI et
  corrélation de Spearman avec les scores de la plateforme.

**Plateforme**
- Inscription publique des entreprises, soumise à validation de l'administrateur ; comptes activés
  par lien e-mail, réinitialisation et changement d'e-mail par lien à usage unique.
- Notifications dans l'application, journal d'audit des événements de compte, tableaux de bord par
  rôle.

## Rôles et permissions

| Rôle | Peut… | Ne voit que… |
|---|---|---|
| `ADMIN` | Valider les inscriptions, gérer les comptes, affecter les auditeurs, décider des rapports, publier ou suspendre une entreprise, saisir les données financières (CA, valeur d'entreprise), consulter le journal d'audit | tout |
| `ENTERPRISE` | Déposer et corriger ses rapports, suivre leur statut, télécharger la synthèse PDF | sa propre entreprise |
| `AUDITOR` | Examiner un dossier et ses preuves, rendre un avis | les dossiers qui lui sont affectés |
| `INVESTOR` | Consulter et comparer les entreprises publiées, gérer ses portefeuilles, voir leur empreinte PCAF | les entreprises publiées, ses portefeuilles |
| `INSTITUTION` | Inviter des chercheurs, créer des projets, valider les analyses, exporter | ses projets et leur périmètre |
| `RESEARCHER` | Rédiger et soumettre des analyses, comparer, valider contre un jeu externe | le périmètre des projets auxquels il est affecté |

Deux règles s'appliquent partout : un rôle non autorisé reçoit `403` ; un utilisateur du bon rôle
qui n'a pas accès à la ressource reçoit `404`, sans jamais apprendre qu'elle existe. Les sessions
passent par un cookie `httpOnly` protégé contre le CSRF ; les tentatives de connexion sont limitées
par e-mail et par IP.

## Architecture

```mermaid
flowchart LR
    Browser["Navigateur<br/>React 19 · Vite · TanStack Query"]
    subgraph Serveur
        API["API FastAPI<br/>/api/v1"]
        W["Worker ARQ<br/>e-mails · synthèses PDF · tâche planifiée"]
        WX["Worker d'extraction<br/>Docling · bge-m3 · FAISS"]
    end
    DB[("PostgreSQL 16")]
    R[("Redis 7<br/>files ARQ · limites")]
    S[("Stockage<br/>rapports · preuves · avatars")]
    LLM["Gemini<br/>(extraction structurée)"]

    Browser -->|"cookie de session"| API
    API --> DB
    API -->|"enfile"| R
    R --> W
    R --> WX
    W --> DB
    WX --> DB
    WX --> LLM
    API --> S
    W --> S
    WX --> S
```

- **Backend** (`app/`) : un module par domaine (`company`, `reporting`, `ingestion`, `audit`,
  `scoring`, `explainability`, `carbon`, `investor`, `institution`, `researcher`, `admin`,
  `auth`), chacun organisé en routes → services → modèles. SQLModel/SQLAlchemy 2, Pydantic v2,
  une migration Alembic par évolution du schéma.
- **Travaux en arrière-plan** (ARQ sur Redis) : deux files — l'extraction (un rapport à la fois,
  modèles lourds) et le reste (e-mails, PDF de synthèse, reprise des extractions interrompues).
  Un travail n'est enfilé qu'après le commit de la transaction qui l'a déclenché.
- **Frontend** (`frontend/`) : client TypeScript généré par Orval depuis le schéma OpenAPI ; la CI
  échoue si le client n'est pas à jour.

Le cycle de vie d'un rapport (l'entreprise voit les quatre états d'examen, de `EXTRACTING` à
`PENDING_DECISION`, comme un seul : « En cours d'examen 🔒 ») :

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> EXTRACTING : dépôt
    EXTRACTING --> AWAITING_ASSIGNMENT : extraction terminée
    EXTRACTING --> EXTRACTION_FAILED
    EXTRACTION_FAILED --> EXTRACTING : relance (admin)
    AWAITING_ASSIGNMENT --> IN_AUDIT : affectation d'un auditeur
    IN_AUDIT --> PENDING_DECISION : avis d'audit
    PENDING_DECISION --> VALIDATED : validation + score
    PENDING_DECISION --> REJECTED
    PENDING_DECISION --> REVISION_REQUESTED
    REVISION_REQUESTED --> EXTRACTING : nouvelle version
```

Détails : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (modèle de données, sécurité,
transactions, scoring) et [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) (transitions, acteurs, effets).

## Captures d'écran

Prises sur le jeu de démonstration (voir [plus bas](#jeu-de-démonstration)).

| | |
|---|---|
| ![Connexion](docs/screenshots/01-connexion.png) **Connexion** | ![Tableau de bord administrateur](docs/screenshots/02-admin-tableau-de-bord.png) **Administrateur** — état de la plateforme et actions prioritaires |
| ![Rapport et preuves](docs/screenshots/03-admin-rapport-preuves.png) **Administrateur** — un rapport validé : avis d'audit, indicateurs et page source de chacun | ![Journal d'audit](docs/screenshots/04-admin-journal.png) **Administrateur** — journal d'audit |
| ![Dossier auditeur](docs/screenshots/05-auditeur-dossier.png) **Auditeur** — dossier affecté, indicateurs et preuves | ![Tableau de bord investisseur](docs/screenshots/06-investisseur-tableau-de-bord.png) **Investisseur** — tableau de bord |
| ![Fiche entreprise](docs/screenshots/07-investisseur-fiche-score.png) **Investisseur** — score, décomposition et émissions | ![Portefeuille](docs/screenshots/08-investisseur-portefeuille-carbone.png) **Investisseur** — portefeuille et empreinte PCAF |
| ![Tableau de bord entreprise](docs/screenshots/09-entreprise-tableau-de-bord.png) **Entreprise** — suivi du rapport | ![Projet de recherche](docs/screenshots/10-institution-projet.png) **Institution** — projet, chercheurs et périmètre |

## Démarrage local

Prérequis : Docker, [uv](https://docs.astral.sh/uv/), Node.js 22.

```bash
cp .env.example .env               # une seule fois
./scripts/dev-up.sh                # PostgreSQL + Redis + migrations
uv run uvicorn app.main:app --reload --port 8000   # terminal 1
cd frontend && npm install && npm run dev           # terminal 2
uv run arq app.worker.settings.WorkerSettings              # terminal 3 : e-mails, PDF, tâche planifiée
uv run arq app.worker.settings.ExtractionWorkerSettings    # terminal 4 : extraction des rapports
```

Frontend sur `http://localhost:5173`, API sur `http://localhost:8000` (documentation interactive :
`/api/v1/docs`). Le proxy Vite fait apparaître `/api/v1` comme same-origin depuis le frontend
(`frontend/vite.config.ts`), ce qui permet le cookie de session sans configuration CORS.

Sans workers, les e-mails et les extractions attendent dans Redis et sont traités au démarrage
d'un worker. Sans vraie clé `GEMINI_API_KEY`, l'extraction bascule sur un mode de démonstration
qui ne lit pas le PDF. En Docker : `docker compose up api worker worker-extraction`
(ports et identifiants de développement dans `docker-compose.override.yml`).

### Jeu de démonstration

`scripts/seed_demo.py` charge dans une base **vide** les six entreprises synthétiques de
`data_test/reference_e2e/`, passées par les vrais services (affectation, avis, validation avec
calcul du score, publication), plus un portefeuille, un projet de recherche et une analyse. Quatre
entreprises sont publiées, une attend la décision de l'administrateur, une attend l'auditeur.

```bash
docker compose exec db createdb -U greenfinance greenfinance_demo
export DATABASE_URL=postgresql+psycopg://greenfinance:changeme@localhost:5432/greenfinance_demo
export STORAGE_PATH=./storage/demo
uv run alembic upgrade head && uv run python scripts/seed_demo.py
```

Comptes (mot de passe commun `demo-greenfinance-2026`) : `admin@`, `auditeur@`,
`investisseur@`, `institution@`, `chercheur@`, `atlas@` (entreprise) — tous
`@greenfinance-demo.com`. Lancer ensuite l'API avec les mêmes variables d'environnement.

## Tests et qualité

```bash
uv run pytest                      # tests unitaires et d'intégration (PostgreSQL requis)
uv run ruff check app tests && uv run mypy app tests
cd frontend && npm run lint && npx tsc -b && npm test && npm run api:check
```

La CI (`.github/workflows/ci.yml`) exécute tout cela sur chaque pull request, plus :
`alembic upgrade head` depuis une base vide, `alembic check` (un modèle modifié sans sa migration
échoue), une seule tête Alembic, et la construction de l'image `api`.

## Déploiement

```bash
POSTGRES_PASSWORD=… REDIS_PASSWORD=… \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

- Deux images depuis le même `Dockerfile` multi-étapes : `api` (API, worker par défaut,
  migrations — sans la pile d'extraction) et `worker` (extraction Docling/torch). Utilisateur non
  privilégié, ni tests ni outils de développement.
- Le service `migrate` applique `alembic upgrade head` avant tout le reste.
- Seul le port de l'API est publié ; PostgreSQL et Redis restent sur le réseau Docker, Redis exige
  un mot de passe.
- Derrière un reverse proxy, lancer uvicorn avec `FORWARDED_ALLOW_IPS=<adresse du proxy>` : les
  limites par IP (connexion, contact) reposent sur la vraie adresse du client.

Variables principales (liste complète et valeurs par défaut dans `.env.example`) :

| Variable | Rôle |
|---|---|
| `DATABASE_URL`, `REDIS_URL` | Connexions PostgreSQL et Redis |
| `SECRET_KEY` | Signature des jetons de session |
| `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS` | Liens des e-mails, origines autorisées |
| `SMTP_*`, `MAIL_FROM`, `CONTACT_TO_EMAIL` | Envoi des e-mails |
| `GEMINI_API_KEY` | Extraction par LLM (mode démonstration si absente) |
| `STORAGE_PATH` | Fichiers déposés, extraits de preuve, synthèses, avatars |
| `DEFAULT_SCORING_CONFIG`, `FX_RATES_PATH` | Méthodologie de scoring (`config/weights/`), taux de change (`config/fx/`) |

## Documentation

| Document | Contenu |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architecture cible et état : modèle de données, sécurité, transactions, workers, scoring |
| [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) | Cycles de vie : inscription, rapport, portefeuille, recherche |
| [`docs/TASKS.md`](docs/TASKS.md) | Suivi des tâches de la refonte |
| [`docs/RENAME_PLAN.md`](docs/RENAME_PLAN.md) | Glossaire du passage du modèle de domaine à l'anglais |
| [`ARCHITECTURE.md`](ARCHITECTURE.md), [`FRONTEND-ARCHITECTURE.md`](FRONTEND-ARCHITECTURE.md) | Conventions de code backend et frontend |
| [`config/weights/default.yaml`](config/weights/default.yaml) | Méthodologie de scoring de référence, commentée |
