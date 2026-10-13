# Diagrammes retenus et constats sur l'implémentation

Analyse du dépôt au 6 octobre 2026. Le code courant constitue la référence ; les documents de conception servent à repérer les intentions et les écarts. Ce document sélectionne les prochaines représentations, sans les produire. Le seul visuel réalisé à cette étape est le diagramme de classes, livré séparément.

## Ensemble recommandé

Le socle comprend **huit diagrammes** : un diagramme de classes, un workflow proposé, deux cas d'utilisation, trois séquences et une architecture. Une activité spécifique et un déploiement peuvent compléter le rapport en annexe ; ils ne sont pas nécessaires à une soutenance courte.

| Représentation | Décision et périmètre | Valeur apportée |
|---|---|---|
| **Classes UML** | À produire maintenant : principales entités persistantes, attributs utiles, relations et cardinalités réellement contraintes. | Expliquer comment les données ESG, leurs preuves, leur audit et leurs usages sont reliés. |
| **Workflow du système proposé** | À retenir ensuite : parcours métier de l'inscription de l'entreprise à la publication, avec les couloirs Entreprise / Plateforme / Auditeur / Administrateur, puis consultation des résultats. | Montrer les responsabilités et les décisions humaines, l'analyse automatique, les retours en correction et la distinction validation/publication. |
| **Cas d'utilisation général** | À retenir : visiteur et six rôles existants — administrateur, entreprise, auditeur, investisseur, chercheur, institution. | Donner une vue d'ensemble des services accessibles, sans détailler chaque écran ni chaque route. |
| **Un cas d'utilisation détaillé** | À retenir : « Produire et publier une évaluation ESG », centré sur l'entreprise, l'auditeur et l'administrateur. | Préciser les droits distincts de dépôt, revue, avis, décision et publication. Les préconditions seront documentées ; aucune relation UML `include` ou `extend` ne sera déduite de la seule succession chronologique. |
| **Trois séquences** | À retenir : préparation/soumission d'un rapport ; revue/décision/publication ; import d'un portefeuille et consultation de ses indicateurs. Voir les scénarios ci-dessous. | Expliquer les échanges techniques critiques, les transactions et le traitement asynchrone, en complément du workflow métier. |
| **Architecture du système** | À retenir : frontend React, API FastAPI, PostgreSQL, Redis et deux workers ARQ, stockage local partagé, extraction documentaire et services externes réellement appelés. | Montrer les frontières de processus et les échanges ; distinguer composants internes, fichiers et services externes. |
| **Activité** | Annexe facultative, seulement pour « Soumettre et corriger une analyse de recherche ». | Ce processus Chercheur / Institution est distinct du parcours ESG. Une activité supplémentaire du rapport ESG ferait doublon avec le workflow proposé. |
| **Composants** | Non retenu comme visuel autonome. | Les modules peuvent être regroupés à l'intérieur du backend dans l'architecture. Un deuxième schéma des mêmes blocs apporterait peu d'information. |
| **Déploiement** | Annexe pertinente, limitée à la configuration Docker Compose effectivement versionnée. | Montrer les conteneurs API, worker général, worker d'extraction, migrations, PostgreSQL, Redis et les volumes partagés. Ne pas présenter cette configuration comme la preuve d'un hébergement en production observé. |
| **Workflow du système existant avant la solution** | Différé jusqu'à disposer d'une description du terrain validée. | Les documents évoquent la lecture manuelle de rapports, mais ne prouvent pas une chaîne organisationnelle précise, ses acteurs, ses outils, ses délais ou ses doublons. Les anciens états du logiciel décrits dans les documents ne sont pas le processus métier antérieur à la plateforme. |

Pour une soutenance courte, privilégier classes, workflow proposé, cas d'utilisation général, architecture et la séquence la plus utile à l'explication orale. Les autres visuels du socle restent disponibles dans le rapport.

## Les trois séquences à réaliser ensuite

### S1 — Préparer, analyser et soumettre un rapport ESG

L'entreprise ouvre un brouillon, joint un PDF, attend son analyse, consulte la complétude puis soumet explicitement le rapport. L'API vérifie le rôle, le périmètre et les règles d'exercice ; le PDF est enregistré, le traitement est mis en file après validation de la transaction. Le worker d'extraction exécute le pipeline, conserve l'exécution et les résultats, puis ramène le rapport non soumis à `DRAFT`. La soumission pose `submitted_at`, passe à `AWAITING_ASSIGNMENT` et déclenche les notifications et la synthèse.

