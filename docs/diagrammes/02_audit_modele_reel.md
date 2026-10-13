# Audit du modèle réel — justification du diagramme de classes

Date de lecture : 6 octobre 2026. Périmètre : code source présent dans le dépôt, modèles SQLModel, migrations Alembic et services cités ci-dessous. Aucun code applicatif n'a été modifié pour cet audit.

Le diagramme décrit le modèle implémenté. Les cardinalités proviennent d'abord de la nullabilité des clés étrangères et des contraintes d'unicité. Les règles supplémentaires imposées par les services sont distinguées des garanties du schéma. Cette analyse du schéma versionné ne constitue pas une inspection d'une base de production : l'application effective des migrations à une instance distante n'est pas affirmée.

## 1. Périmètre de la vue synthétique

Le code définit **31 classes persistantes**, réparties dans dix fichiers `models.py`. Le diagramme principal en retient **23**, organisées par domaine :

| Domaine | Classes représentées | Source principale |
|---|---|---|
| Identité et collaboration | `User`, `ResearcherAffiliation` | [auth/models.py](../../app/auth/models.py#L30) |
| Entreprise | `Company` | [company/models.py](../../app/company/models.py#L30) |
| Rapports et extraction | `ESGReport`, `ExtractionRun`, `Evidence`, `ESGMetric`, `CarbonEmission`, `MetricCoverage` | [ingestion/models.py](../../app/ingestion/models.py#L43) |
| Audit | `AuditOpinion`, `MetricReview` | [audit/models.py](../../app/audit/models.py#L29) |
| Notation | `ScoringConfig`, `Score` | [scoring/models.py](../../app/scoring/models.py#L29) |
| Investissement | `Portfolio`, `PortfolioPosition` | [investor/models.py](../../app/investor/models.py#L44) |
| Projets institutionnels | `Project`, `ProjectAssignment`, `ProjectCompany`, `ProjectDocument` | [institution/models.py](../../app/institution/models.py#L26) |
| Recherche | `Analysis`, `AnalysisCompany`, `ReferenceDataset`, `ReferenceDatasetRow` | [researcher/models.py](../../app/researcher/models.py#L28) |

Les huit classes suivantes existent réellement, mais restent hors du visuel principal afin de conserver une lecture adaptée à la soutenance. Elles restent dans l'inventaire exhaustif :

| Classe écartée du visuel | Motif de sélection | Relations à conserver dans l'inventaire |
|---|---|---|
| `PasswordResetToken` | Détail du mécanisme d'authentification | Un `User` obligatoire par jeton ; plusieurs jetons possibles ; hash unique. [auth/models.py:80](../../app/auth/models.py#L80) |
| `AccountActivationToken` | Détail de l'activation | Même structure de rattachement à `User`. [auth/models.py:100](../../app/auth/models.py#L100) |
| `EmailChangeRequest` | Détail du changement d'identifiant | Un `User` obligatoire ; plusieurs demandes possibles ; hash unique. [auth/models.py:117](../../app/auth/models.py#L117) |
| `InstitutionProfile` | Complément réduit au quota d'export | Un `User` obligatoire, FK unique : au plus un profil par utilisateur. [auth/models.py:136](../../app/auth/models.py#L136) |
| `AccessRequest` | Sous-processus d'inscription | Un demandeur obligatoire et unique ; un décideur optionnel, tous deux `User`. [access_requests/models.py:24](../../app/access_requests/models.py#L24) |
| `Notification` | Support transverse | Un destinataire `User` obligatoire ; `resource_id` n'est pas une FK. [core/models.py:49](../../app/core/models.py#L49) |
| `AuditLogEntry` | Journal technique transverse | Acteur `User` optionnel ; `resource_id` n'est pas une FK. [core/models.py:15](../../app/core/models.py#L15) |
| `DiscrepancyFlag` | Détail du signalement d'écart | Un `ESGMetric` et une `Company` obligatoires. [ingestion/models.py:360](../../app/ingestion/models.py#L360) |

L'absence de ces classes du visuel ne signifie pas que leurs fonctionnalités sont absentes du système.

## 2. Héritage, méthodes et notation UML

Toutes les classes persistantes héritent directement de `SQLModel`. Cet héritage technique commun est indiqué par une note générale ; il ne justifie pas de dessiner une classe mère métier artificielle.

Il n'existe pas de sous-classes persistantes `Administrateur`, `Auditeur`, `Investisseur`, `Chercheur`, `Institution` ou `Entreprise` dérivées de `User`. Les six rôles sont les valeurs de `Role`, portées par `User.role` : `ADMIN`, `ENTERPRISE`, `AUDITOR`, `INVESTOR`, `RESEARCHER`, `INSTITUTION`. Sources : [auth/models.py:53](../../app/auth/models.py#L53), [core/enums.py:193](../../app/core/enums.py#L193). `Company` est une entité distincte d'un compte `User` de rôle `ENTERPRISE`.

Les opérations métier sont principalement des fonctions de services, pas des méthodes des entités. Par exemple, `calculer_score()` est une fonction de [scoring/engine.py:288](../../app/scoring/engine.py#L288), et `soumettre_analyse()` une fonction de [researcher/analyses.py:194](../../app/researcher/analyses.py#L194). Elles ne doivent donc pas être ajoutées comme opérations de `Score` ou `Analysis`.

Les seules méthodes définies directement dans les classes persistantes sont les validateurs internes `PortfolioPosition._valider_regles_duree()` et `PortfolioPosition._valider_montant_minimum(info)`, dans [investor/models.py:127](../../app/investor/models.py#L127) et [investor/models.py:161](../../app/investor/models.py#L161). Leur omission du visuel synthétique évite de donner aux seuls détails de validation une importance disproportionnée.

**Choix graphique : associations simples par défaut.** Une FK avec `ON DELETE CASCADE` décrit un comportement de suppression ; elle ne suffit pas, à elle seule, à établir une composition UML. La seule composition retenue est `ReferenceDataset`–`ReferenceDatasetRow` : une ligne appartient à un jeu obligatoire et la relation ORM déclare explicitement `cascade="all, delete-orphan"` ([researcher/models.py:112](../../app/researcher/models.py#L112), [researcher/models.py:130](../../app/researcher/models.py#L130)). Aucune agrégation partagée n'est ajoutée par convention esthétique.

## 3. Cardinalités justifiées des classes représentées

Dans les tableaux suivants, « parent par enfant » indique combien de parents peut référencer une ligne enfant. L'inverse est `0..*` sauf indication contraire. Les noms de colonnes permettent de distinguer les multiples associations vers une même classe.

### Identité, rapports et extraction

| Enfant → parent | Parent par enfant | Justification |
|---|---|---|
| `Company` → `User` par `owner_user_id` | `0..1` | FK nullable, sans unicité ; inverse `0..*` en base. [company/models.py:43](../../app/company/models.py#L43) |
| `Company` → `User` par `onboarded_by_id` | `0..1` | Validateur de l'inscription optionnel. [company/models.py:90](../../app/company/models.py#L90) |
| `ResearcherAffiliation` → `User` par `researcher_id` | `1` | FK obligatoire. [auth/models.py:168](../../app/auth/models.py#L168) |
| `ResearcherAffiliation` → `User` par `institution_id` | `1` | FK obligatoire ; couple chercheur/institution unique. [auth/models.py:160](../../app/auth/models.py#L160) |
| `ESGReport` → `Company` | `1` | FK obligatoire. [ingestion/models.py:79](../../app/ingestion/models.py#L79) |
| `ESGReport` → `User` par `auditor_id` | `0..1` | Un rapport peut être en attente d'affectation. [ingestion/models.py:101](../../app/ingestion/models.py#L101) |
| `ESGReport` → `ESGReport` par `previous_report_id` | `0..1` | FK nullable et non unique ; inverse `0..*`. [ingestion/models.py:120](../../app/ingestion/models.py#L120) |
| `ESGReport` → `Evidence` par `declared_global_score_proof_id` | `0..1` | Preuve optionnelle du score global déclaré seulement. [ingestion/models.py:129](../../app/ingestion/models.py#L129) |
| `ExtractionRun` → `ESGReport` | `1` | Une ligne par tentative d'extraction ; plusieurs tentatives possibles. [ingestion/models.py:166](../../app/ingestion/models.py#L166) |
| `ESGMetric` → `ESGReport` | `1` | FK obligatoire ; couple rapport/code unique. [ingestion/models.py:212](../../app/ingestion/models.py#L212) |
| `ESGMetric` → `Evidence` | `1` | `proof_id` obligatoire. [ingestion/models.py:223](../../app/ingestion/models.py#L223) |
| `ESGMetric` → `ExtractionRun` | `0..1` | Champ nullable, notamment pour les lignes antérieures à sa création. [ingestion/models.py:241](../../app/ingestion/models.py#L241) |
| `CarbonEmission` → `ESGReport` | `1` | FK obligatoire. [ingestion/models.py:289](../../app/ingestion/models.py#L289) |
| `CarbonEmission` → `Evidence` | `1` | `proof_id` obligatoire. [ingestion/models.py:297](../../app/ingestion/models.py#L297) |
| `CarbonEmission` → `ExtractionRun` | `0..1` | FK nullable. [ingestion/models.py:308](../../app/ingestion/models.py#L308) |
| `MetricCoverage` → `ESGReport` | `1` | FK obligatoire ; couple rapport/code unique. [ingestion/models.py:347](../../app/ingestion/models.py#L347) |

`Evidence` ne contient **aucune FK `report_id`** : elle est référencée par les valeurs extraites et éventuellement par le score global déclaré. Une preuve peut être référencée par plusieurs métriques ou émissions ; aucune unicité de `proof_id` ne limite cette réutilisation. Ne pas dessiner une appartenance exclusive d'`Evidence` à `ESGReport` ([ingestion/models.py:188](../../app/ingestion/models.py#L188)).

### Audit et notation

| Enfant → parent | Parent par enfant | Justification |
|---|---|---|
| `AuditOpinion` → `ESGReport` | `1` | FK obligatoire, sans unicité : plusieurs avis peuvent être conservés. [audit/models.py:33](../../app/audit/models.py#L33) |
| `AuditOpinion` → `User` par `auditor_id` | `1` | Auteur obligatoire ; suppression RESTRICT. [audit/models.py:39](../../app/audit/models.py#L39) |
| `MetricReview` → `ESGReport` | `1` | Rapport obligatoire, RESTRICT. [audit/models.py:80](../../app/audit/models.py#L80) |
| `MetricReview` → `User` par `auditor_id` | `1` | Auteur obligatoire, RESTRICT. [audit/models.py:95](../../app/audit/models.py#L95) |
| `MetricReview` → `ESGMetric` | `0..1` | FK nullable ; exclusivité avec `emission_id`. [audit/models.py:81](../../app/audit/models.py#L81) |
| `MetricReview` → `CarbonEmission` | `0..1` | FK nullable ; exclusivité avec `metric_id`. [audit/models.py:84](../../app/audit/models.py#L84) |
| `Score` → `ESGReport` | `1` | FK obligatoire. [scoring/models.py:104](../../app/scoring/models.py#L104) |
| `Score` → `ScoringConfig` | `1` | FK obligatoire, RESTRICT ; couple rapport/configuration unique. [scoring/models.py:91](../../app/scoring/models.py#L91) |
| `ScoringConfig` → `User` par `owner_user_id` | `0..1` | Configuration de référence si nul, personnalisée sinon. [scoring/models.py:69](../../app/scoring/models.py#L69) |

La contrainte de `MetricReview` impose **exactement une cible**, métrique ESG **ou** émission carbone : `(metric_id IS NULL) <> (emission_id IS NULL)`. Les deux associations optionnelles doivent être accompagnées d'une note `{xor, une cible obligatoire}` ; seules, leurs cardinalités seraient incomplètes ([audit/models.py:61](../../app/audit/models.py#L61)).

Un `Score` n'est pas unique par rapport : il est unique **par rapport et configuration**. Les scores E/S/G sont optionnels lorsque les données d'un pilier manquent ; `global_score` est obligatoire. Les champs de score sont bornés entre 0 et 100, et `coverage_rate` entre 0 et 1 ([scoring/models.py:88](../../app/scoring/models.py#L88)).

### Investissement et recherche

| Enfant → parent | Parent par enfant | Justification |
|---|---|---|
| `Portfolio` → `User` | `1` | Propriétaire obligatoire, plusieurs portefeuilles possibles. [investor/models.py:50](../../app/investor/models.py#L50) |
| `PortfolioPosition` → `Portfolio` | `1` | FK obligatoire. [investor/models.py:86](../../app/investor/models.py#L86) |
| `PortfolioPosition` → `Company` | `0..1` | Une position importée peut rester non rapprochée. [investor/models.py:87](../../app/investor/models.py#L87) |
| `Project` → `User` par `institution_id` | `1` | Institution obligatoire, RESTRICT. [institution/models.py:32](../../app/institution/models.py#L32) |
| `ProjectAssignment` → `Project` | `1` | FK obligatoire. [institution/models.py:72](../../app/institution/models.py#L72) |
| `ProjectAssignment` → `User` par `researcher_id` | `1` | Couple projet/chercheur unique. [institution/models.py:64](../../app/institution/models.py#L64) |
| `ProjectCompany` → `Project` et → `Company` | `1` chacune | Deux FK obligatoires ; couple unique. [institution/models.py:85](../../app/institution/models.py#L85) |
| `ProjectDocument` → `Project` et → `ESGReport` | `1` chacune | Deux FK obligatoires ; couple unique. [institution/models.py:102](../../app/institution/models.py#L102) |
| `Analysis` → `Project` et → `User` par `researcher_id` | `1` chacune | Deux FK obligatoires, RESTRICT. [researcher/models.py:35](../../app/researcher/models.py#L35) |
| `Analysis` → `Analysis` par `previous_analysis_id` | `0..1` | FK nullable, non unique : inverse `0..*`. [researcher/models.py:44](../../app/researcher/models.py#L44) |
| `AnalysisCompany` → `Analysis` et → `Company` | `1` chacune | Deux FK obligatoires ; couple unique. [researcher/models.py:62](../../app/researcher/models.py#L62) |
| `AnalysisCompany` → `ESGReport` et → `Score` | `0..1` chacune | Sources figées à l'ajout, FK nullable et SET NULL. [researcher/models.py:70](../../app/researcher/models.py#L70) |
| `ReferenceDataset` → `User` par `owner_user_id` | `1` | Auteur obligatoire. [researcher/models.py:103](../../app/researcher/models.py#L103) |
| `ReferenceDatasetRow` → `ReferenceDataset` | `1` | FK obligatoire et gestion ORM des orphelins ; composition retenue. [researcher/models.py:112](../../app/researcher/models.py#L112) |

Les tables de liaison sont des classes persistantes réelles : les supprimer du diagramme au profit d'une simple relation plusieurs-à-plusieurs ferait perdre leurs attributs et, pour `AnalysisCompany`, la traçabilité du rapport et du score utilisés.

## 4. Contraintes et règles métier à ne pas confondre

| Sujet | Garantie du schéma | Règle supplémentaire du service |
|---|---|---|
| Déclarations ESG | Unicité entreprise/checksum ; unicité partielle entreprise/exercice/type pour un rapport non soumis. [ingestion/models.py:53](../../app/ingestion/models.py#L53) | Contrôle des déclarations actives et exercices déjà validés dans [company/rapports.py:115](../../app/company/rapports.py#L115). Ne pas transformer cela en unicité générale entreprise/exercice. |
| Affectation d'un chercheur | Unicité projet/chercheur. [institution/models.py:64](../../app/institution/models.py#L64) | Rattachement à l'institution accepté et projet ouvert exigés dans [institution/projets.py:100](../../app/institution/projets.py#L100). Il n'existe pas de FK d'affectation vers `ResearcherAffiliation`. |
| Création d'une analyse | Projet et chercheur obligatoires ; aucune FK `assignment_id`. [researcher/models.py:35](../../app/researcher/models.py#L35) | `_projet_affecte()` vérifie l'affectation existante. [researcher/analyses.py:31](../../app/researcher/analyses.py#L31) |
| Entreprises d'une analyse | Le schéma permet `0..*` liens `AnalysisCompany`. | Le service exige au moins une entreprise, dans le périmètre du projet, publiée, avec rapport validé et score officiel identifiables. [researcher/analyses.py:48](../../app/researcher/analyses.py#L48) |
| Sources d'une analyse | `report_id` et `score_id` sont optionnels en base, notamment après une suppression SET NULL. | Le service choisit et enregistre ces deux sources lors de l'ajout ; le chercheur ne fournit pas lui-même leurs identifiants. [researcher/analyses.py:99](../../app/researcher/analyses.py#L99) |
| Positions importées | `company_id` renseigné si et seulement si `match_status = MATCHED`. [investor/models.py:78](../../app/investor/models.py#L78) | Les imports non rapprochés restent représentables ; ne pas imposer une entreprise obligatoire sur le visuel. |
| Versionnement | Au plus un prédécesseur par rapport/analyse ; aucun index unique sur le prédécesseur. | Les services construisent des chaînes avec `version+1`. [company/rapports.py:296](../../app/company/rapports.py#L296), [researcher/analyses.py:232](../../app/researcher/analyses.py#L232). Le schéma seul ne garantit pas au plus un successeur. |
| Valeurs auditées | Valeur extraite et valeur auditée sont deux champs distincts ; historique séparé. [ingestion/models.py:254](../../app/ingestion/models.py#L254) | Le calcul utilise la valeur corrigée si `OVERRIDDEN`, écarte la valeur si `NOT_FOUND`, conserve la valeur extraite sinon. [scoring/engine.py:129](../../app/scoring/engine.py#L129) |

`MetricReview` conserve une ligne par décision et interdit la décision `PENDING`. La présence de `new_value` équivaut à `OVERRIDDEN`, et une raison est exigée sauf pour `ACCEPTED` ([audit/models.py:60](../../app/audit/models.py#L60)). Son caractère append-only est également imposé par les triggers PostgreSQL interdisant UPDATE, DELETE et TRUNCATE dans [la migration e3b8c5d1f9a2:70](../../alembic/versions/e3b8c5d1f9a2_task_5_6_metric_review_log.py#L70).

`ReferenceDatasetRow` ne possède aucune FK vers `Company`. Ses identifiants ISIN/LEI servent au rapprochement ; au moins l'un des deux doit être présent. Il serait faux de dessiner une association persistante directe vers une entreprise ([researcher/models.py:123](../../app/researcher/models.py#L123)).

Les montants financiers de `PortfolioPosition` et les montants financiers des rapports sont des `Decimal` stockés en `Numeric` ; les scores sont des `float`. Les émissions sont exprimées par `tonnes_co2e`, avec scope 1, 2 ou 3, et une qualité PCAF optionnelle de 1 à 5 ([investor/models.py:101](../../app/investor/models.py#L101), [ingestion/models.py:144](../../app/ingestion/models.py#L144), [ingestion/models.py:279](../../app/ingestion/models.py#L279)).

## 5. Écarts et limites relevés

1. **Relation utilisateur/entreprise : intention ORM plus restrictive que le schéma.** `User.company` est déclaré scalaire et optionnel ([auth/models.py:64](../../app/auth/models.py#L64)), mais `Company.owner_user_id` n'a pas de contrainte d'unicité ([company/models.py:43](../../app/company/models.py#L43)). Le schéma autorise donc `0..*` entreprises par utilisateur et `0..1` propriétaire par entreprise. Le diagramme conserve cette cardinalité et signale l'écart ; il n'invente pas un un-à-un garanti.

2. **`AnalysisCompany.company` est annotée optionnelle malgré une FK obligatoire.** Le champ `company_id` est non nullable ([researcher/models.py:69](../../app/researcher/models.py#L69)), tandis que la relation est `Optional[Company]` ([researcher/models.py:85](../../app/researcher/models.py#L85)). La cardinalité retenue est `1`, conformément au schéma.

3. **« Rattachée à l'affectation » décrit une règle de service.** Le commentaire d'ouverture de [researcher/models.py](../../app/researcher/models.py#L1) ne correspond pas à une FK directe vers `ProjectAssignment`. L'autorisation est vérifiée à partir du couple projet/chercheur. Le diagramme conserve uniquement les associations présentes dans le modèle.

4. **Les noms historiques de la documentation et des migrations ne sont pas des classes supplémentaires.** Les tables et classes françaises d'anciennes migrations ont été renommées. Le [plan de renommage](../RENAME_PLAN.md#L156) garde volontairement ces correspondances. Les noms anglais des modèles actuels constituent la référence du diagramme.

5. **Certaines formulations documentaires résument un état antérieur.** La décision D5 de [docs/ARCHITECTURE.md:338](../ARCHITECTURE.md#L338) indique un démarrage d'inscription à `PENDING_ONBOARDING`, alors que le flux actuel ajoute `EMAIL_VERIFICATION_PENDING`, décrit dans [docs/WORKFLOWS.md:38](../WORKFLOWS.md#L38) et présent dans [core/enums.py:68](../../app/core/enums.py#L68). Il faut utiliser les états actuels lors des prochains workflows.

6. **Les dates décrites comme `timestamptz` dans certains tableaux documentaires ne changent pas les types réels.** Par exemple, [docs/ARCHITECTURE.md:82](../ARCHITECTURE.md#L82) utilise ce libellé pour `published_at`, alors que le modèle utilise `datetime` et que `utcnow()` produit explicitement un UTC naïf cohérent avec `TIMESTAMP WITHOUT TIME ZONE` ([core/database.py:14](../../app/core/database.py#L14)). Le diagramme conserve le type applicatif `datetime`.

Ces observations documentent l'implémentation existante. Elles ne constituent ni des corrections appliquées au projet, ni des fonctionnalités ajoutées au diagramme.
