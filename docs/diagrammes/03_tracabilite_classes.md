# Traçabilité du diagramme de classes

Généré depuis l’AST des modèles. Aucun accès à une base en exécution.

## Classes et attributs affichés

| Classe | Source | Attributs affichés |
|---|---|---|
| `User` | [app/auth/models.py:30](../../app/auth/models.py#L30) | `id` (L43), `email` (L44), `name` (L45), `role` (L53), `active` (L55) |
| `Company` | [app/company/models.py:30](../../app/company/models.py#L30) | `id` (L33), `name` (L34), `sector` (L35), `country` (L36), `status` (L40), `isin` (L62), `lei` (L63), `published_at` (L86) |
| `ESGReport` | [app/ingestion/models.py:43](../../app/ingestion/models.py#L43) | `id` (L78), `type` (L80), `channel` (L81), `fiscal_year` (L98), `status` (L86), `version` (L119), `submitted_at` (L85), `source_file` (L90), `official_score` (L137), `revenue` (L144), `enterprise_value` (L148) |
| `Score` | [app/scoring/models.py:77](../../app/scoring/models.py#L77) | `id` (L103), `global_score` (L107), `environmental_score` (L108), `social_score` (L109), `governance_score` (L110), `coverage_rate` (L111), `computed_at` (L112) |
| `ScoringConfig` | [app/scoring/models.py:29](../../app/scoring/models.py#L29) | `id` (L58), `name` (L59), `version` (L62), `content_yaml` (L63), `content_hash` (L64) |
| `ExtractionRun` | [app/ingestion/models.py:166](../../app/ingestion/models.py#L166) | `id` (L174), `status` (L178), `started_at` (L176), `finished_at` (L177), `llm_model` (L184), `prompt_version` (L185) |
| `MetricCoverage` | [app/ingestion/models.py:336](../../app/ingestion/models.py#L336) | `id` (L351), `metric_code` (L353), `status` (L354), `pages_examined` (L355) |
| `ESGMetric` | [app/ingestion/models.py:207](../../app/ingestion/models.py#L207) | `id` (L216), `pillar` (L218), `metric_code` (L219), `value` (L220), `unit` (L221), `method` (L222), `review_status` (L254), `audited_value` (L262) |
| `CarbonEmission` | [app/ingestion/models.py:269](../../app/ingestion/models.py#L269) | `id` (L288), `scope` (L290), `tonnes_co2e` (L293), `year` (L294), `method` (L295), `pcaf_data_quality` (L296), `review_status` (L322), `audited_value` (L330) |
| `Evidence` | [app/ingestion/models.py:188](../../app/ingestion/models.py#L188) | `id` (L194), `document_name` (L195), `year` (L196), `page_start` (L198), `page_end` (L199), `excerpt_pdf_path` (L201) |
| `AuditOpinion` | [app/audit/models.py:29](../../app/audit/models.py#L29) | `id` (L32), `decision` (L40), `comment` (L43), `submitted_at` (L44) |
| `MetricReview` | [app/audit/models.py:50](../../app/audit/models.py#L50) | `id` (L79), `decision` (L87), `original_value` (L89), `new_value` (L90), `reason` (L91), `created_at` (L96) |
| `Portfolio` | [app/investor/models.py:44](../../app/investor/models.py#L44) | `id` (L47), `name` (L51), `reference_currency` (L52), `archived` (L57), `created_at` (L53) |
| `PortfolioPosition` | [app/investor/models.py:70](../../app/investor/models.py#L70) | `id` (L85), `outstanding_amount` (L101), `currency` (L102), `converted_amount` (L111), `weight` (L114), `match_status` (L96), `duration_type` (L115), `start_date` (L118), `end_date` (L121) |
| `Project` | [app/institution/models.py:26](../../app/institution/models.py#L26) | `id` (L31), `name` (L33), `objective` (L37), `status` (L45), `deadline` (L44), `closed_at` (L51) |
| `ProjectAssignment` | [app/institution/models.py:60](../../app/institution/models.py#L60) | `id` (L70), `assigned_at` (L74) |
| `ProjectCompany` | [app/institution/models.py:80](../../app/institution/models.py#L80) | `id` (L89), `added_at` (L92) |
| `ProjectDocument` | [app/institution/models.py:98](../../app/institution/models.py#L98) | `id` (L106), `added_at` (L109) |
| `Analysis` | [app/researcher/models.py:28](../../app/researcher/models.py#L28) | `id` (L33), `title` (L37), `content` (L38), `status` (L39), `version` (L42), `submitted_at` (L49), `institution_comment` (L47) |
| `AnalysisCompany` | [app/researcher/models.py:57](../../app/researcher/models.py#L57) | `id` (L66), `report_id` (L75), `score_id` (L80) |
| `ResearcherAffiliation` | [app/auth/models.py:149](../../app/auth/models.py#L149) | `id` (L166), `status` (L170), `invited_at` (L173), `responded_at` (L174), `collaboration_terms` (L178) |
| `ReferenceDataset` | [app/researcher/models.py:88](../../app/researcher/models.py#L88) | `id` (L102), `name` (L104), `source_url` (L105), `licence` (L106), `scale_min` (L107), `scale_max` (L108), `higher_is_better` (L109) |
| `ReferenceDatasetRow` | [app/researcher/models.py:117](../../app/researcher/models.py#L117) | `id` (L129), `line_number` (L133), `isin` (L134), `lei` (L135), `environmental_score` (L137), `social_score` (L138), `governance_score` (L139), `total_score` (L140) |

## Associations affichées

Lecture : pour une instance de la classe source, la cible est obligatoire (1) ou optionnelle (0..1). La colonne inverse indique combien de sources une cible peut référencer.

| Source et FK réelle | Cible | Multiplicité cible | Inverse | Suppression SQL | Preuve |
|---|---|---|---|---|---|
| `Company.owner_user_id` | `User` | 0..1 | 0..* | SET NULL | [app/company/models.py:43](../../app/company/models.py#L43) |
| `Company.onboarded_by_id` | `User` | 0..1 | 0..* | SET NULL | [app/company/models.py:90](../../app/company/models.py#L90) |
| `ESGReport.company_id` | `Company` | 1 | 0..* | CASCADE | [app/ingestion/models.py:79](../../app/ingestion/models.py#L79) |
| `ESGReport.auditor_id` | `User` | 0..1 | 0..* | SET NULL | [app/ingestion/models.py:101](../../app/ingestion/models.py#L101) |
| `ESGReport.previous_report_id` | `ESGReport` | 0..1 | 0..* | SET NULL | [app/ingestion/models.py:120](../../app/ingestion/models.py#L120) |
| `ESGReport.declared_global_score_proof_id` | `Evidence` | 0..1 | 0..* | SET NULL | [app/ingestion/models.py:129](../../app/ingestion/models.py#L129) |
| `Score.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/scoring/models.py:104](../../app/scoring/models.py#L104) |
| `Score.config_id` | `ScoringConfig` | 1 | 0..* | RESTRICT | [app/scoring/models.py:106](../../app/scoring/models.py#L106) |
| `ScoringConfig.owner_user_id` | `User` | 0..1 | 0..* | RESTRICT | [app/scoring/models.py:69](../../app/scoring/models.py#L69) |
| `ExtractionRun.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/ingestion/models.py:175](../../app/ingestion/models.py#L175) |
| `MetricCoverage.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/ingestion/models.py:352](../../app/ingestion/models.py#L352) |
| `ESGMetric.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/ingestion/models.py:217](../../app/ingestion/models.py#L217) |
| `CarbonEmission.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/ingestion/models.py:289](../../app/ingestion/models.py#L289) |
| `ESGMetric.extraction_run_id` | `ExtractionRun` | 0..1 | 0..* | SET NULL | [app/ingestion/models.py:241](../../app/ingestion/models.py#L241) |
| `CarbonEmission.extraction_run_id` | `ExtractionRun` | 0..1 | 0..* | SET NULL | [app/ingestion/models.py:308](../../app/ingestion/models.py#L308) |
| `ESGMetric.proof_id` | `Evidence` | 1 | 0..* | CASCADE | [app/ingestion/models.py:223](../../app/ingestion/models.py#L223) |
| `CarbonEmission.proof_id` | `Evidence` | 1 | 0..* | CASCADE | [app/ingestion/models.py:297](../../app/ingestion/models.py#L297) |
| `AuditOpinion.auditor_id` | `User` | 1 | 0..* | RESTRICT | [app/audit/models.py:39](../../app/audit/models.py#L39) |
| `AuditOpinion.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/audit/models.py:33](../../app/audit/models.py#L33) |
| `MetricReview.auditor_id` | `User` | 1 | 0..* | RESTRICT | [app/audit/models.py:95](../../app/audit/models.py#L95) |
| `MetricReview.report_id` | `ESGReport` | 1 | 0..* | RESTRICT | [app/audit/models.py:80](../../app/audit/models.py#L80) |
| `MetricReview.metric_id` | `ESGMetric` | 0..1 | 0..* | RESTRICT | [app/audit/models.py:81](../../app/audit/models.py#L81) |
| `MetricReview.emission_id` | `CarbonEmission` | 0..1 | 0..* | RESTRICT | [app/audit/models.py:84](../../app/audit/models.py#L84) |
| `Portfolio.user_id` | `User` | 1 | 0..* | CASCADE | [app/investor/models.py:50](../../app/investor/models.py#L50) |
| `PortfolioPosition.portfolio_id` | `Portfolio` | 1 | 0..* | CASCADE | [app/investor/models.py:86](../../app/investor/models.py#L86) |
| `PortfolioPosition.company_id` | `Company` | 0..1 | 0..* | CASCADE | [app/investor/models.py:87](../../app/investor/models.py#L87) |
| `Project.institution_id` | `User` | 1 | 0..* | RESTRICT | [app/institution/models.py:32](../../app/institution/models.py#L32) |
| `ProjectAssignment.project_id` | `Project` | 1 | 0..* | CASCADE | [app/institution/models.py:72](../../app/institution/models.py#L72) |
| `ProjectAssignment.researcher_id` | `User` | 1 | 0..* | RESTRICT | [app/institution/models.py:73](../../app/institution/models.py#L73) |
| `ProjectCompany.project_id` | `Project` | 1 | 0..* | CASCADE | [app/institution/models.py:90](../../app/institution/models.py#L90) |
| `ProjectCompany.company_id` | `Company` | 1 | 0..* | CASCADE | [app/institution/models.py:91](../../app/institution/models.py#L91) |
| `ProjectDocument.project_id` | `Project` | 1 | 0..* | CASCADE | [app/institution/models.py:107](../../app/institution/models.py#L107) |
| `ProjectDocument.report_id` | `ESGReport` | 1 | 0..* | CASCADE | [app/institution/models.py:108](../../app/institution/models.py#L108) |
| `Analysis.project_id` | `Project` | 1 | 0..* | RESTRICT | [app/researcher/models.py:35](../../app/researcher/models.py#L35) |
| `Analysis.researcher_id` | `User` | 1 | 0..* | RESTRICT | [app/researcher/models.py:36](../../app/researcher/models.py#L36) |
| `Analysis.previous_analysis_id` | `Analysis` | 0..1 | 0..* | SET NULL | [app/researcher/models.py:44](../../app/researcher/models.py#L44) |
| `AnalysisCompany.analysis_id` | `Analysis` | 1 | 0..* | CASCADE | [app/researcher/models.py:68](../../app/researcher/models.py#L68) |
| `AnalysisCompany.company_id` | `Company` | 1 | 0..* | CASCADE | [app/researcher/models.py:69](../../app/researcher/models.py#L69) |
| `AnalysisCompany.report_id` | `ESGReport` | 0..1 | 0..* | SET NULL | [app/researcher/models.py:75](../../app/researcher/models.py#L75) |
| `AnalysisCompany.score_id` | `Score` | 0..1 | 0..* | SET NULL | [app/researcher/models.py:80](../../app/researcher/models.py#L80) |
| `ResearcherAffiliation.institution_id` | `User` | 1 | 0..* | CASCADE | [app/auth/models.py:169](../../app/auth/models.py#L169) |
| `ResearcherAffiliation.researcher_id` | `User` | 1 | 0..* | CASCADE | [app/auth/models.py:168](../../app/auth/models.py#L168) |
| `ReferenceDataset.owner_user_id` | `User` | 1 | 0..* | CASCADE | [app/researcher/models.py:103](../../app/researcher/models.py#L103) |
| `ReferenceDatasetRow.dataset_id` | `ReferenceDataset` | 1 | 0..* | CASCADE | [app/researcher/models.py:130](../../app/researcher/models.py#L130) |

## Classes non développées dans la vue de synthèse

Ces classes existent réellement. Leur omission est graphique ; l’inventaire JSON conserve leurs attributs, FK, méthodes et contraintes.

| Classe | Source |
|---|---|
| `AccessRequest` | [app/access_requests/models.py:24](../../app/access_requests/models.py#L24) |
| `AccountActivationToken` | [app/auth/models.py:100](../../app/auth/models.py#L100) |
| `AuditLogEntry` | [app/core/models.py:15](../../app/core/models.py#L15) |
| `DiscrepancyFlag` | [app/ingestion/models.py:360](../../app/ingestion/models.py#L360) |
| `EmailChangeRequest` | [app/auth/models.py:117](../../app/auth/models.py#L117) |
| `InstitutionProfile` | [app/auth/models.py:136](../../app/auth/models.py#L136) |
| `Notification` | [app/core/models.py:49](../../app/core/models.py#L49) |
| `PasswordResetToken` | [app/auth/models.py:80](../../app/auth/models.py#L80) |