Participants utiles : entreprise, frontend, API reporting, stockage, PostgreSQL, Redis/ARQ, worker d'extraction, service LLM. Montrer au minimum l'alternative analyse réussie/échouée et le refus d'une soumission avant une analyse réussie. Ne pas confondre ce parcours avec le dépôt en une étape, également disponible.

Preuves : [`app/reporting/router.py`](../../app/reporting/router.py), [`sessions.py`](../../app/reporting/sessions.py) (`ouvrir`, `joindre_fichier`, `soumettre`), [`app/company/rapports.py`](../../app/company/rapports.py) (`deposer_fichier`), [`app/worker/queue.py`](../../app/worker/queue.py), [`app/worker/jobs.py`](../../app/worker/jobs.py), [`app/ingestion/extractor.py`](../../app/ingestion/extractor.py) (`run_extraction_pipeline`), [`app/ingestion/etat_extraction.py`](../../app/ingestion/etat_extraction.py).

### S2 — Revoir les valeurs, décider et publier

Après affectation administrative, l'auditeur affecté accepte, corrige ou écarte les valeurs extraites. Chaque décision crée une entrée de revue et actualise l'état courant de la valeur. L'avis est refusé tant qu'il reste des valeurs non revues ; il ferme ensuite la revue en faisant passer le rapport à `PENDING_DECISION`. L'administrateur peut valider, rejeter ou demander une correction. La validation calcule le score officiel et enregistre ensemble score, statut et notification. La publication de l'entreprise est une **action administrative séparée**, qui exige un rapport validé muni d'un score.

Participants utiles : auditeur, administrateur, frontend, API audit/admin, moteur de score, PostgreSQL, file/worker de synthèse. Montrer la transaction de validation et l'alternative score incalculable/couverture insuffisante ; éviter une longue répétition des étapes d'extraction déjà couvertes par S1.

Preuves : [`app/audit/assignment.py`](../../app/audit/assignment.py) (`affecter_auditeur`), [`app/audit/revue.py`](../../app/audit/revue.py) (`enregistrer_revue`, `valeurs_non_revues`, `pre_score`), [`app/audit/opinion.py`](../../app/audit/opinion.py) (`soumettre_avis`), [`app/admin/review_queue.py`](../../app/admin/review_queue.py) (`_rapport_en_validation`, `valider_rapport`, `publier_entreprise`), [`app/scoring/engine.py`](../../app/scoring/engine.py) (`valeur_effective`, `calculer_score`).

### S3 — Importer un portefeuille et consulter ses résultats ESG/carbone

L'investisseur importe un CSV ou JSON dans un portefeuille vide. Le backend valide toutes les lignes, rapproche les identifiants, convertit les montants avec les taux configurés et enregistre les positions en une transaction ; une erreur de validation empêche l'ensemble de l'import. Les lignes sans entreprise rapprochée restent représentées avec leur état de rapprochement. Une consultation ultérieure calcule les agrégats ESG et les résultats carbone/PCAF à partir des positions et des rapports validés disponibles.

Participants utiles : investisseur, frontend, API investisseur, service d'import/rapprochement, conversion de devises, calcul ESG/carbone et PostgreSQL. Cette séquence reste synchrone : **aucun job `recompute_portfolio` n'est implémenté**. Les taux proviennent d'un fichier YAML configuré, pas d'un service de change en direct.

Preuves : [`app/investor/router.py`](../../app/investor/router.py) (`import_portfolio_positions`, `get_portfolio_carbon`), [`app/investor/importation.py`](../../app/investor/importation.py) (`importer_positions`), [`app/investor/portfolio.py`](../../app/investor/portfolio.py) (`resume_portefeuille`, `detail_portefeuille`), [`app/investor/fx.py`](../../app/investor/fx.py), [`app/investor/carbon.py`](../../app/investor/carbon.py) et [`app/carbon/pcaf.py`](../../app/carbon/pcaf.py).

## Règles vérifiées à conserver dans les représentations

