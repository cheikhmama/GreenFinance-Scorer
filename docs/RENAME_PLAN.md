# English Domain Rename Plan (decision D3)

The French domain model is renamed to English **module by module**, together with each phase's
refactoring, never as one big-bang change. This file is the single glossary: before renaming
anything, add or check its row here; after a rename lands, tick it.

## 1. Boundary rules

1. **Layers renamed together.** For a renamed entity, these change in the same commit: the table,
   its columns, the SQLModel class and attributes, its relationships, its enums, the domain code
   that uses them, the tests, and the scripts under `scripts/`.
2. **Inbound foreign-key columns follow their own table.** `score_esg.rapport_id` keeps its name
   until the scoring tables are renamed (task 3.1); only its `ON DELETE` rule and index are fixed
   when the referenced table is renamed. Relationship attributes on a not-yet-renamed class
   (e.g. `Utilisateur.entreprise`) likewise keep their name.
3. **The HTTP contract changes only when its endpoints are redesigned.** Response schemas keep
   their French JSON field names and translate the English model explicitly, in one function per
   entity (`company_vers_contrat` / `CompanyContractMixin` in `app/company/schemas.py`,
   `rapport_vers_contrat` and `IndicateurESGDetail` in `app/ingestion/schemas.py`), so the frontend
   doesn't change during a persistence rename. Request schemas keep their French fields and the
   service code maps them. The English JSON contract arrives with the redesigned endpoints
   (tasks 1.3–1.5, 2.2, 3.2) and, for the rest, task 4.7.
   - *Exceptions (task 1.1):* report status **values** change in the API (`statut` now carries
     `ReportStatus`), and reports gain `statut_extraction` (`ExtractionStatus`) — the frontend
     needs both to tell a queued report from one being extracted. Company `actif` stays a boolean
     in the API (true only for `ACTIVE`); task 1.3 adds `statut` (`CompanyStatus`) next to it.
   - New endpoints use English JSON from the start (first one: `POST /companies/register`,
     task 1.3).
4. **One consolidated migration per task**, with a working `downgrade()` that restores the
   previous names, values and constraints. Data transformations (status mapping) are written in
   SQL inside that migration, in both directions.
5. **Every foreign key touched gets an explicit `ON DELETE`** (`CASCADE` for rows that only
   exist as part of their parent, `SET NULL` for optional references) **and an index** on the
   referencing column.
6. **LLM contracts are not renamed.** `IndicateurExtrait` / `ExtractionEntreprise`
   (`app/ingestion/schemas.py`) are the validated Gemini tool-calling schema; they are
   translated at the persistence boundary, not changed.

## 2. Task 1.1 — Company, ESG report, ESG metric ✅

Landed in migration `21e17187789f` (upgrade/downgrade round-trip and `alembic check` verified).

### 2.1 `entreprise` → `companies` (`Entreprise` → `Company`)

| Current | Target | Note |
|---|---|---|
| `nom` | `name` | |
| `secteur` | `sector` | |
| `pays` | `country` | free text until task 1.3 |
| `logo`, `description` | unchanged | |
| `site_officiel` | `website` | |
| `actif` (bool) | `status` (`CompanyStatus`) | `false` → `SUSPENDED`, `true` → `ACTIVE` |
| `utilisateur_id` | `owner_user_id` | `ON DELETE SET NULL` |
| `montant_minimum_investissement` | `minimum_investment_amount` | |
| `devise_montant_minimum` | `minimum_investment_currency` | |
| `date_publication` | `published_at` | |
| — | `isin`, `lei` | new, unique when present, check digits validated |
| — | `revenue`, `revenue_currency` | new, `numeric(20,2)` |
| — | `enterprise_value`, `enterprise_value_currency`, `enterprise_value_as_of` | new (EVIC for PCAF) |
| rel. `utilisateur` / `rapports` / `signalements_ecart` | `owner` / `reports` / `discrepancy_flags` | `positions` unchanged |

### 2.2 `rapport_esg` → `esg_reports` (`RapportESG` → `ESGReport`)

