# Audit du diagramme de classes corrigé

Revue du 6 octobre 2026, fondée sur le code présent dans le dépôt. Le diagramme fourni a été reconstruit en document UML vectoriel, avec une source PlantUML modifiable. Aucun modèle applicatif, aucune migration et aucune donnée métier n'ont été modifiés.

## Livrables et périmètre

- [Diagramme complet, PDF vectoriel](Diagramme_classes_corrige.pdf)
- [Image haute résolution](Diagramme_classes_corrige.png)
- [SVG vectoriel](Diagramme_classes_corrige.svg)
- [Source PlantUML](Diagramme_classes_corrige.puml)
- [Six vues agrandies par domaine, PDF](Diagramme_classes_par_domaine.pdf)
- [Traçabilité des classes, attributs et associations](Tracabilite.md)

La vue représente 22 entités métier persistantes et l'énumération `Role`. Les noms français des classes sont des alias ; leur nom réel de code apparaît dans chaque cadre. Les attributs sélectionnés conservent leurs noms et types réels. Il s'agit d'une vue métier documentée, et non de la totalité des tables techniques. Les cadres pointillés sont des répétitions de la même classe destinées à limiter les croisements.

La classe **JeuDeDonnees** a été entièrement retirée de cette version, avec ses relations. Le sous-système de référence externe n'est pas représenté sous un autre nom. Cette suppression graphique demandée ne supprime pas la fonctionnalité de validation croisée ni ses modèles dans l'application. Les jetons d'authentification, demandes d'accès, notifications, journal transverse et signalements d'écart sont aussi hors de cette vue ; ils ne sont pas considérés comme inexistants.

## Propriété des entreprises : règle demandée et état du code

```text
Utilisateur « 0..1 » ───── propriétaire ───── « 0..* » Entreprise
```

La multiplicité placée du côté `Entreprise` compte les entreprises d'un utilisateur : **zéro à plusieurs**. La multiplicité du côté `Utilisateur` compte les propriétaires d'une entreprise : **zéro ou un**.

Le schéma déclaré autorise cette relation : `Company.owner_user_id` est nullable et sans contrainte d'unicité, avec une clé étrangère vers `User`. Voir [Company](../../../app/company/models.py#L43).

