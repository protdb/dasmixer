"""Reads MaxQuant msms.txt/msmsScans.txt and converts .apl spectra files to enriched MGF + companion CSV identification files."""

import re
import pandas as pd
from pathlib import Path

APL_TYPE_MAP = {
    'peak': {'msms_type': 'MSMS', 'scans_type': 'PEAK', 'header_suffix': '_peak_'},
    'sil0': {'msms_type': 'MULTI-MSMS', 'scans_type': 'MULTI', 'header_suffix': '_multi_'},
}

MSMS_COLS = [
    'Raw file', 'Modified sequence', 'Sequence', 'Charge',
    'Mass error [ppm]', 'Proteins', 'Score', 'Scan number',
    'Fragmentation', 'Mass analyzer', 'Type',
    'Precursor Intensity', 'Retention time',
    'Decoy', 'Potential contaminant',
]

SCANS_COLS = [
    'Raw file', 'Scan number', 'Charge', 'Retention time',
    'Type', 'Fragmentation', 'Mass analyzer',
    'Precursor intensity',
]

MERGE_KEYS = ['Raw file', 'Fragmentation', 'Mass analyzer', 'Scan number']

_index_re = re.compile(r'Index: (\d+)')


def load_and_merge(txt_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    msms = pd.read_csv(
        txt_path / 'msms.txt', sep='\t', usecols=MSMS_COLS, low_memory=False
    )
    scans = pd.read_csv(
        txt_path / 'msmsScans.txt', sep='\t', usecols=SCANS_COLS
    )
    merged = pd.merge(
        scans, msms, on=MERGE_KEYS, how='left', suffixes=('_scans', '_msms')
    )
    return merged, msms


def parse_apl_filename(apl_path: Path) -> tuple[str, str, str, str]:
    parts = apl_path.stem.split('.')
    raw_file = parts[0]
    frag = parts[1]
    analyzer = parts[2]
    apl_type = '.'.join(parts[3:])
    return raw_file, frag, analyzer, apl_type


def build_lookup(
    merged: pd.DataFrame, raw_file: str, frag: str, analyzer: str
) -> dict:
    sub = merged[
        (merged['Raw file'] == raw_file)
        & (merged['Fragmentation'] == frag)
        & (merged['Mass analyzer'] == analyzer)
    ]
    sub = sub.drop_duplicates('Scan number', keep='first')
    sub = sub.set_index('Scan number')
    return sub.to_dict('index')


def _val(row: dict, key: str):
    v = row.get(key)
    if v is None or pd.isna(v):
        return None
    return v


def _write_mgf_spectrum(
    fout, header: str, mz: str, peaks: list[str],
    row: dict | None, scan_num: int
):
    fout.write('BEGIN IONS\n')
    fout.write(f'TITLE={header}\n')

    pepmass = str(mz)
    if row:
        pi = _val(row, 'Precursor Intensity')
        if pi is None:
            pi = _val(row, 'Precursor intensity')
        if pi is not None:
            pepmass += f' {pi}'
    fout.write(f'PEPMASS={pepmass}\n')

    if row:
        seq = _val(row, 'Modified sequence')
        if seq is not None:
            fout.write(f'SEQ={seq}\n')

    charge = None
    if row:
        charge = _val(row, 'Charge_msms')
        if charge is None:
            charge_scans = _val(row, 'Charge_scans')
            if charge_scans is not None and charge_scans != 0:
                charge = charge_scans
    if charge is not None:
        fout.write(f'CHARGE={int(charge)}\n')

    rt = None
    if row:
        rt = _val(row, 'Retention time_msms')
        if rt is None:
            rt = _val(row, 'Retention time_scans')
    if rt is not None:
        fout.write(f'RTINSECONDS={rt * 60:.4f}\n')

    fout.write(f'SCANS={scan_num}\n')

    for p in peaks:
        fout.write(p + '\n')
    fout.write('END IONS\n')


def process_apl(
    apl_path: Path, merged: pd.DataFrame,
    msms_df: pd.DataFrame, output_dir: Path,
    keep_contaminants: bool = False
) -> tuple[int, int]:
    raw_file, frag, analyzer, apl_type = parse_apl_filename(apl_path)

    if 'secpep' in apl_type:
        return 0, 0

    type_info = APL_TYPE_MAP.get(apl_type)
    if type_info is None:
        return 0, 0

    lookup = build_lookup(merged, raw_file, frag, analyzer)

    mgf_path = output_dir / (apl_path.stem + '.mgf')
    written_indexes: set[int] = set()
    spectra_written = 0
    spectra_total = 0

    in_spectrum = False
    header = ''
    index = None
    mz = ''
    peaks: list[str] = []

    with open(apl_path, 'r') as fin, open(mgf_path, 'w') as fout:
        for line in fin:
            line = line.rstrip('\n')

            if line == 'peaklist start':
                in_spectrum = True
                header = ''
                index = None
                mz = ''
                peaks = []
                continue

            if line == 'peaklist end':
                if index is not None:
                    spectra_total += 1
                    if index not in written_indexes:
                        written_indexes.add(index)
                        row = lookup.get(index)
                        _write_mgf_spectrum(
                            fout, header, mz, peaks, row, index
                        )
                        spectra_written += 1
                in_spectrum = False
                continue

            if not in_spectrum:
                continue

            if line.startswith('header='):
                header = line.split('=', 1)[1]
                m = _index_re.search(header)
                if m:
                    index = int(m.group(1))
                continue

            if line.startswith('mz='):
                mz = line.split('=', 1)[1]
                continue

            if line.startswith('charge='):
                continue

            if line.startswith('fragmentation='):
                continue

            if '\t' in line:
                peaks.append(line.replace('\t', ' '))

    csv_path = output_dir / (apl_path.stem + '.csv')
    sub = msms_df[
        (msms_df['Raw file'] == raw_file)
        & (msms_df['Fragmentation'] == frag)
        & (msms_df['Mass analyzer'] == analyzer)
        & (msms_df['Type'] == type_info['msms_type'])
    ]
    sub = sub[sub['Decoy'] != '+']
    if not keep_contaminants:
        sub = sub[sub['Potential contaminant'] != '+']
    sub = sub[[
        'Scan number', 'Modified sequence', 'Sequence',
        'Proteins', 'Mass error [ppm]', 'Score',
    ]].rename(columns={'Scan number': 'MS/MS scan number'})
    sub.to_csv(csv_path, index=False, sep='\t')

    return spectra_written, spectra_total