| Current | Target | Note |
|---|---|---|
| `entreprise_id` | `company_id` | `ON DELETE CASCADE`; index `(company_id, fiscal_year)` |
| `type` | unchanged | |
| `canal` | `channel` | |
| `date_depot` | `submitted_at` | |
| `statut` (`StatutRapport`) | `status` (`ReportStatus`) | see §2.4 |
| — | `extraction_status` (`ExtractionStatus`) | new, see §2.4 |
| `fichier_source` | `source_file` | |
| `nom_fichier_origine` | `original_filename` | |
| `annee_reporting` | `fiscal_year` | |
| `auditeur_id` | `auditor_id` | `ON DELETE SET NULL` |
| `date_affectation` | `assigned_at` | |
| `extraction_demarree_le` | `extraction_started_at` | |
| `extraction_terminee_le` | `extraction_finished_at` | |
| `extraction_erreur` | `extraction_error` | |
| `tentatives_extraction` | `extraction_attempts` | |
| `version` | unchanged | |
| `rapport_precedent_id` | `previous_report_id` | `ON DELETE SET NULL` |
| `checksum_sha256` | unchanged | |
| `score_global_declare` | `declared_global_score` | |
| `score_global_declare_preuve_id` | `declared_global_score_proof_id` | `ON DELETE SET NULL` |
| `rapport_synthese_genere` | `synthesis_report_path` | |
| — | `official_score`, `coverage_rate`, `config_hash` | new, filled by tasks 1.6 and 3.1 |
| rel. `entreprise`, `auditeur`, `indicateurs`, `donnees_carbone`, `avis_audit`, `couvertures`, `score_global_declare_preuve` | `company`, `auditor`, `metrics`, `carbon_data`, `audit_opinions`, `coverages`, `declared_global_score_proof` | `scores` unchanged |

### 2.3 `indicateur_esg` → `esg_metrics` (`IndicateurESG` → `ESGMetric`)

| Current | Target | Note |
|---|---|---|
| `rapport_id` | `report_id` | `ON DELETE CASCADE`; unique `(report_id, metric_code)` |
| `pilier` | `pillar` | enum `Pilier` unchanged until task 3.1 |
| `code` | `metric_code` | |
| `valeur` | `value` | |
| `unite` | `unit` | |
| `methode` | `method` | |
| `preuve_id` | `proof_id` | `ON DELETE CASCADE` (no value without proof) |
| `valeur_brute` | `raw_value` | |
| `section` | unchanged | |
| `citation_source` | `proof_text` | |
| `annee_valeur` | `value_year` | |
| `confiance` | `confidence` | |
| — | `auditor_overridden`, `override_value`, `override_reason`, `overridden_by_id`, `overridden_at` | new; `overridden_by_id` `ON DELETE SET NULL` |
| rel. `rapport`, `preuve`, `signalements` | `report`, `proof`, `discrepancy_flags` | |

### 2.4 Report status (`StatutRapport` → `ReportStatus` + `ExtractionStatus`)

| `statut` | `status` | `extraction_status` |
|---|---|---|
| — | `DRAFT` | `NOT_STARTED` |
| `ENVOYE` | `SUBMITTED` | `QUEUED` |
| `EN_EXTRACTION` | `SUBMITTED` | from timestamps: error → `FAILED`, finished → `DONE`, started → `RUNNING`, else `QUEUED` |
| `AFFECTE_AUDITEUR` | `PENDING_AUDIT` | from timestamps |
| `EN_VALIDATION` | `PENDING_DECISION` | from timestamps |
| `DEMANDE_CORRECTION` | `REVISION_REQUESTED` | from timestamps |
| `VALIDE` | `VALIDATED` | from timestamps |
| `REJETE` | `REJECTED` | from timestamps |

"From timestamps" for a status past `SUBMITTED` falls back to `NOT_STARTED` when no extraction
timestamp exists. Downgrade maps back one-to-one; `SUBMITTED` goes back to `ENVOYE` when
extraction is `QUEUED`/`NOT_STARTED`, otherwise to `EN_EXTRACTION`; `DRAFT` goes back to `ENVOYE`.

### 2.5 Inbound foreign keys fixed in task 1.1 (names unchanged)

