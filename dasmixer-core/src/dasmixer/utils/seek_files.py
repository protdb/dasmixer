import os
from pathlib import Path
from parse import parse

def seek_files(root: str | Path, accept_template: str, id_template: str) -> list[tuple[Path, str]]:
    """
    Seeks for files to process in given directory.
    :param root: path to the base directory to search
    :param accept_template: template to search files
    :param id_template: template to get sample ID from file_name
    :return: list of tuples (path_to_file, sample_id)
    """
    if type(root) is str:
        root = Path(root)
    res = []
    for file in root.rglob(accept_template):
        parsed = parse(id_template, file.name)
        if parsed is None:
            res.append((file, None))
            continue
        sample_id = parsed.named.get('id', None)
        if sample_id is None:
            sample_id = parsed.fixed[0]
        res.append((file, sample_id))
    return res
