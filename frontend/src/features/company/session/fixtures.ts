/** Ligne de la liste des rapports d'une entreprise, pour les tests (tâche 5.9). */
const SHA = "f".repeat(64);

export function rapportListe(id: string, surcharges: Record<string, unknown> = {}) {
  return {
    id,
    company_id: "c1",
    type: "RAPPORT_ESG",
    channel: "ENTREPRISE",
    created_at: "2026-01-10T08:00:00Z",
    submitted_at: "2026-01-12T08:00:00Z",
    status: "VALIDATED",
    source_file: "x.pdf",
    original_filename: "x.pdf",
    fiscal_year: 2024,
    extraction_finished_at: "2026-01-11T08:00:00Z",
    extraction_error: null,
    extraction_attempts: 1,
    version: 1,
    previous_report_id: null,
    checksum_sha256: SHA,
    official_global_score: 74.5,
    coverage_rate: 0.88,
    config_hash: "a".repeat(64),
    synthesis_available: true,
    ...surcharges,
  };
}