| Column | Target of | `ON DELETE` | Index |
|---|---|---|---|
| `analyse_entreprise.entreprise_id` | companies | CASCADE | add |
| `analyse_entreprise.rapport_id` | esg_reports | SET NULL | add |
| `avis_audit.rapport_id` | esg_reports | CASCADE | add |
| `couverture_indicateur.rapport_id` | esg_reports | CASCADE | exists (unique) |
| `donnee_carbone.rapport_id` | esg_reports | CASCADE | add |
| `position_portefeuille.entreprise_id` | companies | CASCADE | add |
| `projet_document.rapport_id` | esg_reports | CASCADE | add |
| `projet_entreprise.entreprise_id` | companies | CASCADE | add |
| `score_esg.rapport_id` | esg_reports | CASCADE | exists |
| `signalement_ecart.entreprise_id` | companies | CASCADE | add |
| `signalement_ecart.indicateur_id` | esg_metrics | CASCADE | add |

The application never hard-deletes a company or a report (suspension and versioning are the
application-level operations); these rules define what an administrative purge removes.

## 3. Task 1.2 — users and authentication ✅

Landed in migration `7499c018ddb1` (upgrade/downgrade round-trip and `alembic check` verified).

### 3.1 Tables and columns

| Current | Target | Note |
|---|---|---|
| `utilisateur` (`Utilisateur`) | `users` (`User`) | e-mail stored lower-case (`ck_users_email_lowercase`), unique |
| `nom`, `mot_de_passe_hache`, `date_creation`, `actif`, `date_activation` | `name`, `password_hash`, `created_at`, `active`, `activated_at` | `email`, `avatar`, `role` unchanged |
| `activation_compte` (`ActivationCompte`) | `account_activation_tokens` (`AccountActivationToken`) | |
| `reinitialisation_mot_de_passe` (`ReinitialisationMotDePasse`) | `password_reset_tokens` (`PasswordResetToken`) | |
| token columns `utilisateur_id`, `jeton_hache`, `date_creation`, `date_expiration`, `utilise_le` | `user_id`, `token_hash`, `created_at`, `expires_at`, `used_at` | |
| — | `email_change_requests` (`EmailChangeRequest`) | new: e-mail change confirmed by the new address |
| rel. `institution_profil`, `entreprise`, `rapports_audites`, `configurations_ponderation`, `portefeuilles`, `avis_rendus`, `projets`, `affectations_projet` | `institution_profile`, `company`, `audited_reports`, `scoring_configs`, `portfolios`, `audit_opinions`, `projects`, `project_assignments` | `notifications`, `analyses` unchanged |
| `Role` values `ADMINISTRATEUR`, `ENTREPRISE`, `AUDITEUR`, `INVESTISSEUR`, `CHERCHEUR` | `ADMIN`, `ENTERPRISE`, `AUDITOR`, `INVESTOR`, `RESEARCHER` | `INSTITUTION` unchanged (D1); values change in the API too (rule 3 exception) |

The audit journal's resource-type label `"Utilisateur"` is stored data, not a class name: it
stays until the journal is renamed (task 4.7).

### 3.2 `ON DELETE` rules for foreign keys to `users`

| Rule | Columns | Why |
|---|---|---|
| CASCADE | tokens, `email_change_requests`, `notification.utilisateur_id`, `institution_profil.utilisateur_id`, `chercheur_institution.*` | rows that only exist for the user |
| SET NULL | `journal_audit.acteur_id`, `companies.owner_user_id`, `esg_reports.auditor_id`, `esg_metrics.overridden_by_id` | optional references; the row keeps its own meaning |
| RESTRICT | `avis_audit.auditeur_id`, `analyse.chercheur_id`, `affectation_projet.chercheur_id`, `projet.institution_id`, `configuration_ponderation.utilisateur_id` | accountability or business records: deleting the user must fail rather than erase them. `configuration_ponderation.utilisateur_id` NULL means the *reference* config, so SET NULL would be actively wrong. Revisit each with its module's task. |

This is a deliberate exception to the "CASCADE or SET NULL" guideline: the application never
deletes a user (it deactivates them), and silently deleting audit opinions or research analyses
would destroy evidence.

## 3b. Task 2.1 — portfolios ✅

