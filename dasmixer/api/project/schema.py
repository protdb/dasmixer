"""SQL schema for DASMixer project database."""
from dasmixer.versions import PROJECT_VERSION

# Complete SQL schema for SQLite database
# Note: SQLite doesn't have native JSON type, using TEXT for JSON fields

CREATE_SCHEMA_SQL = """
-- Project metadata and settings
CREATE TABLE IF NOT EXISTS project_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Comparison groups/subsets
CREATE TABLE IF NOT EXISTS subset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    details TEXT,
    display_color TEXT
);

-- Identification tools
CREATE TABLE IF NOT EXISTS tool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,  -- "Library" or "De Novo"
    parser TEXT NOT NULL,  -- Parser name (e.g., "PowerNovo2", "MaxQuant")
    settings TEXT,  -- JSON as TEXT
    display_color TEXT
);

-- Samples
CREATE TABLE IF NOT EXISTS sample (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    subset_id INTEGER,
    additions TEXT,  -- JSON as TEXT
    outlier INTEGER NOT NULL DEFAULT 0,  -- BOOLEAN: 1 if sample is marked as outlier
    FOREIGN KEY (subset_id) REFERENCES subset(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sample_subset ON sample(subset_id);

-- Spectra files
CREATE TABLE IF NOT EXISTS spectre_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL,
    format TEXT NOT NULL,
    path TEXT NOT NULL,
    FOREIGN KEY (sample_id) REFERENCES sample(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spectre_file_sample ON spectre_file(sample_id);

-- Spectra
CREATE TABLE IF NOT EXISTS spectre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spectre_file_id INTEGER NOT NULL,
    seq_no INTEGER NOT NULL,
    title TEXT,
    scans INTEGER,
    charge INTEGER,
    rt REAL,
    pepmass REAL NOT NULL,
    intensity REAL,
    mz_array BLOB,
    intensity_array BLOB,
    peaks_count INTEGER,
    charge_array BLOB,
    charge_array_common_value INTEGER,
    all_params TEXT,  -- JSON as TEXT
    FOREIGN KEY (spectre_file_id) REFERENCES spectre_file(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spectre_file ON spectre(spectre_file_id);
CREATE INDEX IF NOT EXISTS idx_spectre_title ON spectre(title);
CREATE INDEX IF NOT EXISTS idx_spectre_seq ON spectre(spectre_file_id, seq_no);

-- Identification files
CREATE TABLE IF NOT EXISTS identification_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spectre_file_id INTEGER NOT NULL,
    tool_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    FOREIGN KEY (spectre_file_id) REFERENCES spectre_file(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES tool(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ident_file_spectre ON identification_file(spectre_file_id);
CREATE INDEX IF NOT EXISTS idx_ident_file_tool ON identification_file(tool_id);

-- Identifications
CREATE TABLE IF NOT EXISTS identification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spectre_id INTEGER NOT NULL,
    tool_id INTEGER NOT NULL,
    ident_file_id INTEGER NOT NULL,
    is_preferred INTEGER NOT NULL DEFAULT 0,  -- BOOLEAN as INTEGER
    sequence TEXT NOT NULL,
    canonical_sequence TEXT NOT NULL,
    ppm REAL,
    theor_mass REAL,
    score REAL,
    positional_scores TEXT,  -- JSON as TEXT
    intensity_coverage REAL,  -- Percentage of spectrum intensity matched by theoretical ions
    ions_matched INTEGER,
    ion_match_type TEXT,
    top_peaks_covered INTEGER,
    override_charge INTEGER,
    source_sequence TEXT,  -- original unmodified sequence; NULL if same as sequence
    isotope_offset INTEGER,  -- precursor isotope offset; NULL if not determined
    FOREIGN KEY (spectre_id) REFERENCES spectre(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES tool(id) ON DELETE CASCADE,
    FOREIGN KEY (ident_file_id) REFERENCES identification_file(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ident_spectre ON identification(spectre_id);
CREATE INDEX IF NOT EXISTS idx_ident_tool ON identification(tool_id);
CREATE INDEX IF NOT EXISTS idx_ident_file ON identification(ident_file_id);
CREATE INDEX IF NOT EXISTS idx_ident_preferred ON identification(is_preferred);

-- Proteins
CREATE TABLE IF NOT EXISTS protein (
    id TEXT PRIMARY KEY,
    is_uniprot INTEGER NOT NULL DEFAULT 0,  -- BOOLEAN as INTEGER
    fasta_name TEXT,
    sequence TEXT,
    gene TEXT,
    name TEXT,  -- Short protein name
    uniprot_data BLOB,  -- Serialized UniprotData object (pickle + gzip)
    taxon_id INTEGER,           -- NCBI Taxonomy ID (nullable)
    organism_name TEXT          -- Organism display name (nullable)
);

CREATE INDEX IF NOT EXISTS idx_protein_uniprot ON protein(is_uniprot);
CREATE INDEX IF NOT EXISTS idx_protein_gene ON protein(gene);

-- Peptide matches
CREATE TABLE IF NOT EXISTS peptide_match (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id TEXT NOT NULL,
    identification_id INTEGER NOT NULL,
    matched_sequence TEXT NOT NULL,
    identity REAL NOT NULL,
    matched_ppm REAL,
    matched_theor_mass REAL,
    unique_evidence INTEGER,  -- BOOLEAN as INTEGER
    matched_coverage_percent REAL,
    matched_peaks INTEGER,          -- ions_matched for matched sequence
    matched_top_peaks INTEGER,      -- top_peaks_covered for matched sequence
    matched_ion_type TEXT,          -- ion_match_type for matched sequence
    matched_sequence_modified TEXT, -- ProForma with PTMs if get_matched_ppm found override; NULL otherwise
    substitution INTEGER NOT NULL DEFAULT 0,  -- BOOLEAN: 1 if saved as AA substitution candidate
    FOREIGN KEY (protein_id) REFERENCES protein(id) ON DELETE CASCADE,
    FOREIGN KEY (identification_id) REFERENCES identification(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_peptide_match_protein ON peptide_match(protein_id);
CREATE INDEX IF NOT EXISTS idx_peptide_match_ident ON peptide_match(identification_id);

-- Protein identification results
CREATE TABLE IF NOT EXISTS protein_identification_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id TEXT NOT NULL,
    sample_id INTEGER NOT NULL,
    peptide_count INTEGER NOT NULL,
    uq_evidence_count INTEGER NOT NULL,
    coverage REAL,
    intensity_sum REAL,  -- Sum of peptide intensities for this protein
    FOREIGN KEY (protein_id) REFERENCES protein(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_id) REFERENCES sample(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prot_ident_protein ON protein_identification_result(protein_id);
CREATE INDEX IF NOT EXISTS idx_prot_ident_sample ON protein_identification_result(sample_id);

-- Protein quantification results
CREATE TABLE IF NOT EXISTS protein_quantification_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_identification_id INTEGER NOT NULL,
    algorithm TEXT NOT NULL,
    rel_value REAL,
    abs_value REAL,
    FOREIGN KEY (protein_identification_id) REFERENCES protein_identification_result(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_prot_quant_ident ON protein_quantification_result(protein_identification_id);
CREATE INDEX IF NOT EXISTS idx_prot_quant_algo ON protein_quantification_result(algorithm);

-- Sample status cache (Stage 11)
-- Stores pre-computed aggregated statistics per sample for fast panel rendering.
-- Updated whenever stats are recalculated; read on project open.
CREATE TABLE IF NOT EXISTS sample_status_cache (
    sample_id INTEGER PRIMARY KEY,
    spectra_files_count INTEGER NOT NULL DEFAULT 0,
    ident_files_count INTEGER NOT NULL DEFAULT 0,
    identifications_count INTEGER NOT NULL DEFAULT 0,
    preferred_count INTEGER NOT NULL DEFAULT 0,
    coverage_known_count INTEGER NOT NULL DEFAULT 0,
    protein_ids_count INTEGER NOT NULL DEFAULT 0,
    empty_ident_files_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (sample_id) REFERENCES sample(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sample_status_cache ON sample_status_cache(sample_id);

-- Generated reports (updated for Stage 5)
CREATE TABLE IF NOT EXISTS generated_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    plots BLOB,  -- pickle + gzip: list[tuple[str, go.Figure]]
    tables BLOB,  -- pickle + gzip: list[tuple[str, pd.DataFrame, bool]]
    project_settings TEXT,  -- JSON as TEXT
    tools_settings TEXT,  -- JSON as TEXT
    report_settings TEXT  -- JSON as TEXT
);

CREATE INDEX IF NOT EXISTS idx_generated_reports_name ON generated_reports(report_name);
CREATE INDEX IF NOT EXISTS idx_generated_reports_created ON generated_reports(created_at);

-- Report parameters (Stage 5)
CREATE TABLE IF NOT EXISTS report_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT UNIQUE NOT NULL,
    parameters TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_parameters_name ON report_parameters(report_name);

-- Saved plots (Stage 6)
CREATE TABLE IF NOT EXISTS saved_plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    plot_type TEXT NOT NULL,
    settings TEXT,
    plot BLOB
);

CREATE INDEX IF NOT EXISTS idx_saved_plots_type ON saved_plots(plot_type);
CREATE INDEX IF NOT EXISTS idx_saved_plots_created ON saved_plots(created_at);
"""

# Default project metadata
DEFAULT_METADATA = {
    'version': PROJECT_VERSION,
    'created_at': None,  # Will be set on creation
    'modified_at': None  # Will be updated on each save
}
