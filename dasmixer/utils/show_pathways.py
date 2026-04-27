from uniprot_meta_tool import UniprotData, get_pathways, get_molecular_functions, get_biological_processes

def _get_values_from_list(lines: list[str]) -> tuple[str | None, str | None]:
    if len(lines) == 0:
        return None, None
    first_line = lines[0]
    if len(first_line) >= 32:
        first_line = first_line[:30]+'…'
    if len(lines) > 1:
        first_line+='↵'
    tooltip = '\n'.join(lines)
    return first_line, tooltip

def get_pathways_from_uniprot(data: UniprotData) -> tuple[str| None, str| None]:
    """
    Returns biological pathway data from UniProt
    :param data: UniprotData object
    :return: tuple[str| None, str| None] with values:
    - display data (single short record)
    - tooltip data (all pathways each from new line)
    """
    return _get_values_from_list(get_pathways(data))

def get_mol_functions_from_uniprot(data: UniprotData) -> tuple[str | None, str| None]:
    return _get_values_from_list(get_molecular_functions(data))

def get_biological_processes_from_uniprot(data: UniprotData) -> tuple[str | None, str| None]:
    return _get_values_from_list(get_biological_processes(data))

def get_locations_from_uniprot(data: UniprotData) -> tuple[str | None, str| None]:
    return _get_values_from_list(data.subcellular_locations)