Landed in migration `be63d4541f22` (upgrade/downgrade round-trip and `alembic check` verified).

| Current | Target | Note |
|---|---|---|
| `portefeuille` (`Portefeuille`) | `portfolios` (`Portfolio`) | `user_id` → users **CASCADE** (was RESTRICT in §3.2: a portfolio only belongs to its investor) |
| `investisseur_id`, `nom`, `devise_reference`, `date_creation`, `archive` | `user_id`, `name`, `reference_currency`, `created_at`, `archived` | + cached `total_esg_score`, `waci`, `financed_emissions_tco2e`, `computed_at`, `config_hash` (filled by 2.3) |
| `position_portefeuille` (`PositionPortefeuille`) | `portfolio_positions` (`PortfolioPosition`) | `portfolio_id` CASCADE + index |
| `portefeuille_id`, `entreprise_id`, `montant_investi`, `devise`, `taux_change_utilise`, `montant_converti`, `type_duree`, `date_debut`, `date_fin` | `portfolio_id`, `company_id` (**nullable**), `outstanding_amount`, `currency`, `fx_rate_used`, `converted_amount`, `duration_type`, `start_date`, `end_date` | + `identifier_type`, `identifier_raw`, `match_status` (`MatchStatus`), `weight` in ]0, 1] |
| rel. `investisseur`, `portefeuille`, `entreprise` | `user`, `portfolio`, `company` | |

`DevisePosition` and `TypeDureeInvestissement` keep their class names for now (their values are
part of the API). Amounts are `Decimal` / `numeric` since task 2.3.

## 3c. Task 2.3 — carbon, evidence, coverage, discrepancy tables (migration `c3a9f2d71b58`)

| Old table (class) | New table (class) | Columns |
|---|---|---|
| `donnee_carbone` (`DonneeCarbone`) | `carbon_emissions` (`CarbonEmission`) | `rapport_id` → `report_id`, `categorie_ges` → `ghg_category`, `valeur_tonnes_co2e` → `tonnes_co2e`, `annee` → `year`, `methode` → `method`, `score_qualite_pcaf` → `pcaf_data_quality` (**nullable**), `preuve_id` → `proof_id` (CASCADE + index, had neither), `valeur_brute` → `raw_value`, `citation_source` → `proof_text`, `annee_valeur` → `value_year`, `confiance` → `confidence` |
| `preuve_documentaire` (`PreuveDocumentaire`) | `evidence` (`Evidence`) | `nom_document` → `document_name`, `annee` → `year`, `nombre_pages_total` → `total_pages`, `page_debut` / `page_fin` → `page_start` / `page_end`, `pdf_extrait_genere` → `excerpt_pdf_path` |
| `couverture_indicateur` (`CouvertureIndicateur`) | `metric_coverage` (`MetricCoverage`) | `rapport_id` → `report_id`, `code` → `metric_code`, `statut` → `status`, `pages_examinees` → `pages_examined` |
| `signalement_ecart` (`SignalementEcart`) | `discrepancy_flags` (`DiscrepancyFlag`) | `indicateur_id` → `metric_id`, `entreprise_id` → `company_id`, `nature_ecart` → `nature`, `statut` → `status`, `date_signalement` → `flagged_at` |

Relationships follow (`report`, `proof`, `metric`, `company`, `Evidence.metrics` /
`carbon_emissions`). The JSON contract is unchanged (rule 3): `PreuveDocumentairePublic`,
`DonneeCarboneDetail` and `CouvertureIndicateurPublic` map the English attributes explicitly;
only `score_qualite_pcaf` becomes nullable. `StatutCouvertureIndicateur` and `MethodeDonnee` keep
their names (their values are in the API).

## 4. Later renames

| Task | Tables | Classes |
|---|---|---|
| ~~2.3~~ | done — see §3c | |
| 3.1 | `configuration_ponderation` → `scoring_configs`, `score_esg` → `scores` | `ConfigurationPonderation` → `ScoringConfig`, `ScoreESG` → `Score`; `Pilier` → `Pillar` |
| 4.7 | audit, researcher, institution, core (`notification`, `journal_audit`) tables; remaining French JSON field names; audit journal labels | remaining classes |
