"""Table view for peptide identifications with filtering."""

import flet as ft
import pandas as pd

from dasmixer.gui.components.base_table_view import BaseTableView
from dasmixer.api.project.project import Project
from dasmixer.utils import logger

_MAX_SEQ_LEN = 31


class PeptideIonTableView(BaseTableView):
    """Table view for peptide identifications."""

    table_view_name = "peptide_identifications"
    plot_id_field = "spectre_id"

    header_name_mapping = {
        # ID/sample/spectrum
        'identification_id': 'ID',
        'spectre_id': 'Spectrum ID',
        'sample': 'Sample',
        'sample_id': 'Sample ID',
        'subset': 'Subset',
        'subset_id': 'Subset ID',
        'seq_no': 'Seq #',
        'scans': 'Scans',
        'rt': 'RT',
        'peaks_count': 'Peaks Count',
        'intensity': 'Intensity',
        # tool
        'tool': 'Tool',
        'tool_id': 'Tool ID',
        # sequence / PPM
        'sequence': 'Sequence',
        'canonical_sequence': 'Canonical Sequence',
        'source_sequence': 'Source Sequence',
        'ppm': 'PPM',
        'theor_mass': 'Theoretical Mass',
        'score': 'Score',
        'is_preferred': 'Preferred',
        'intensity_coverage': 'Ion Coverage, %',
        'ions_matched': 'Ions Matched',
        'ion_match_type': 'Ion Type',
        'top_peaks_covered': 'Top-10 Peaks',
        'quality': 'Quality',
        'lcrr': 'LCRR',
        'unconfirmed_ptms': 'Unconfirmed PTMs',
        # charge / pepmass (source + final)
        'charge': 'Source charge',
        'pepmass': 'Source pepmass',
        'override_charge': 'Override Charge',
        'override_pepmass': 'Override Pepmass',
        'isotope_offset': 'Isotope Offset',
        'final_charge': 'Charge',
        'final_pepmass': 'Pepmass',
        # has_ptm
        'has_ptm': 'Has PTM',
        # peptide_match
        'matched_sequence': 'Match Sequence',
        'matched_ppm': 'Match PPM',
        'protein_id': 'Protein',
        'gene': 'Gene',
        'identity': 'Identity',
        'unique_evidence': 'Unique Evidence',
        'matched_peaks': 'Match Ions',
        'matched_top_peaks': 'Match Top-10',
        'matched_ion_type': 'Match Ion Type',
        'matched_sequence_modified': 'Match Seq (modified)',
        'substitution': 'AA Substitution',
    }

    column_filter_mapping = {
        'scans': 'scans',
        'spectre_id': 'spectre_id',
        'identification_id': 'identification_id',
        'protein_id': 'protein_id',
    }

    default_columns = {
        'identification_id', 'spectre_id', 'sample', 'seq_no', 'scans',
        'tool', 'sequence', 'ppm', 'intensity_coverage', 'ions_matched',
        'ion_match_type', 'top_peaks_covered', 'is_preferred',
        'protein_id', 'gene',
        # NEW visible by default:
        'quality', 'lcrr', 'final_charge', 'final_pepmass',
    }

    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Peptide Identifications", plot_callback=plot_callback)

    def get_default_filters(self) -> dict:
        return {
            'identification_id': None,
            'sample_id': 'all',
            'tool_id': 'all',
            'min_score': 0.0,
            'max_ppm': "",
            'sequence': '',
            'canonical_sequence': '',
            'is_preferred': 'None',
            'seq_no': None,
            'scans': None,
            'spectre_id': None,
            'protein_id': None,
            'gene': None,
            'protein_identified': 'All',
            'min_quality': 0.0,
            'has_ptm': 'None',
            'has_substitution': 'None',
        }

    def _build_filter_view(self) -> ft.Control:
        self.identification_id_field = ft.TextField(
            label="Identification ID", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all", width=200
        )
        self.seq_no_field = ft.TextField(
            label="Spectre Seq #", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.scans_field = ft.TextField(
            label="Scans", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.spectre_id_field = ft.TextField(
            label="Spectrum ID", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.DropdownOption(key="all", text="All Tools")],
            value="all", width=200
        )
        self.min_score_field = ft.TextField(
            label="Min Score", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.max_ppm_field = ft.TextField(
            label="Max PPM", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.sequence_field = ft.TextField(
            label="Sequence contains", value="", width=200
        )
        self.canonical_sequence_field = ft.TextField(
            label="Canonical sequence contains", value="", width=200
        )
        self.is_preferred_field = ft.Dropdown(
            label="Is Preferred", value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="True", text="Yes"),
                ft.DropdownOption(key="False", text="No"),
            ],
            width=150,
        )
        self.protein_identified_field = ft.Dropdown(
            label="Protein Identified", value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="True", text="Yes"),
                ft.DropdownOption(key="False", text="No"),
            ],
            width=150,
        )
        self.protein_field = ft.TextField(
            label="Protein id", value="", width=150
        )
        self.gene_field = ft.TextField(
            label="Gene", value="", width=150
        )
        self.min_quality_field = ft.TextField(
            label="Min Quality", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.has_ptm_field = ft.Dropdown(
            label="Has PTM", value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="Yes", text="Yes"),
                ft.DropdownOption(key="No", text="No"),
            ],
            width=150,
        )
        self.has_substitution_field = ft.Dropdown(
            label="Has AA Substitution", value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="Yes", text="Yes"),
                ft.DropdownOption(key="No", text="No"),
            ],
            width=180,
        )
        # Register filter_controls (for set_filters_in_ui)
        self.filter_controls = {
            'identification_id': self.identification_id_field,
            'scans': self.scans_field,
            'spectre_id': self.spectre_id_field,
            'seq_no': self.seq_no_field,
            'protein_id': self.protein_field,
            'gene': self.gene_field,
        }

        return ft.Column([
            ft.Row([
                self.identification_id_field,
                self.sample_dropdown,
                self.seq_no_field,
                self.scans_field,
                self.spectre_id_field,
                self.is_preferred_field,
            ], spacing=10),
            ft.Row([
                self.tool_dropdown,
                self.min_score_field,
                self.max_ppm_field,
                self.sequence_field,
                self.canonical_sequence_field
            ], spacing=10),
            ft.Row([
                self.protein_identified_field,
                self.protein_field,
                self.gene_field
            ]),
            ft.Row([
                self.min_quality_field,
                self.has_ptm_field,
                self.has_substitution_field,
            ], spacing=10),
        ], spacing=10)

    async def _update_filters_from_ui(self):
        self.filter['sample_id'] = self.sample_dropdown.value
        self.filter['tool_id'] = self.tool_dropdown.value
        try:
            self.filter['min_score'] = float(self.min_score_field.value)
        except ValueError:
            self.filter['min_score'] = None
        try:
            self.filter['max_ppm'] = float(self.max_ppm_field.value)
        except ValueError:
            self.filter['max_ppm'] = None

        self.filter['sequence'] = self.sequence_field.value
        self.filter['canonical_sequence'] = self.canonical_sequence_field.value
        self.filter['is_preferred'] = self.is_preferred_field.value
        self.filter['identification_id'] = self.identification_id_field.value
        self.filter['scans'] = self.scans_field.value
        self.filter['seq_no'] = self.seq_no_field.value
        self.filter['spectre_id'] = self.spectre_id_field.value
        self.filter['protein_id'] = self.protein_field.value
        self.filter['gene'] = self.gene_field.value
        self.filter['protein_identified'] = self.protein_identified_field.value
        try:
            self.filter['min_quality'] = float(self.min_quality_field.value)
        except (ValueError, TypeError):
            self.filter['min_quality'] = None
        self.filter['has_ptm'] = self.has_ptm_field.value
        self.filter['has_substitution'] = self.has_substitution_field.value


    async def load_data(self):
        await self._load_filter_options()
        await super().load_data()

    async def _load_filter_options(self):
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.DropdownOption(key="all", text="All Samples")
        ] + [ft.DropdownOption(key=str(s.id), text=s.name) for s in samples]

        tools = await self.project.get_tools()
        self.tool_dropdown.options = [
            ft.DropdownOption(key="all", text="All Tools")
        ] + [ft.DropdownOption(key=str(t.id), text=t.name) for t in tools]

        if self.page:
            self.sample_dropdown.update()
            self.tool_dropdown.update()

    def _build_filter_kwargs(self) -> dict:
        logger.debug(f"filter: {self.filter}")

        kwargs = {}

        if self.filter['sample_id'] != 'all':
            kwargs['sample_id'] = int(self.filter['sample_id'])

        if self.filter['tool_id'] != 'all':
            kwargs['tool_id'] = int(self.filter['tool_id'])

        if self.filter['sequence']:
            kwargs['sequence'] = self.filter['sequence']

        if self.filter['canonical_sequence']:
            kwargs['canonical_sequence'] = self.filter['canonical_sequence']

        if self.filter['is_preferred'] != 'None':
            kwargs['is_preferred'] = self.filter['is_preferred'] == 'True'

        if self.filter['protein_identified'] != 'None':
            kwargs['protein_identified'] = self.filter['protein_identified'] == 'True'

        if self.filter.get('identification_id'):
            try:
                kwargs['identification_id'] = int(self.filter['identification_id'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('scans'):
            try:
                kwargs['scans'] = int(self.filter['scans'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('seq_no'):
            try:
                kwargs['seq_no'] = int(self.filter['seq_no'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('min_score'):
            try:
                kwargs['min_score'] = float(self.filter['min_score'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('max_ppm'):
            try:
                kwargs['max_ppm'] = float(self.filter['max_ppm'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('protein_id'):
            kwargs['protein_id'] = self.filter['protein_id']

        if self.filter.get('gene'):
            kwargs['gene'] = self.filter['gene']

        if self.filter.get('min_quality'):
            try:
                kwargs['min_quality'] = float(self.filter['min_quality'])
            except (ValueError, TypeError):
                pass

        hp = self.filter.get('has_ptm')
        if hp and hp != 'None':
            kwargs['has_ptm'] = hp

        hs = self.filter.get('has_substitution')
        if hs and hs != 'None':
            kwargs['has_substitution'] = hs

        logger.debug(f"kwargs: {kwargs}")
        return kwargs

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        kwargs = self._build_filter_kwargs()

        # limit=-1 means no pagination (export)
        if limit == -1:
            df = await self.project.get_joined_peptide_data(**kwargs)
        else:
            df = await self.project.get_joined_peptide_data(**kwargs, limit=limit, offset=offset)

        if df.empty:
            return df, None

        # Format is_preferred
        if 'is_preferred' in df.columns:
            df['is_preferred'] = df['is_preferred'].apply(lambda x: '✓' if x else '')

        tips = pd.DataFrame(index=df.index)

        # --- final_charge (string with ♻ U+267B) + tooltip ---
        if 'override_charge' in df.columns and 'charge' in df.columns:
            oc = df['override_charge']
            has_override = oc.notna() & ((oc != df['charge']).fillna(True))
            df['_has_oc'] = has_override

            def _fc(row):
                ov = row['override_charge']
                ch = row['charge']
                if row['_has_oc'] and not pd.isna(ov):
                    try:
                        return f"{int(ov)}\u267b"
                    except (ValueError, TypeError):
                        return str(ov)
                if pd.isna(ch):
                    return ""
                try:
                    return f"{int(ch)}"
                except (ValueError, TypeError):
                    return str(ch)

            df['final_charge'] = df.apply(_fc, axis=1)

            def _ftc(row):
                if row['_has_oc'] and not pd.isna(row['charge']):
                    try:
                        return f"Source: {int(row['charge'])}"
                    except (ValueError, TypeError):
                        return f"Source: {row['charge']}"
                return None

            tips['final_charge'] = df.apply(_ftc, axis=1)
            df.drop(columns=['_has_oc'], inplace=True)

        # --- final_pepmass (string with ♻ U+267B) + tooltip ---
        if 'override_pepmass' in df.columns and 'pepmass' in df.columns:
            opm = df['override_pepmass']
            has_opm = opm.notna()
            df['_has_opm'] = has_opm

            def _fp(row):
                ov = row['override_pepmass']
                pm = row['pepmass']
                if row['_has_opm'] and not pd.isna(ov):
                    try:
                        return f"{float(ov):.4f}\u267b"
                    except (ValueError, TypeError):
                        return str(ov)
                if pd.isna(pm):
                    return ""
                try:
                    return f"{float(pm):.4f}"
                except (ValueError, TypeError):
                    return str(pm)

            df['final_pepmass'] = df.apply(_fp, axis=1)

            def _ftp(row):
                if row['_has_opm'] and not pd.isna(row['pepmass']):
                    io_v = row.get('isotope_offset')
                    io_str = ""
                    if io_v is not None and not pd.isna(io_v):
                        try:
                            io_str = f"\nIsotope offset: {int(io_v)}"
                        except (ValueError, TypeError):
                            io_str = ""
                    try:
                        return f"Source: {float(row['pepmass']):.4f}{io_str}"
                    except (ValueError, TypeError):
                        return f"Source: {row['pepmass']}{io_str}"
                return None

            tips['final_pepmass'] = df.apply(_ftp, axis=1)
            df.drop(columns=['_has_opm'], inplace=True)

        # --- sequence tooltip (full seq if truncated, + Source line) ---
        if 'sequence' in df.columns:
            seq = df['sequence']
            src = df['source_sequence'] if 'source_sequence' in df.columns else None
            truncated = seq.str.len() > _MAX_SEQ_LEN

            def _seq_tip(row):
                i = row.name
                parts = []
                if bool(truncated.loc[i]):
                    parts.append(str(seq.loc[i]))
                if src is not None:
                    sv = src.loc[i]
                    if not pd.isna(sv) and sv:
                        parts.append(f"Source: {sv}")
                return "\n".join(parts) if parts else None

            tips['sequence'] = df.apply(_seq_tip, axis=1)
            # truncate the displayed sequence
            df.loc[truncated, 'sequence'] = df.loc[truncated, 'sequence'].str[:_MAX_SEQ_LEN] + '…'

        # --- drop helper isotope_offset (not shown as column) ---
        if 'isotope_offset' in df.columns:
            df.drop(columns=['isotope_offset'], inplace=True)

        # tips → tooltips_df (only columns with at least one non-None value)
        tooltips_df = tips.loc[:, tips.notna().any()] if not tips.empty else None
        return df, tooltips_df

    async def get_total_count(self) -> int:
        kwargs = self._build_filter_kwargs()
        return await self.project.count_joined_peptide_data(**kwargs)
