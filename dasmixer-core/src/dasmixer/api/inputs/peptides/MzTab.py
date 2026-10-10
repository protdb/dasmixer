"""mzTab identification parser (multi-file / per-ms_run aware)."""

import re

import pandas as pd
from pyteomics.mass import Unimod
from pyteomics.mztab import MzTab
from pyteomics.proforma import GenericModification, parse, to_proforma

from dasmixer.api.project.dataclasses import Protein
from dasmixer.utils.ident_spectra_pairing import resolve_spectra_file_by_location
from dasmixer.utils.logger import logger
from dasmixer.utils.ppm import calculate_ppm

from .base import IdentificationParser


_MOD_PARAM_RE = re.compile(
    r"^\s*\[\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^\]]*)\]\s*$"
)
_SPECTRA_REF_RE = re.compile(r"ms_run\[(\d+)\]\s*[:\-]\s*(scan|index|spectrum)=(\d+)")
_LOCATION_KEY_RE = re.compile(r"ms_run\[(\d+)\][-_]location$")


class MzTabImporter(IdentificationParser):
    """Parser for mzTab PSM files.

    Supports multi-file import: one mzTab file may reference multiple spectra
    files via ``ms_run[N]-location``/``ms_run[N]_location`` MTD keys. Each
    resolved ``ms_run`` yields rows bound to its own ``spectra_file_id``.
    """

    PARSER_ID = "mzTab"
    contain_proteins = True
    can_import_multifile = True
    require_project = True          # needs Project to resolve ms_run -> spectre_file
    spectra_id_field = "seq_no"      # overridden dynamically (scan= -> "scans")

    def __init__(
        self,
        file_path: str,
        collect_proteins: bool = False,
        is_uniprot_proteins: bool = False,
    ):
        super().__init__(file_path, collect_proteins, is_uniprot_proteins)
        self.ms_run_locations: dict[int, str] = {}
        self._mod_tags: dict[str, str] = {}
        self._unimod = None
        self._header: list[str] = []
        self._rows: list[list] = []
        self._psm_df: pd.DataFrame | None = None
        self.ms_run_spectra: dict[int, int] = {}
        self._ignore_ms_run: bool = False

    # --- lazy Unimod (network; may raise when offline) ---
    @property
    def unimod(self):
        if self._unimod is None:
            self._unimod = Unimod()
        return self._unimod

    # ---- MTD reading (raw lines; pyteomics metadata loses accessions) ----
    def _read_mtd(self) -> None:
        self.ms_run_locations = {}
        raw_mods: list[str] = []
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("MTD"):
                    parts = line.rstrip("\r\n").split("\t")
                    if len(parts) < 3:
                        continue
                    key, value = parts[1], parts[2]
                    m = _LOCATION_KEY_RE.match(key)
                    if m:
                        if value.lower().endswith('.gz'):
                            value = value[:-3]
                        self.ms_run_locations[int(m.group(1))] = value
                        continue
                    if key.startswith("fixed_mod[") or key.startswith("variable_mod["):
                        raw_mods.append(value)
                elif line.startswith("COM") or line.strip() == "":
                    continue
                else:
                    # Table data section reached; metadata is over.
                    break
        self._build_mod_tags(raw_mods)

    # ---- modification tag map ----
    def _build_mod_tags(self, raw_mods: list[str]) -> None:
        self._mod_tags = {}
        for raw in raw_mods:
            m = _MOD_PARAM_RE.match(raw)
            if not m:
                continue
            cv, accession, name, _value = (x.strip() for x in m.groups())
            accession = accession.strip()
            if not accession:
                continue
            self._mod_tags[accession] = self._to_proforma_tag(accession, name)

    def _to_proforma_tag(self, accession: str, name: str = "") -> str:
        if accession.startswith("UNIMOD:"):
            if name:
                return name
            uid = int(accession.split(":", 1)[1])
            return self.unimod.by_id(uid)["title"]
        if accession.startswith("MOD:"):
            return "PSI-MOD:" + accession.split(":", 1)[1]
        if accession.startswith("CHEMMOD:"):
            mass = accession.split(":", 1)[1]
            return mass if mass.startswith(("-", "+")) else "+" + mass
        return accession

    # ---- sequence assembly ----
    def _source_sequence(self, row: dict) -> str:
        return row.get("sequence") or ""

    def get_canonical_sequence(self, row: dict) -> str:
        return "".join(aa for aa, _ in parse(self._source_sequence(row))[0])

    def get_modified_sequence(self, seq: str, mods: str) -> str:
        pf_seq, params = parse(seq)
        if not mods:
            return to_proforma(pf_seq, **params)
        params.setdefault("n_term", [])
        params.setdefault("c_term", [])
        params.setdefault("unlocalized_modifications", [])
        n = len([1 for aa, _ in pf_seq])
        for position_part, ident in self._iter_mod_items(mods):
            tag = self._mod_tags.get(ident) or self._to_proforma_tag(ident)
            positions = position_part.split("|")
            if len(positions) > 1 or positions[0] in ("null", ""):
                params["unlocalized_modifications"].append(GenericModification(tag))
                continue
            pos = int(positions[0])
            if pos == 0:
                params["n_term"].append(GenericModification(tag))
            elif pos == n + 1:
                params["c_term"].append(GenericModification(tag))
            else:
                idx = pos - 1
                aa, mods_list = pf_seq[idx]
                mods_list = mods_list or []
                mods_list.append(GenericModification(tag))
                pf_seq[idx] = (aa, mods_list)
        return to_proforma(pf_seq, **params)

    @staticmethod
    def _iter_mod_items(mods: str):
        """Yield (position_part, identifier) pairs from an mzTab modifications string.

        Comma-separated; parameters inside ``[...]`` are discarded together with
        their brackets; ``|``-alternatives in the identifier are dropped.
        """
        cleaned = re.sub(r"\[[^\]]*\]", "", mods)
        for item in cleaned.split(","):
            item = item.strip()
            if not item or "-" not in item:
                continue
            position_part, ident = item.split("-", 1)
            ident = ident.split("|")[0].strip()
            yield position_part.strip(), ident

    # ---- PSM table reading + spectra_ref parsing ----
    def _read_psm_rows(self) -> None:
        mz = MzTab(str(self.file_path), table_format="raw")
        psm = mz["PSM"]
        self._header = list(psm.header)
        self._rows = [list(r) for r in psm.rows]

    @staticmethod
    def _parse_spectra_ref(ref: str) -> tuple[int | None, str | None, int | None]:
        """Parse a spectra_ref value.

        Returns (ms_run_index, kind, value) where kind is "scan" or "index".
        The first reference is used when several are joined by ``|``.
        """
        if not ref:
            return None, None, None
        first = ref.split("|")[0]
        m = _SPECTRA_REF_RE.search(first)
        if not m:
            return None, None, None
        return int(m.group(1)), m.group(2), int(m.group(3))

    def _determine_mapping(self) -> None:
        """Set spectra_id_field from the first non-empty spectra_ref.

        ``index=`` maps to seq_no; ``scan=`` maps to scans.
        """
        if "spectra_ref" not in self._header:
            return
        ref_idx = self._header.index("spectra_ref")
        for row in self._rows:
            ref = row[ref_idx]
            if not ref:
                continue
            _, kind, _ = self._parse_spectra_ref(ref)
            if kind == "index":
                self.spectra_id_field = "seq_no"
            elif kind in ("scan", "spectrum"):
                self.spectra_id_field = "scans"
            return

    # ---- ms_run -> spectra_file resolution ----
    async def _resolve_ms_runs(self) -> None:
        self.ms_run_spectra = {}
        self._ignore_ms_run = False
        if self.spectra_file_id is not None and len(self.ms_run_locations) == 1:
            (idx,) = self.ms_run_locations
            self.ms_run_spectra[idx] = self.spectra_file_id
            self._ignore_ms_run = True
            return
        spectra_files = await self.project.get_spectra_files()
        for idx, location in self.ms_run_locations.items():
            sf_id = resolve_spectra_file_by_location(location, spectra_files)
            if sf_id is None:
                logger.warning(
                    "mzTab ms_run[%s] location '%s' not resolved to any spectra file; rows will be skipped",
                    idx,
                    location,
                )
                continue
            self.ms_run_spectra[idx] = sf_id

    # ---- collapsing per-protein rows ----
    def _collapse_psms(self) -> list[dict]:
        """Collapse per-protein rows into one row per (PSM_ID, spectra_ref).

        Accessions are joined with ``;`` (order-preserving unique); all other
        columns are taken from the first row of each group.
        """
        header = self._header
        rows: list[dict] = [
            {header[i]: raw[i] for i in range(len(header))} for raw in self._rows
        ]
        grouped: dict[tuple, list[dict]] = {}
        order: list[tuple] = []
        for row in rows:
            key = (row.get("PSM_ID"), row.get("spectra_ref"))
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(row)

        result: list[dict] = []
        for key in order:
            group = grouped[key]
            out = dict(group[0])
            accessions = []
            for r in group:
                a = r.get("accession")
                if a is not None and str(a).strip():
                    accessions.append(str(a).strip())
            accession_joined = ";".join(dict.fromkeys(accessions))
            out["accession"] = accession_joined or None
            result.append(out)
        return result

    # ---- output DataFrame ----
    def _build_psm_df(self) -> pd.DataFrame:
        records: list[dict] = []
        for row in self._collapse_psms():
            ref = row.get("spectra_ref") or ""
            ms_run_idx, kind, value = self._parse_spectra_ref(ref)
            if self._ignore_ms_run:
                spectra_file_id = self.spectra_file_id
            else:
                if ms_run_idx is None:
                    continue
                spectra_file_id = self.ms_run_spectra.get(ms_run_idx)
                if spectra_file_id is None:
                    continue
            if self.spectra_id_field == "scans":
                map_val = value if kind in ("scan", "spectrum") else None
            else:
                map_val = value if kind == "index" else None
            if map_val is None:
                continue

            seq = self.get_modified_sequence(
                self._source_sequence(row), row.get("modifications")
            )
            canon = self.get_canonical_sequence(row)
            score = row.get("search_engine_score[1]")
            charge = row.get("charge")
            exp_mz = row.get("exp_mass_to_charge")
            ppm = None
            if charge is not None and exp_mz is not None:
                try:
                    ppm = calculate_ppm(seq, float(exp_mz), int(charge))
                except Exception:
                    ppm = None

            records.append(
                {
                    self.spectra_id_field: map_val,
                    "sequence": seq,
                    "canonical_sequence": canon,
                    "score": float(score) if score is not None else None,
                    "ppm": ppm,
                    "src_file_protein_id": row.get("accession"),
                    "positional_scores": self._positional_scores(row),
                    "spectra_file_id": spectra_file_id,
                    "ms_run_index": ms_run_idx,
                }
            )

        columns = [
            self.spectra_id_field,
            "sequence",
            "canonical_sequence",
            "score",
            "ppm",
            "src_file_protein_id",
            "positional_scores",
            "spectra_file_id",
            "ms_run_index",
        ]
        return pd.DataFrame(records, columns=columns)

    def _positional_scores(self, row: dict):
        """Return per-position confidence scores for this PSM row (list[float] | None).

        Base mzTab returns None. Subclasses that provide per-position scores
        (e.g. CasaNovo) override this method.
        """
        return None

    def _collect_proteins(self) -> None:
        if not self.contain_proteins or self._psm_df is None:
            return
        if "src_file_protein_id" not in self._psm_df.columns:
            return
        for raw_val in self._psm_df["src_file_protein_id"].dropna().unique():
            raw_str = str(raw_val).strip()
            if not raw_str:
                continue
            for pid in raw_str.split(";"):
                pid = pid.strip()
                if pid and pid not in self._proteins:
                    self._proteins[pid] = Protein(
                        id=pid,
                        is_uniprot=self.is_uniprot_proteins,
                    )

    # ---- IdentificationParser interface ----
    async def validate(self) -> bool:
        try:
            self._read_mtd()
            self._read_psm_rows()
            self._determine_mapping()
            await self._resolve_ms_runs()
            self._psm_df = self._build_psm_df()
            self._collect_proteins()
            return True
        except Exception as e:
            logger.exception(e)
            return False

    async def parse_batch(self, batch_size: int = 1000):
        if self._psm_df is None:
            ok = await self.validate()
            if not ok or self._psm_df is None:
                raise ValueError(f"mzTab validation failed for {self.file_path}")
        cursor = 0
        while cursor < len(self._psm_df):
            yield self._psm_df[cursor : cursor + batch_size]
            cursor += batch_size

    async def get_metadata(self) -> dict:
        if not self._rows:
            await self.validate()
        return {
            "num_psms": len(self._rows),
            "ms_runs": len(self.ms_run_locations),
            "resolved_ms_runs": len(self.ms_run_spectra),
        }