- Les rôles sont des valeurs de `Role` portées par `User`, pas six sous-classes d'utilisateur : [`app/core/enums.py`](../../app/core/enums.py), [`app/auth/models.py`](../../app/auth/models.py).
- Inscription et publication sont distinctes. L'inscription publique crée une demande dont l'adresse doit être vérifiée ; l'administrateur examine ensuite la demande et l'approbation permet l'activation du compte. La publication est suivie par `Company.published_at` : [`app/company/registration.py`](../../app/company/registration.py), [`verification_email.py`](../../app/company/verification_email.py), [`app/admin/onboarding.py`](../../app/admin/onboarding.py), [`app/admin/review_queue.py`](../../app/admin/review_queue.py).
- Une entreprise doit être active pour déposer un rapport. Le code vérifie aussi les déclarations en cours et les exercices déjà validés : [`app/company/rapports.py`](../../app/company/rapports.py) (`verifier_entreprise_active`, `verifier_regles_exercice`).
- La revue des valeurs appartient à l'auditeur affecté ; la décision finale appartient à l'administrateur. Le pré-score n'est montré à l'auditeur qu'après l'avis : [`app/audit/revue.py`](../../app/audit/revue.py).
- Les valeurs corrigées interviennent dans le score ; une valeur déclarée `NOT_FOUND` est exclue. La configuration utilisée est persistée avec son contenu et son empreinte : [`app/scoring/engine.py`](../../app/scoring/engine.py), [`app/scoring/models.py`](../../app/scoring/models.py).
- Le parcours de recherche repose sur les affiliations, projets, affectations, périmètres d'entreprises et analyses versionnées. Une analyse brouillon est privée au chercheur ; l'institution décide après soumission : [`app/institution/projets.py`](../../app/institution/projets.py), [`app/researcher/analyses.py`](../../app/researcher/analyses.py), [`app/institution/analyses.py`](../../app/institution/analyses.py).
- L'API monte effectivement les routes d'authentification, demandes d'accès, contact, notifications, administration, audit, entreprise, reporting, explicabilité, investissement, recherche et institution : [`app/api/router.py`](../../app/api/router.py).

## Écarts documentaires à signaler

| Document ou intention | Constat dans le code courant | Conséquence graphique |
|---|---|---|
| `docs/WORKFLOWS.md`, §1.1, bloc « Current » : absence d'inscription publique. | Les routes `register_company`, `verify_registration_email` et le suivi public existent dans [`app/company/router.py`](../../app/company/router.py). | Représenter le parcours réellement implémenté, y compris la vérification d'adresse. |
| `docs/WORKFLOWS.md`, §1.2, bloc « Current » : anciens statuts français, absence de brouillon et de corrections auditeur. | `ReportStatus` est unifié ; `DRAFT`, `EXTRACTING`, `PENDING_DECISION` et la revue des valeurs sont présents. | Ignorer ces anciens blocs pour les états actuels. |
| `ARCHITECTURE.md`, §6 : `get_current_user` encore présenté comme un placeholder. | [`app/core/dependencies.py`](../../app/core/dependencies.py) valide le cookie d'accès, vérifie la révocation et charge un compte actif. | L'authentification est implémentée. |
| `ARCHITECTURE.md`, §2 : explicabilité présentée comme dépourvue de router. | [`app/explainability/router.py`](../../app/explainability/router.py) existe et est monté par l'API. | Tenir compte de cette surface API réelle. |
| `docs/WORKFLOWS.md`, §2.2–2.3 : recomposition du portefeuille par job ; `docs/ARCHITECTURE.md` précise ailleurs que ce job n'est pas implémenté. | Les agrégats sont calculés à la lecture. Les champs de cache existent dans `Portfolio`, mais aucun job de recomposition n'est enregistré dans [`app/worker/settings.py`](../../app/worker/settings.py). L'import courant exige un portefeuille vide. | Ne pas présenter un calcul asynchrone ni un remplacement général des positions comme disponibles. |
| Les fichiers d'architecture décrivent une cible de production. | [`docker-compose.yml`](../../docker-compose.yml) et [`docker-compose.prod.yml`](../../docker-compose.prod.yml) définissent les services backend et les volumes, mais pas un hébergeur réel ni un service frontend/reverse proxy déployé. | Distinguer configuration versionnée et infrastructure observée ; ne pas inventer cloud, domaine ou nœud d'hébergement. |

Enfin, le stockage applicatif implémenté est uniquement **local** ([`app/core/storage.py`](../../app/core/storage.py)). L'extraction utilise Docling, bge-m3/FAISS et Gemini ([`app/ingestion/extractor.py`](../../app/ingestion/extractor.py)) ; le code prévoit aussi un mode de démonstration lorsque la clé Gemini est un placeholder. Une représentation de l'architecture doit donc décrire les mécanismes disponibles sans prétendre qu'une exécution LLM réelle a été observée dans cette analyse statique.

La documentation de présentation évoque les difficultés de comparaison manuelle ([`docs/Presentation_GreenFinance_Scorer.md`](../Presentation_GreenFinance_Scorer.md), introduction). Cela justifie le besoin général, mais ne suffit pas à dessiner un workflow historique précis sans entretien, procédure ou autre source métier.
