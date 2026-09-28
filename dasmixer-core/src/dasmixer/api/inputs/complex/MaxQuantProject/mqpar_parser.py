"""Parsing of MaxQuant mqpar.xml parameter files."""

import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from lxml import etree


@dataclass
class PathInfo:
    path: Path

    @property
    def exists(self) -> bool:
        return self.path.exists()
    @property
    def is_dir(self) -> bool | None:
        if not self.path.exists():
            return None
        else:
            return self.path.is_dir()

@dataclass
class RawFile:
    path: Path
    name: str # without extension
    @property
    def exists(self) -> bool:
        return self.path.exists()

@dataclass
class MQParPaths:
    fasta_path: PathInfo
    custom_txt_path: PathInfo
    index_path: PathInfo
    raw_files: list[RawFile]
    raw_parents: list[PathInfo] # list of unique RawFile.path.parent
    combined_path: PathInfo # raw_parents[0] / combined
    # --- additional path fields found in mqpar ---
    gff3_path: PathInfo # GFF3 annotation file from FastaFileInfo
    protein_grouping_file: PathInfo
    intensity_prediction_folder: PathInfo
    plugin_folder: PathInfo

def _is_windows_path(path_str: str) -> bool:
    """Detect Windows-style paths by drive letter (C:\\, C:/) or backslash separator."""
    return '\\' in path_str or (len(path_str) >= 2 and path_str[1] == ':')

def _pure_path(path_str: str) -> PurePosixPath | PureWindowsPath:
    """Select the matching PurePath class so separators are parsed and preserved correctly."""
    if _is_windows_path(path_str):
        return PureWindowsPath(path_str)
    return PurePosixPath(path_str)

def _extract_stem(path_str: str) -> str:
    if not path_str:
        return ''
    try:
        return _pure_path(path_str).stem
    except Exception:
        parts = path_str.replace('\\', '/').rsplit('/', 1)
        filename = parts[-1] if parts else path_str
        if '.' in filename:
            return filename.rsplit('.', 1)[0]
        return filename

def _extract_parent(path_str: str) -> str:
    if not path_str:
        return ''
    return str(_pure_path(path_str).parent)

def _text(root, xpath: str) -> str:
    return (root.findtext(xpath) or '').strip()

def get_paths_from_mqpar(mqpar_path: str | Path) -> MQParPaths:
    tree = etree.parse(str(mqpar_path))
    root = tree.getroot()

    fasta_str = _text(root, './/fastaFilePath')
    gff3_str = _text(root, './/gff3FilePath')
    custom_txt_str = _text(root, 'customTxtFolder')
    index_str = _text(root, 'fixedSearchFolder')
    protein_grouping_str = _text(root, 'proteinGroupingFile')
    intensity_pred_str = _text(root, 'intensityPredictionFolder')
    plugin_str = _text(root, 'pluginFolder')

    raw_files: list[RawFile] = []
    for string_elem in root.findall('filePaths/string'):
        raw_str = (string_elem.text or '').strip()
        raw_files.append(RawFile(
            path=Path(raw_str),
            name=_extract_stem(raw_str),
        ))

    seen: set[str] = set()
    raw_parents: list[PathInfo] = []
    for rf in raw_files:
        parent_str = _extract_parent(str(rf.path))
        if parent_str not in seen:
            seen.add(parent_str)
            raw_parents.append(PathInfo(path=Path(parent_str)))

    if raw_parents:
        combined_str = str(_pure_path(str(raw_parents[0].path)) / 'combined')
        combined_path = PathInfo(path=Path(combined_str))
    else:
        combined_path = PathInfo(path=Path('combined'))

    return MQParPaths(
        fasta_path=PathInfo(path=Path(fasta_str)),
        custom_txt_path=PathInfo(path=Path(custom_txt_str)),
        index_path=PathInfo(path=Path(index_str)),
        raw_files=raw_files,
        raw_parents=raw_parents,
        combined_path=combined_path,
        gff3_path=PathInfo(path=Path(gff3_str)),
        protein_grouping_file=PathInfo(path=Path(protein_grouping_str)),
        intensity_prediction_folder=PathInfo(path=Path(intensity_pred_str)),
        plugin_folder=PathInfo(path=Path(plugin_str)),
    )

if __name__ == '__main__':
    mqpar_path = sys.argv[1] if len(sys.argv) > 1 else 'data_samples/mqpar.xml'
    print(get_paths_from_mqpar(Path(mqpar_path)))
