# Diagrammes d'architecture — GreenFinance-Scorer

Diagrammes générés à partir du code (`app/`, `frontend/src/`, `docker-compose.yml`, `alembic/`)
et des workflows de référence (`docs/WORKFLOWS.md`).

- **Partie A — Diagrammes UML** (dossier [`uml/`](uml/)) : notation UML 2, réalisés avec PlantUML,
  PNG à 200 dpi, destinés au rapport de PFE.
- **Partie B — Vues complémentaires** (ce dossier) : schémas d'architecture et flux de données
  réalisés avec Mermaid.

---

# Partie A — Diagrammes UML

Sources PlantUML dans [`uml/src/`](uml/src/), avec une feuille de style commune (`_style.iuml`).
Pour régénérer (Java et Graphviz requis) :

```bash
PLANTUML_JAR=/chemin/plantuml.jar GRAPHVIZ_DOT=/chemin/dot ./uml/src/render.sh            # tous
PLANTUML_JAR=/chemin/plantuml.jar GRAPHVIZ_DOT=/chemin/dot ./uml/src/render.sh st-01-rapport.puml
```

## A.1 Diagrammes de cas d'utilisation

### Hiérarchie des acteurs

Six rôles authentifiés qui héritent de l'utilisateur authentifié, le visiteur, et trois systèmes
externes (Gemini, GLEIF, SMTP).

![Hiérarchie des acteurs](uml/uc-00-acteurs.png)

### Cas d'utilisation global

Vue d'ensemble : un ou deux cas majeurs par acteur, l'extraction automatique incluse dans le dépôt.

