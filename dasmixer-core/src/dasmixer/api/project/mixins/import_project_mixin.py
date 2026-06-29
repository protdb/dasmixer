"""Mixin for importing data from another .dasmix project file."""

import aiosqlite
from pathlib import Path
from typing import Callable, Literal

from dasmixer.api.project.core.base import ProjectBase
from dasmixer.utils.logger import logger


class ImportProjectMixin(ProjectBase):
    """
    Mixin providing import_project() method to merge data from another .dasmix file.

    The import operation runs in a single transaction on the target database.
    It maps IDs from source to target for subset, tool, and sample tables,
    then bulk-inserts remaining tables via ATTACH DATABASE + SQL.
    """

    async def import_project(
        self,
        source_path: str | Path,
        tool_match: Literal['name', 'parser'] | None = 'parser',
        subset_match: bool = True,
        project_settings_match: bool = False,
        sample_match: bool = True,
        conflict_suffix: str = "_1",
        status_callback: Callable[[str, float], None] | None = None,
    ) -> None:
        """
        Import data from another .dasmix project file into this project.

        Args:
            source_path: Path to source .dasmix file
            tool_match: Strategy for matching tools ('name', 'parser', or None for all new)
            subset_match: If True, merge subsets by name; if False, add all with suffix
            project_settings_match: If True, overwrite target settings with source
            sample_match: If True, merge samples by name; if False, add all with suffix
            conflict_suffix: Suffix appended to duplicate names (default: "_1")
            status_callback: Optional callback(table_name, fraction) for progress updates
        """
        src_path = Path(source_path)
        if not src_path.exists():
            raise FileNotFoundError(f"Source project not found: {src_path}")

        # Open source DB in read-only mode
        src_db = await aiosqlite.connect(str(src_path))
        src_db.row_factory = aiosqlite.Row
        await src_db.execute("PRAGMA query_only = ON")

        old_sync = None
        old_cache = None

        try:
            # Save current PRAGMA values to restore later (must be done BEFORE BEGIN)
            row = await self._fetchone("PRAGMA synchronous")
            old_sync = row['synchronous'] if row else None
            row = await self._fetchone("PRAGMA cache_size")
            old_cache = row['cache_size'] if row else None

            # Optimize target for bulk insert (outside transaction)
            await self._db.execute("PRAGMA synchronous = NORMAL")
            await self._db.execute("PRAGMA cache_size = -65536")

            # BEGIN transaction on target
            await self._db.execute("BEGIN")

            if status_callback:
                status_callback("subset", 0.05)

            # ----------------------------------------------------------------
            # Step 1. Subset mapping
            # ----------------------------------------------------------------

            # Get all subsets from source
            src_subsets = await src_db.execute_fetchall(
                "SELECT id, name, details, display_color FROM subset"
            )
            src_subsets = [dict(r) for r in src_subsets]

            # Get existing subset names in target
            tgt_rows = await self._fetchall("SELECT id, name FROM subset")
            tgt_names = {r['name'] for r in tgt_rows}

            subset_id_map = {}  # src_id -> tgt_id

            for ss in src_subsets:
                src_id = ss['id']
                name = ss['name']

                if subset_match:
                    # Find by name
                    row = await self._fetchone(
                        "SELECT id FROM subset WHERE name = ?", (name,)
                    )
                    if row:
                        subset_id_map[src_id] = row['id']
                        continue
                    # Not found — insert new

                if not subset_match:
                    # If name conflicts — add suffix
                    orig_name = name
                    while name in tgt_names:
                        name = orig_name + conflict_suffix

                await self._execute(
                    "INSERT INTO subset (name, details, display_color) VALUES (?, ?, ?)",
                    (name, ss['details'], ss['display_color'])
                )
                new_id = (await self._fetchone(
                    "SELECT last_insert_rowid() as id"
                ))['id']
                subset_id_map[src_id] = new_id
                tgt_names.add(name)

            if status_callback:
                status_callback("tool", 0.10)

            # ----------------------------------------------------------------
            # Step 2. Tool mapping
            # ----------------------------------------------------------------

            src_tools = await src_db.execute_fetchall(
                "SELECT id, name, type, parser, settings, display_color FROM tool"
            )
            src_tools = [dict(r) for r in src_tools]

            tgt_rows = await self._fetchall(
                "SELECT id, name, parser FROM tool"
            )
            tgt_tools_by_parser = {}
            tgt_tools_by_name = {}
            tgt_tool_names = set()
            for r in tgt_rows:
                tgt_tools_by_parser[r['parser']] = r['id']
                tgt_tools_by_name[r['name']] = r['id']
                tgt_tool_names.add(r['name'])

            tool_id_map = {}

            for st in src_tools:
                src_id = st['id']
                matched = False

                if tool_match == 'parser':
                    if st['parser'] in tgt_tools_by_parser:
                        tool_id_map[src_id] = tgt_tools_by_parser[st['parser']]
                        matched = True
                elif tool_match == 'name':
                    if st['name'] in tgt_tools_by_name:
                        tool_id_map[src_id] = tgt_tools_by_name[st['name']]
                        matched = True
                # tool_match=None — don't match, insert as new

                if not matched:
                    name = st['name']
                    orig_name = name
                    while name in tgt_tool_names:
                        name = orig_name + conflict_suffix

                    await self._execute(
                        "INSERT INTO tool (name, type, parser, settings, display_color) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (name, st['type'], st['parser'],
                         st['settings'], st['display_color'])
                    )
                    new_id = (await self._fetchone(
                        "SELECT last_insert_rowid() as id"
                    ))['id']
                    tool_id_map[src_id] = new_id
                    tgt_tool_names.add(name)

            if status_callback:
                status_callback("sample", 0.15)

            # ----------------------------------------------------------------
            # Step 3. Sample mapping
            # ----------------------------------------------------------------

            src_samples = await src_db.execute_fetchall(
                "SELECT id, name, subset_id, additions, outlier FROM sample"
            )
            src_samples = [dict(r) for r in src_samples]

            base_sample_id_row = await self._fetchone(
                "SELECT COALESCE(MAX(id), 0) AS max_id FROM sample"
            )
            base_sample_id = (
                base_sample_id_row['max_id'] if base_sample_id_row else 0
            )

            tgt_rows = await self._fetchall("SELECT id, name FROM sample")
            tgt_sample_names = {r['name'] for r in tgt_rows}

            sample_id_map = {}

            for ss in src_samples:
                src_id = ss['id']
                name = ss['name']

                if sample_match:
                    row = await self._fetchone(
                        "SELECT id FROM sample WHERE name = ?", (name,)
                    )
                    if row:
                        sample_id_map[src_id] = row['id']
                        continue

                if not sample_match:
                    orig_name = name
                    while name in tgt_sample_names:
                        name = orig_name + conflict_suffix

                new_id = src_id + base_sample_id
                new_subset_id = subset_id_map.get(
                    ss['subset_id'], ss['subset_id']
                )

                await self._execute(
                    "INSERT INTO sample (id, name, subset_id, additions, outlier) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (new_id, name, new_subset_id,
                     ss['additions'], ss['outlier'])
                )
                sample_id_map[src_id] = new_id
                tgt_sample_names.add(name)

            if status_callback:
                status_callback("protein", 0.20)

            # ----------------------------------------------------------------
            # Step 4. ATTACH DATABASE + bulk insert
            # ----------------------------------------------------------------

            await self._db.execute(f"ATTACH DATABASE '{src_path}' AS src")

            # Create temp mapping tables
            await self._db.execute("""
                CREATE TEMP TABLE IF NOT EXISTS _sample_id_map (
                    src_id INTEGER PRIMARY KEY,
                    tgt_id INTEGER
                )
            """)
            await self._db.execute("""
                CREATE TEMP TABLE IF NOT EXISTS _tool_id_map (
                    src_id INTEGER PRIMARY KEY,
                    tgt_id INTEGER
                )
            """)

            # Get base IDs for all bulk tables
            bulk_tables = [
                'spectre_file', 'spectre', 'identification_file', 'identification',
                'peptide_match', 'protein_identification_result',
                'protein_quantification_result', 'generated_reports', 'saved_plots'
            ]
            base_ids = {}
            for tbl in bulk_tables:
                row = await self._fetchone(
                    f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {tbl}"
                )
                base_ids[tbl] = row['max_id'] if row else 0

            # Fill temp mapping tables
            await self._executemany(
                "INSERT INTO temp._sample_id_map (src_id, tgt_id) VALUES (?, ?)",
                [(sid, tid) for sid, tid in sample_id_map.items()]
            )
            await self._executemany(
                "INSERT INTO temp._tool_id_map (src_id, tgt_id) VALUES (?, ?)",
                [(sid, tid) for sid, tid in tool_id_map.items()]
            )

            if status_callback:
                status_callback("spectre_file", 0.25)

            # 4.1 protein
            await self._db.execute("""
                INSERT OR IGNORE INTO protein (id, is_uniprot, fasta_name,
                    sequence, gene, name, uniprot_data)
                SELECT id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data
                FROM src.protein
            """)

            # 4.2 spectre_file
            b_sf = base_ids['spectre_file']
            await self._db.execute(f"""
                INSERT INTO spectre_file (id, sample_id, format, path)
                SELECT sf.id + {b_sf}, m.tgt_id, sf.format, sf.path
                FROM src.spectre_file sf
                JOIN temp._sample_id_map m ON m.src_id = sf.sample_id
            """)

            if status_callback:
                status_callback("spectre", 0.45)

            # 4.3 spectre
            b_s = base_ids['spectre']
            await self._db.execute(f"""
                INSERT INTO spectre (id, spectre_file_id, seq_no, title,
                    scans, charge, rt, pepmass, intensity, mz_array,
                    intensity_array, peaks_count, charge_array,
                    charge_array_common_value, all_params)
                SELECT s.id + {b_s}, s.spectre_file_id + {b_sf},
                       s.seq_no, s.title, s.scans, s.charge, s.rt,
                       s.pepmass, s.intensity, s.mz_array, s.intensity_array,
                       s.peaks_count, s.charge_array, s.charge_array_common_value,
                       s.all_params
                FROM src.spectre s
            """)

            if status_callback:
                status_callback("identification_file", 0.50)

            # 4.4 identification_file
            b_idf = base_ids['identification_file']
            await self._db.execute(f"""
                INSERT INTO identification_file (id, spectre_file_id, tool_id,
                    file_path, selection_field, selection_field_value)
                SELECT idf.id + {b_idf}, idf.spectre_file_id + {b_sf},
                       tm.tgt_id, idf.file_path,
                       idf.selection_field, idf.selection_field_value
                FROM src.identification_file idf
                JOIN temp._tool_id_map tm ON tm.src_id = idf.tool_id
            """)

            if status_callback:
                status_callback("identification", 0.65)

            # 4.5 identification
            b_i = base_ids['identification']
            await self._db.execute(f"""
                INSERT INTO identification (id, spectre_id, tool_id,
                    ident_file_id, is_preferred, sequence, canonical_sequence,
                    ppm, theor_mass, score, positional_scores,
                    intensity_coverage, ions_matched, ion_match_type,
                    top_peaks_covered, override_charge, source_sequence,
                    isotope_offset, src_file_protein_id)
                SELECT i.id + {b_i}, i.spectre_id + {b_s},
                       tm.tgt_id, i.ident_file_id + {b_idf},
                       i.is_preferred,
                       i.sequence, i.canonical_sequence, i.ppm, i.theor_mass,
                       i.score, i.positional_scores, i.intensity_coverage,
                       i.ions_matched, i.ion_match_type, i.top_peaks_covered,
                       i.override_charge, i.source_sequence, i.isotope_offset,
                       i.src_file_protein_id
                FROM src.identification i
                JOIN temp._tool_id_map tm ON tm.src_id = i.tool_id
            """)

            if status_callback:
                status_callback("peptide_match", 0.75)

            # 4.6 peptide_match
            b_pm = base_ids['peptide_match']
            await self._db.execute(f"""
                INSERT INTO peptide_match (id, protein_id, identification_id,
                    matched_sequence, identity, matched_ppm, matched_theor_mass,
                    unique_evidence, matched_coverage_percent, matched_peaks,
                    matched_top_peaks, matched_ion_type,
                    matched_sequence_modified, substitution)
                SELECT pm.id + {b_pm}, pm.protein_id,
                       pm.identification_id + {b_i},
                       pm.matched_sequence, pm.identity, pm.matched_ppm,
                       pm.matched_theor_mass, pm.unique_evidence,
                       pm.matched_coverage_percent, pm.matched_peaks,
                       pm.matched_top_peaks, pm.matched_ion_type,
                       pm.matched_sequence_modified, pm.substitution
                FROM src.peptide_match pm
            """)

            if status_callback:
                status_callback("protein_identification_result", 0.85)

            # 4.7 protein_identification_result
            b_pir = base_ids['protein_identification_result']
            await self._db.execute(f"""
                INSERT INTO protein_identification_result (id, protein_id,
                    sample_id, peptide_count, uq_evidence_count, coverage,
                    intensity_sum)
                SELECT pir.id + {b_pir}, pir.protein_id,
                       m.tgt_id,
                       pir.peptide_count, pir.uq_evidence_count, pir.coverage,
                       pir.intensity_sum
                FROM src.protein_identification_result pir
                JOIN temp._sample_id_map m ON m.src_id = pir.sample_id
            """)

            if status_callback:
                status_callback("protein_quantification_result", 0.90)

            # 4.8 protein_quantification_result
            b_pqr = base_ids['protein_quantification_result']
            await self._db.execute(f"""
                INSERT INTO protein_quantification_result (id,
                    protein_identification_id, algorithm, rel_value, abs_value)
                SELECT pqr.id + {b_pqr},
                       pqr.protein_identification_id + {b_pir},
                       pqr.algorithm, pqr.rel_value, pqr.abs_value
                FROM src.protein_quantification_result pqr
            """)

            if status_callback:
                status_callback("reports", 0.95)

            # 4.9 generated_reports
            b_gr = base_ids['generated_reports']
            await self._db.execute(f"""
                INSERT INTO generated_reports (id, report_name, created_at,
                    plots, tables, project_settings, tools_settings,
                    report_settings)
                SELECT gr.id + {b_gr},
                       gr.report_name, gr.created_at, gr.plots, gr.tables,
                       gr.project_settings, gr.tools_settings,
                       gr.report_settings
                FROM src.generated_reports gr
            """)

            # 4.10 saved_plots
            b_sp = base_ids['saved_plots']
            await self._db.execute(f"""
                INSERT INTO saved_plots (id, created_at, plot_type, settings,
                    plot)
                SELECT sp.id + {b_sp},
                       sp.created_at, sp.plot_type, sp.settings, sp.plot
                FROM src.saved_plots sp
            """)

            # ----------------------------------------------------------------
            # Step 5. project_settings
            # ----------------------------------------------------------------

            if project_settings_match:
                await self._db.execute("""
                    INSERT OR REPLACE INTO project_settings (key, value)
                    SELECT key, value FROM src.project_settings
                """)
            else:
                await self._db.execute("""
                    INSERT OR IGNORE INTO project_settings (key, value)
                    SELECT key, value FROM src.project_settings
                """)

            # ----------------------------------------------------------------
            # Step 6. Reset autoincrement sequences
            # ----------------------------------------------------------------

            for tbl in [
                'subset', 'tool', 'sample', 'spectre_file', 'spectre',
                'identification_file', 'identification', 'peptide_match',
                'protein_identification_result', 'protein_quantification_result',
                'generated_reports', 'saved_plots'
            ]:
                await self._db.execute(f"""
                    UPDATE sqlite_sequence
                    SET seq = (SELECT COALESCE(MAX(id), 0) FROM {tbl})
                    WHERE name = '{tbl}'
                """)

            # ----------------------------------------------------------------
            # COMMIT
            # ----------------------------------------------------------------

            await self._db.execute("COMMIT")

            if status_callback:
                status_callback("finalizing", 1.0)

            logger.info(f"Project import complete from {src_path}")

        except Exception:
            # Rollback on error
            try:
                await self._db.execute("ROLLBACK")
            except Exception:
                pass
            raise

        finally:
            # Restore PRAGMA values
            try:
                await self._db.execute(
                    f"PRAGMA synchronous = {old_sync or 'FULL'}"
                )
                await self._db.execute(
                    f"PRAGMA cache_size = {old_cache or -2000}"
                )
            except Exception:
                pass
            try:
                await self._db.execute("DETACH DATABASE src")
            except Exception:
                pass
            await src_db.close()

            # Final save with checkpoint
            await self.save(checkpoint=True)
