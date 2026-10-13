# Traçabilité du diagramme corrigé

Lecture statique du code du 6 octobre 2026. Aucun accès à une base en exécution.

Les types et attributs gardent leur nom dans le code. Les noms français sont des alias UML.

## Classes et attributs

| Classe UML | Classe réelle | Source | Attributs affichés |
|---|---|---|---|
| Utilisateur | `User` | [app/auth/models.py:30](../../../app/auth/models.py#L30) | `id`, `email`, `name`, `password_hash`, `role`, `active`, `created_at` |
| Entreprise | `Company` | [app/company/models.py:30](../../../app/company/models.py#L30) | `id`, `name`, `sector`, `country`, `status`, `tax_id`, `isin`, `lei`, `published_at` |
| RapportESG | `ESGReport` | [app/ingestion/models.py:43](../../../app/ingestion/models.py#L43) | `id`, `type`, `fiscal_year`, `status`, `version`, `source_file`, `submitted_at`, `assigned_at`, `revenue`, `revenue_currency`, `enterprise_value`, `enterprise_value_currency` |
| ScoreESG | `Score` | [app/scoring/models.py:77](../../../app/scoring/models.py#L77) | `id`, `global_score`, `environmental_score`, `social_score`, `governance_score`, `coverage_rate`, `computed_at` |
| ConfigurationScore | `ScoringConfig` | [app/scoring/models.py:29](../../../app/scoring/models.py#L29) | `id`, `name`, `version`, `content_yaml`, `content_hash` |
| ExecutionExtraction | `ExtractionRun` | [app/ingestion/models.py:166](../../../app/ingestion/models.py#L166) | `id`, `status`, `started_at`, `finished_at`, `llm_model`, `prompt_version` |
| CouvertureIndicateur | `MetricCoverage` | [app/ingestion/models.py:336](../../../app/ingestion/models.py#L336) | `id`, `metric_code`, `status`, `pages_examined` |
| MesureESG | `ESGMetric` | [app/ingestion/models.py:207](../../../app/ingestion/models.py#L207) | `id`, `pillar`, `metric_code`, `value`, `unit`, `method`, `review_status`, `audited_value` |
| EmissionCarbone | `CarbonEmission` | [app/ingestion/models.py:269](../../../app/ingestion/models.py#L269) | `id`, `scope`, `tonnes_co2e`, `year`, `method`, `pcaf_data_quality`, `review_status`, `audited_value` |
| Preuve | `Evidence` | [app/ingestion/models.py:188](../../../app/ingestion/models.py#L188) | `id`, `document_name`, `year`, `page_start`, `page_end`, `excerpt_pdf_path` |
| AvisAudit | `AuditOpinion` | [app/audit/models.py:29](../../../app/audit/models.py#L29) | `id`, `decision`, `comment`, `submitted_at` |
| RevueValeur | `MetricReview` | [app/audit/models.py:50](../../../app/audit/models.py#L50) | `id`, `decision`, `original_value`, `new_value`, `reason`, `created_at` |
| Portefeuille | `Portfolio` | [app/investor/models.py:44](../../../app/investor/models.py#L44) | `id`, `name`, `reference_currency`, `archived`, `created_at` |
| PositionPortefeuille | `PortfolioPosition` | [app/investor/models.py:70](../../../app/investor/models.py#L70) | `id`, `outstanding_amount`, `currency`, `converted_amount`, `weight`, `match_status`, `duration_type`, `start_date`, `end_date` |
| Projet | `Project` | [app/institution/models.py:26](../../../app/institution/models.py#L26) | `id`, `name`, `objective`, `status`, `deadline`, `closed_at` |
| AffectationChercheur | `ProjectAssignment` | [app/institution/models.py:60](../../../app/institution/models.py#L60) | `id`, `assigned_at` |
| EntrepriseProjet | `ProjectCompany` | [app/institution/models.py:80](../../../app/institution/models.py#L80) | `id`, `added_at` |
| DocumentProjet | `ProjectDocument` | [app/institution/models.py:98](../../../app/institution/models.py#L98) | `id`, `added_at` |
| Analyse | `Analysis` | [app/researcher/models.py:28](../../../app/researcher/models.py#L28) | `id`, `title`, `content`, `status`, `version`, `submitted_at`, `institution_comment` |
| EntrepriseAnalyse | `AnalysisCompany` | [app/researcher/models.py:57](../../../app/researcher/models.py#L57) | `id`, `report_id`, `score_id` |
| RattachementChercheur | `ResearcherAffiliation` | [app/auth/models.py:149](../../../app/auth/models.py#L149) | `id`, `status`, `invited_at`, `responded_at`, `collaboration_terms` |
| ProfilInstitution | `InstitutionProfile` | [app/auth/models.py:136](../../../app/auth/models.py#L136) | `id`, `export_quota` |

## Associations

La cardinalité cible indique combien de cibles une source peut référencer. L'inverse compte les sources pour une cible.

| Source | Clé étrangère | Cible | Cible | Inverse | Source code |
|---|---|---|---|---|---|
| Entreprise | `owner_user_id` | Utilisateur | 0..1 | 0..* | [app/company/models.py:43](../../../app/company/models.py#L43) |
| Entreprise | `onboarded_by_id` | Utilisateur | 0..1 | 0..* | [app/company/models.py:90](../../../app/company/models.py#L90) |
| RapportESG | `company_id` | Entreprise | 1 | 0..* | [app/ingestion/models.py:79](../../../app/ingestion/models.py#L79) |
| RapportESG | `auditor_id` | Utilisateur | 0..1 | 0..* | [app/ingestion/models.py:101](../../../app/ingestion/models.py#L101) |
| RapportESG | `previous_report_id` | RapportESG | 0..1 | 0..* | [app/ingestion/models.py:120](../../../app/ingestion/models.py#L120) |
| RapportESG | `declared_global_score_proof_id` | Preuve | 0..1 | 0..* | [app/ingestion/models.py:129](../../../app/ingestion/models.py#L129) |
| ScoreESG | `report_id` | RapportESG | 1 | 0..* | [app/scoring/models.py:104](../../../app/scoring/models.py#L104) |
| ScoreESG | `config_id` | ConfigurationScore | 1 | 0..* | [app/scoring/models.py:106](../../../app/scoring/models.py#L106) |
| ConfigurationScore | `owner_user_id` | Utilisateur | 0..1 | 0..* | [app/scoring/models.py:69](../../../app/scoring/models.py#L69) |
| ExecutionExtraction | `report_id` | RapportESG | 1 | 0..* | [app/ingestion/models.py:175](../../../app/ingestion/models.py#L175) |
| CouvertureIndicateur | `report_id` | RapportESG | 1 | 0..* | [app/ingestion/models.py:352](../../../app/ingestion/models.py#L352) |
| MesureESG | `report_id` | RapportESG | 1 | 0..* | [app/ingestion/models.py:217](../../../app/ingestion/models.py#L217) |
| EmissionCarbone | `report_id` | RapportESG | 1 | 0..* | [app/ingestion/models.py:289](../../../app/ingestion/models.py#L289) |
| MesureESG | `extraction_run_id` | ExecutionExtraction | 0..1 | 0..* | [app/ingestion/models.py:241](../../../app/ingestion/models.py#L241) |
| EmissionCarbone | `extraction_run_id` | ExecutionExtraction | 0..1 | 0..* | [app/ingestion/models.py:308](../../../app/ingestion/models.py#L308) |
| MesureESG | `proof_id` | Preuve | 1 | 0..* | [app/ingestion/models.py:223](../../../app/ingestion/models.py#L223) |
| EmissionCarbone | `proof_id` | Preuve | 1 | 0..* | [app/ingestion/models.py:297](../../../app/ingestion/models.py#L297) |
| AvisAudit | `auditor_id` | Utilisateur | 1 | 0..* | [app/audit/models.py:39](../../../app/audit/models.py#L39) |
| AvisAudit | `report_id` | RapportESG | 1 | 0..* | [app/audit/models.py:33](../../../app/audit/models.py#L33) |
| RevueValeur | `auditor_id` | Utilisateur | 1 | 0..* | [app/audit/models.py:95](../../../app/audit/models.py#L95) |
| RevueValeur | `report_id` | RapportESG | 1 | 0..* | [app/audit/models.py:80](../../../app/audit/models.py#L80) |
| RevueValeur | `metric_id` | MesureESG | 0..1 | 0..* | [app/audit/models.py:81](../../../app/audit/models.py#L81) |
| RevueValeur | `emission_id` | EmissionCarbone | 0..1 | 0..* | [app/audit/models.py:84](../../../app/audit/models.py#L84) |
| Portefeuille | `user_id` | Utilisateur | 1 | 0..* | [app/investor/models.py:50](../../../app/investor/models.py#L50) |
| PositionPortefeuille | `portfolio_id` | Portefeuille | 1 | 0..* | [app/investor/models.py:86](../../../app/investor/models.py#L86) |
| PositionPortefeuille | `company_id` | Entreprise | 0..1 | 0..* | [app/investor/models.py:87](../../../app/investor/models.py#L87) |
| Projet | `institution_id` | Utilisateur | 1 | 0..* | [app/institution/models.py:32](../../../app/institution/models.py#L32) |
| AffectationChercheur | `project_id` | Projet | 1 | 0..* | [app/institution/models.py:72](../../../app/institution/models.py#L72) |
| AffectationChercheur | `researcher_id` | Utilisateur | 1 | 0..* | [app/institution/models.py:73](../../../app/institution/models.py#L73) |
| EntrepriseProjet | `project_id` | Projet | 1 | 0..* | [app/institution/models.py:90](../../../app/institution/models.py#L90) |
| EntrepriseProjet | `company_id` | Entreprise | 1 | 0..* | [app/institution/models.py:91](../../../app/institution/models.py#L91) |
| DocumentProjet | `project_id` | Projet | 1 | 0..* | [app/institution/models.py:107](../../../app/institution/models.py#L107) |
| DocumentProjet | `report_id` | RapportESG | 1 | 0..* | [app/institution/models.py:108](../../../app/institution/models.py#L108) |
| Analyse | `project_id` | Projet | 1 | 0..* | [app/researcher/models.py:35](../../../app/researcher/models.py#L35) |
| Analyse | `researcher_id` | Utilisateur | 1 | 0..* | [app/researcher/models.py:36](../../../app/researcher/models.py#L36) |
| Analyse | `previous_analysis_id` | Analyse | 0..1 | 0..* | [app/researcher/models.py:44](../../../app/researcher/models.py#L44) |
| EntrepriseAnalyse | `analysis_id` | Analyse | 1 | 0..* | [app/researcher/models.py:68](../../../app/researcher/models.py#L68) |
| EntrepriseAnalyse | `company_id` | Entreprise | 1 | 0..* | [app/researcher/models.py:69](../../../app/researcher/models.py#L69) |
| EntrepriseAnalyse | `report_id` | RapportESG | 0..1 | 0..* | [app/researcher/models.py:75](../../../app/researcher/models.py#L75) |
| EntrepriseAnalyse | `score_id` | ScoreESG | 0..1 | 0..* | [app/researcher/models.py:80](../../../app/researcher/models.py#L80) |
| RattachementChercheur | `institution_id` | Utilisateur | 1 | 0..* | [app/auth/models.py:169](../../../app/auth/models.py#L169) |
| RattachementChercheur | `researcher_id` | Utilisateur | 1 | 0..* | [app/auth/models.py:168](../../../app/auth/models.py#L168) |
| ProfilInstitution | `user_id` | Utilisateur | 1 | 0..1 | [app/auth/models.py:143](../../../app/auth/models.py#L143) |