![Cas d'utilisation global](uml/uc-01-global.png)

### Entreprise

Inscription publique (vérification de l'e-mail, suivi, complément d'informations, activation) puis
déclaration ESG (session, dépôt ou import par URL, analyse du document, checklist, soumission,
nouvelle version).

![Cas d'utilisation — Entreprise](uml/uc-02-entreprise.png)

### Administrateur

Examen des inscriptions avec revue KYC, demandes d'accès, gestion des utilisateurs et des
entreprises, et circuit de validation des rapports jusqu'à la publication du score.

![Cas d'utilisation — Administrateur](uml/uc-03-administrateur.png)

### Auditeur

Examen des rapports affectés, preuves, révision de chaque valeur (accepter, corriger, déclarer
introuvable), avis d'audit et pré-score. L'avis (FAVORABLE, FAVORABLE_WITH_RESERVATIONS,
CORRECTION_REQUIRED, UNFAVORABLE) exige un commentaire sauf s'il est favorable. Le pré-score n'est
accessible qu'après l'avis, pour ne pas orienter la revue.

![Cas d'utilisation — Auditeur](uml/uc-04-auditeur.png)

### Investisseur

Catalogue et fiches ESG, comparaison, explication d'un score, gestion des portefeuilles, import de
positions, score agrégé et empreinte carbone PCAF.

![Cas d'utilisation — Investisseur](uml/uc-05-investisseur.png)

### Institution et Chercheur

Projets de recherche (périmètre, documents, affectations), analyses versionnées et validation
croisée sur des jeux de données de référence.

![Cas d'utilisation — Recherche](uml/uc-06-recherche.png)

## A.2 Diagrammes de classes

Chaque classe porte ses attributs et ses **méthodes**. Le code suit une architecture en couche de
services : les modèles SQLModel ne portent presque pas de méthodes, les opérations métier sont des
fonctions de service. Chaque fonction est rattachée à la classe qu'elle manipule, avec son module
d'origine en séparateur (`.. reporting/sessions.py ..`). Les signatures viennent du code ; l'objet
courant et les paramètres techniques (session de base, tâches de fond, IP) sont omis. Une méthode
soulignée est une opération de classe (création, calcul, recherche par jeton).

### Diagramme de classes essentiel (pour le rapport)

Une seule vue condensée : les 14 classes centrales, avec leurs attributs et méthodes clés.

![Diagramme de classes essentiel](uml/cl-00-essentiel.png)

### Modèle du domaine (vue globale, méthodes principales)

![Diagramme de classes global](uml/cl-01-domaine-global.png)

### Comptes, authentification et accès

![Classes — comptes et accès](uml/cl-02-comptes-acces.png)

### Entreprise (inscription, KYC, onboarding)

![Classes — entreprise](uml/cl-03-entreprise.png)

### Rapports ESG et extraction

`ESGMetric` et `CarbonEmission` partagent les colonnes de la « valeur extraite » (abstraction de
présentation : ce sont deux tables distinctes en base).

![Classes — rapports et extraction](uml/cl-04-rapports-extraction.png)

### Audit et scoring

`MetricReview` est en ajout seul (append-only).

![Classes — audit et scoring](uml/cl-05-audit-scoring.png)

### Investissement (portefeuilles et carbone PCAF)

![Classes — investissement](uml/cl-06-investissement.png)

### Recherche : projets et analyses

![Classes — projets et analyses](uml/cl-07-recherche.png)

### Recherche : validation croisée sur jeux de référence

![Classes — validation croisée](uml/cl-08-validation-croisee.png)

## A.3 Diagrammes de séquence

### Authentification et contrôle d'accès

![Séquence — authentification](uml/seq-01-authentification.png)

### Inscription d'une entreprise et onboarding

![Séquence — inscription entreprise](uml/seq-02-inscription-entreprise.png)

### Dépôt d'un rapport et extraction automatique

![Séquence — dépôt et extraction](uml/seq-03-depot-extraction.png)

### Affectation et audit d'un rapport

![Séquence — audit](uml/seq-04-audit.png)

### Validation et publication atomique du score

![Séquence — validation du score](uml/seq-05-validation-score.png)

### Import d'un portefeuille et analyse carbone PCAF

![Séquence — portefeuille et PCAF](uml/seq-06-portefeuille-pcaf.png)

## A.4 Diagrammes d'états-transitions

### Rapport ESG (`ReportStatus`)

![États — rapport](uml/st-01-rapport.png)

### Entreprise (`RegistrationStatus`)

![États — entreprise](uml/st-02-entreprise.png)

### Analyse d'un chercheur (`AnalysisStatus`)

![États — analyse](uml/st-03-analyse.png)

## A.5 Diagrammes d'activité

### Traitement d'un rapport, du dépôt à la publication (couloirs par acteur)

![Activité — traitement d'un rapport](uml/act-01-traitement-rapport.png)

### Pipeline d'extraction

![Activité — pipeline d'extraction](uml/act-02-pipeline-extraction.png)

## A.6 Diagramme de composants

![Composants](uml/cmp-01-composants.png)

## A.7 Diagramme de déploiement

![Déploiement](uml/dep-01-deploiement.png)

---

# Partie B — Vues complémentaires (Mermaid)

Les sources Mermaid sont dans [`src/`](src/). Pour régénérer un PNG (exemple) :

```bash
npx @mermaid-js/mermaid-cli -i src/01-architecture-systeme.mmd -o 01-architecture-systeme.png \
  -s 2 --size 2200 -b white -c src/mermaid-config.json
```

## 1. Architecture système (vue d'exécution)

Services `docker compose` (api, migrate, worker, worker-extraction, PostgreSQL + pgvector, Redis),
volumes partagés et services externes (Gemini, SMTP, GLEIF).

![Architecture système](01-architecture-systeme.png)

## 2. Modules du backend FastAPI

Modules « espace » qui exposent un router sous `/api/v1`, modules moteurs sans router
(ingestion, scoring, carbon, explainability), noyau transverse `app/core` et workers arq.

![Modules backend](02-modules-backend.png)

## 3. Schéma de la base de données (ER)

### 3.0 Vue d'ensemble

Les 31 tables SQLModel avec leurs clés primaires et étrangères et leurs colonnes principales.
Dense : à lire en zoomant ; pour une présentation, préférer les sous-schémas 3.1 à 3.5.

![Schéma de la base de données](03-schema-base-de-donnees.png)

Les sous-schémas suivants détaillent chaque domaine. Une table d'un autre domaine n'y figure
que par sa clé (`id`), pour montrer les liens sans la répéter.

### 3.1 Comptes, accès et traçabilité

Utilisateurs et rôles, jetons d'activation / réinitialisation / changement d'e-mail, demandes
d'accès, profils institution, affiliations chercheur, notifications et journal d'audit.

![Schéma BD — comptes et accès](03a-bd-comptes-acces.png)

### 3.2 Entreprises, rapports et extraction

Entreprises (inscription, identifiants, KYC), rapports ESG versionnés, exécutions d'extraction,
indicateurs, émissions carbone, preuves, couverture et anomalies.

![Schéma BD — entreprises et rapports](03b-bd-entreprises-rapports.png)

### 3.3 Audit et scoring

Revue append-only des valeurs, avis d'audit, configurations de pondération (YAML + hash) et scores
par pilier.

![Schéma BD — audit et scoring](03c-bd-audit-scoring.png)

### 3.4 Portefeuilles investisseurs

Portefeuilles (agrégats ESG et carbone) et positions rapprochées par ISIN / ticker, avec
conversion de devise.

![Schéma BD — portefeuilles](03d-bd-portefeuilles.png)

### 3.5 Recherche et institutions

Projets d'institution (périmètre, documents, chercheurs affectés), analyses versionnées et jeux de
données de référence pour la validation croisée.

![Schéma BD — recherche et institutions](03e-bd-recherche-institution.png)

## 4. Flux d'authentification

Activation du compte, connexion (limitation de débit, journal d'audit), cookies `__Host-` JWT et CSRF,
contrôle de chaque requête mutante et révocation des sessions par génération dans Redis.

![Flux d'authentification](04-flux-authentification.png)

## 5. Cycle de vie d'un rapport ESG

Les statuts `ReportStatus`, du brouillon à la validation, avec la revue d'audit et la publication
atomique du score.

![Cycle de vie d'un rapport](05-cycle-vie-rapport.png)

## 6. Pipeline d'extraction et de scoring (flux de données)

Dépôt du PDF, mise en file, pipeline Docling → bge-m3/FAISS → Gemini → preuves → couverture,
puis pré-score, audit et score officiel.

![Pipeline d'extraction](06-pipeline-extraction.png)

## 7. Inscription et cycle de vie d'une entreprise

`RegistrationStatus` : vérification de l'e-mail, onboarding avec revue KYC, demande d'informations,
rejet, activation et suspension.

![Cycle de vie entreprise](07-cycle-vie-entreprise.png)

## 8. Portefeuille investisseur et carbone PCAF

Import et rapprochement des positions, conversion de devises, agrégation du score ESG et calcul
PCAF (émissions financées, empreinte, WACI, qualité des données).

![Portefeuille et PCAF](08-flux-portefeuille-pcaf.png)

## 9. Structure des composants du frontend

Les features par espace, les composants partagés du système « Registre », et le client API
généré par Orval avec gestion CSRF.

![Structure frontend](09-structure-frontend.png)