**Écart d'implémentation confirmé :** la propriété multiple n'est pas pleinement prise en charge par les parcours actuels. `User.company` est une relation scalaire, et plusieurs autorisations/routes utilisent directement cette entreprise unique. Voir [User.company](../../../app/auth/models.py#L64), [routes entreprise](../../../app/company/router.py#L205) et [périmètre des déclarations](../../../app/reporting/sessions.py#L57).

La cardinalité demandée est donc appliquée au diagramme et compatible avec la clé étrangère, sans prétendre que l'interface et les services gèrent déjà plusieurs entreprises par compte. Une adaptation applicative séparée devra remplacer la relation scalaire par une collection, identifier l'entreprise courante dans les parcours, vérifier la propriété de chaque ressource, puis revoir l'inscription, les suspensions et les notifications. Cette évolution n'a pas été effectuée dans cette tâche de modélisation.

## Corrections structurelles

| Élément de l'image initiale | Correction retenue | Justification |
|---|---|---|
| Cinq sous-classes de `Utilisateur`, avec `role` également présent | Une seule classe `Utilisateur` et une énumération à six valeurs, incluant `ENTERPRISE` | Le code ne définit pas d'héritage métier des comptes. Un compte a un rôle. [User](../../../app/auth/models.py#L30), [Role](../../../app/core/enums.py#L193). |
| `Portefeuille` hérite d'`Administrateur` | Association `Utilisateur 1 — 0..* Portefeuille`, avec titulaire de rôle `INVESTOR` | Un portefeuille est un objet détenu par un investisseur, pas un type d'administrateur. [Portfolio](../../../app/investor/models.py#L44). |
| `PositionPortefeuille` ne désigne aucune entreprise | Association `Entreprise 0..1 — 0..* PositionPortefeuille` | Une position importée peut rester non rapprochée. L'entreprise est présente si et seulement si `match_status = MATCHED`. [PortfolioPosition](../../../app/investor/models.py#L78). |
| `AffectationAudit` reliée à l'avis sans rapport explicite | Retrait de cette entité inexistante ; association auditeur facultatif–rapport, et date `assigned_at` sur le rapport | L'affectation courante est portée par `ESGReport.auditor_id`, pas par une table d'affectations. [Rapport](../../../app/ingestion/models.py#L101). |
| `AvisAudit` génère une affectation et inclut un score | Avis associé uniquement à son rapport et à son auteur auditeur dans cette vue | L'avis est une recommandation rendue avant la décision administrative. Le score est calculé séparément. [AuditOpinion](../../../app/audit/models.py#L29). |
| `RapportESG` exige `1..*` scores | `RapportESG 1 — 0..* ScoreESG` | Un brouillon ou rapport non validé peut ne pas avoir de score. Un score appartient à un seul rapport. [Score](../../../app/scoring/models.py#L88). |
| Score sans méthodologie | Ajout de `ConfigurationScore`, liée à chaque score | Chaque score utilise exactement une configuration. Unicité `(report_id, config_id)` ; contenu et empreinte conservés pour la reproductibilité. [ScoringConfig](../../../app/scoring/models.py#L29). |
| Deux entités `IndicateurESG` et `ValeurIndicateur` et valeur liée à plusieurs rapports | Fusion en `MesureESG` (`ESGMetric`) ; chaque mesure dépend exactement d'un rapport | Le modèle réel stocke code, pilier, valeur et unité sur la mesure. Unicité `(report_id, metric_code)`. Le référentiel de codes n'est pas une table d'indicateurs. [ESGMetric](../../../app/ingestion/models.py#L207). |
| Traçabilité documentaire absente | Ajout de `Preuve`, `ExecutionExtraction` et `CouvertureIndicateur` | Chaque mesure et émission a une preuve obligatoire ; l'exécution de provenance est facultative pour les données historiques. La couverture indique aussi les indicateurs non trouvés. [Modèles ingestion](../../../app/ingestion/models.py#L158). |
| Données carbone absentes | Ajout de `EmissionCarbone` distincte de `MesureESG` | Scope, tonnes CO₂e, année et qualité PCAF sont nécessaires au calcul carbone. [CarbonEmission](../../../app/ingestion/models.py#L269). |
| Correction d'une valeur sans historique | Ajout de `RevueValeur`, journal immuable | Une revue vise exactement une mesure ESG ou une émission carbone, conserve la valeur d'origine et une correction éventuelle. [MetricReview](../../../app/audit/models.py#L50). |
| `AffectationChercheur` reliée à `AvisAudit` | Relier l'affectation à un chercheur et à un projet | Chaque affectation a un projet et un chercheur obligatoires, couple unique. [ProjectAssignment](../../../app/institution/models.py#L64). |
| Projet sans institution responsable | Association `Utilisateur 1 — 0..* Projet`, rôle `INSTITUTION` | Un projet appartient à une institution. [Project](../../../app/institution/models.py#L26). |
| Analyse sans auteur | Association à un chercheur obligatoire et à un projet obligatoire | L'affectation donne le droit de rédiger, mais aucune clé `assignment_id` n'existe sur l'analyse. [Analysis](../../../app/researcher/models.py#L28). |
| Périmètre et documents de recherche absents | Ajout de `EntrepriseProjet` et `DocumentProjet` | Les entreprises autorisées et les rapports mis à disposition sont des liens persistants distincts. [Modèles institution](../../../app/institution/models.py#L84). |
| Entreprises comparées et sources de l'analyse absentes | Ajout de `EntrepriseAnalyse` | Chaque lien désigne une entreprise, avec le rapport et le score figés à l'ajout ; ces deux sources peuvent devenir nulles après suppression. [AnalysisCompany](../../../app/researcher/models.py#L62). |
| Invitations et quota non modélisés | Ajout de `RattachementChercheur` et `ProfilInstitution` | L'acceptation d'une invitation précède l'affectation. Le profil institutionnel porte le quota d'export, sans être une sous-classe de compte. [Modèles auth](../../../app/auth/models.py#L136). |
| Rapports et analyses sans version précédente | Autoassociations : précédent `0..1`, suivantes `0..*` selon le schéma | Une correction crée une nouvelle ligne. La FK précédente n'est pas unique ; ne pas inventer une cardinalité inverse `0..1`. |

## Attributs corrigés ou clarifiés

| Classe | Correction |
|---|---|
| Utilisateur | `name` facultatif, pas de prénom distinct ; mot de passe haché facultatif avant activation ; `role: Role`, pas chaîne libre ; aucun `updated_at` sur l'entité actuelle. |
| Entreprise | `tax_id` et `tax_id_type` remplacent le numéro d'enregistrement générique. ISIN/LEI facultatifs, uniques lorsqu'ils sont présents. Pas de `created_at`/`updated_at` dans ce modèle. `published_at` appartient à l'entreprise. |
| RapportESG | Pas de `titre` persistant. Type, exercice, statut, version, fichier et dates de soumission/affectation. `source_file` et `submitted_at` sont facultatifs pendant la préparation du brouillon. `original_filename` existe bien, mais n'est pas affiché dans la sélection courte. |
| RapportESG — finances | Chiffre d'affaires, EVIC et devises appartiennent au rapport/exercice ; ils ne doivent pas être placés comme chiffres intemporels sur l'entreprise. |
| MesureESG | Valeur extraite conservée, état de revue et valeur auditée facultative. Le commentaire et le motif de correction relèvent de la revue. |
| AvisAudit | Décision typée `AuditDecision`, commentaire facultatif, date de soumission. Pas de statut générique supplémentaire. |
| ScoreESG | Global obligatoire entre 0 et 100 ; piliers facultatifs, une absence de données n'étant pas un score de zéro. Couverture facultative entre 0 et 1. Les types réels de score sont `float` ; les montants monétaires sont `Decimal`. |
| Portefeuille | Nom, devise de référence, archivage et date de création. Pas de description persistante dans le modèle actuel. Des agrégats existent mais ne sont pas tous développés dans la vue. |
| PositionPortefeuille | Montant investi, devise, montant converti, poids facultatif, durée et dates ; pas de quantité de titres persistée. Le taux utilisé est conservé dans le modèle même si omis de la vue courte. |
| Projet | Nom, objectif, statut, échéance et clôture réelle ; le modèle distingue les dates prévues de la date de clôture. |
| AffectationChercheur | Date d'affectation ; pas de rôle propre à l'affectation. Le rôle appartient à l'utilisateur. |
| Analyse | Titre, contenu, statut typé, version, soumission et commentaire institutionnel ; les dates de création/décision existent aussi dans le modèle. |

Les classes affichent une sélection d'attributs : l'absence d'un champ réel du visuel ne signifie pas sa suppression. Les FK apparaissent par les associations et sont détaillées dans [Tracabilite.md](Tracabilite.md).

## Méthodes : séparer entités et services

Le diagramme fourni mélangeait attributs persistants et actions de cas d'utilisation. Les entités SQLModel ne possèdent pas les méthodes `authentifier()`, `calculer()` ou `publierEntreprise()` dessinées. Elles sont retirées des compartiments des entités afin que le diagramme soit fidèle au code. Les responsabilités restent assurées par les routes et fonctions suivantes.

| Opération initiale | Emplacement effectif / correction |
|---|---|
| Authentifier, mettre à jour le profil | `app/auth/router.py::login`, `modifier_mon_profil` et services d'authentification. |
| Désactiver un compte | `app/admin/utilisateurs.py::desactiver_utilisateur`, réservé à l'administrateur. |
| Modifier la fiche entreprise | `app/admin/review_queue.py::modifier_entreprise_admin`. Le propriétaire peut consulter sa fiche et modifier son compte personnel. |
| Déposer, joindre un fichier, soumettre | `app/reporting/sessions.py::ouvrir`, `joindre_fichier`, `soumettre` et `app/company/rapports.py`. |
| Affecter un auditeur | `app/audit/assignment.py::affecter_auditeur`. Pas de classe métier `AffectationAudit` ni d'opération de clôture sur cette classe. |
| Extraire une valeur | `app/ingestion/extractor.py::run_extraction_pipeline`. Une mesure ne s'extrait pas elle-même. |
| Corriger / accepter une valeur | `app/audit/revue.py::enregistrer_revue` : ajoute une entrée de journal et actualise l'état courant, sans écraser la valeur extraite. |
| Soumettre / mettre à jour un avis | `app/audit/opinion.py::soumettre_avis`. Pas de mise à jour libre d'un avis rendu dans le parcours actuel. |
| Décider d'un rapport | `app/admin/review_queue.py::valider_rapport`, `rejeter_rapport`, `demander_correction`. Seule la validation calcule le score officiel. |
| Calculer / recalculer le score | `app/scoring/engine.py::calculer_score` ; réparation exceptionnelle dans `app/admin/review_queue.py::recalculer_score`. |
| Publier une entreprise | `app/admin/review_queue.py::publier_entreprise`, après rapport validé et score existant. |
| Gérer les positions | `app/investor/portfolio.py::ajouter_position`, `modifier_position`, `fermer_position`, `supprimer_position` avec contrôles de période et de propriété. |
| Calculer l'empreinte carbone | `app/investor/carbon.py::empreinte_carbone` et moteur `app/carbon/pcaf.py`. Pas une méthode de persistance de PositionPortefeuille. |
| Créer un projet / affecter un chercheur | `app/institution/projets.py::creer_projet`, `affecter_chercheur`. Ne pas inventer `retirerChercheur()` : aucun parcours de désaffectation trouvé dans ce service. |
| Inviter un chercheur | `app/institution/chercheurs.py::inviter_chercheur`, puis réponse au rattachement côté chercheur. |
| Rédiger / soumettre / corriger une analyse | `app/researcher/analyses.py::creer_analyse`, `modifier_analyse`, `soumettre_analyse`, `corriger_analyse`. Modification d'un brouillon et nouvelle version corrigée sont distinctes. |

## Contraintes qui complètent les cardinalités

1. Chaque entreprise peut exister sans propriétaire. Les contrôles de rôle restent distincts de la cardinalité ; un compte `ENTERPRISE` n'est pas lui-même une entreprise.
2. Un rapport appartient à une entreprise, peut être sans auditeur avant affectation et sans score avant validation. Publication de l'entreprise et validation du rapport sont deux actions différentes.
3. Le schéma permet `0..*` avis par rapport. Le parcours courant n'accepte un avis que pendant `IN_AUDIT`, puis passe à `PENDING_DECISION` : au plus un avis par version via ce parcours. Une cardinalité du schéma ne doit pas être présentée comme une permission fonctionnelle.
4. Chaque revue vise exactement une mesure ESG **ou** une émission carbone, jamais les deux. Sa cible doit appartenir à son rapport. Toutes les valeurs doivent être revues avant l'avis ; le pré-score n'est accessible à l'auditeur qu'après celui-ci.
5. `ScoreESG` est unique par rapport/configuration. Les preuves peuvent être réutilisées ; leur partage interdit de les présenter arbitrairement comme des compositions exclusives d'une mesure.
6. Les positions non rapprochées sont conservées. `company_id` est présent si et seulement si l'état vaut `MATCHED`. L'archivage d'un portefeuille préserve son historique ; suppression/modification des positions est encadrée par le service.
7. Une affectation requiert un projet ouvert et un rattachement accepté à l'institution propriétaire. Le couple projet/chercheur est unique. Aucune FK directe ne relie l'affectation à un avis d'audit ou au rattachement.
8. Le schéma permet zéro lien d'entreprise sur une analyse, mais le service de création exige au moins une entreprise autorisée, publiée et scorée. Les sources choisies sont figées pour maintenir la reproductibilité.
9. Une institution ne voit pas les brouillons du chercheur. L'analyse soumise peut être validée ou recevoir une demande de correction ; celle-ci produit une nouvelle version en brouillon.
10. `ProfilInstitution` référence exactement un utilisateur ; un utilisateur en possède zéro ou un. Une institution peut être liée à plusieurs chercheurs et inversement via les rattachements.

## Vérifications réalisées

- Toutes les classes, les attributs affichés et les associations sont confrontés par AST aux modèles présents dans le dépôt, sans connexion à une base.
- Toutes les FK entre les 22 entités sélectionnées sont représentées une fois dans la source sémantique.
- La nullabilité et l'unicité des FK déterminent les cardinalités du schéma. Les contraintes supplémentaires des services sont décrites ci-dessus.
- Absence de la classe supprimée et de ses associations dans les exports ; contrôle de la relation propriétaire dans les deux sens.
- Validation XML du SVG, contrôle des cadres, ouverture du PDF et contrôle visuel des rendus et vues par domaine.
- Aucun test applicatif exécuté : le changement porte exclusivement sur la documentation et son générateur.

Reproduction : `.venv/Scripts/python.exe scripts/generate_corrected_class_diagram.py`. Le générateur réutilise le moteur vectoriel existant de `scripts/generate_class_diagram.py` sans modifier les anciens livrables.
