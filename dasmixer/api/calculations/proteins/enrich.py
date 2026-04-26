from uniprot_meta_tool import UniprotData
from dasmixer.api.project import Project
from typing import AsyncIterator

from dasmixer.utils import logger


async def enrich_protein(project: Project, protein_id: str, force_update: bool = False, overwrite_fasta: bool = True):
    stored_data = await project.get_protein(protein_id)
    if stored_data.uniprot_data and not force_update:
        return
    try:
        uniprot_data = UniprotData(protein_id)
    except Exception as e:
        logger.exception(e)
        return
    stored_data.uniprot_data = uniprot_data
    if not stored_data.gene or overwrite_fasta:
        stored_data.gene = uniprot_data.gene
    if not stored_data.name or overwrite_fasta:
        stored_data.name = uniprot_data.name
    await project.update_protein(stored_data)

async def enrich_proteins(project: Project, force_update: bool = False, overwrite_fasta: bool = True) -> AsyncIterator[tuple[str, int]]:
    """
    perform enrichment of detected proteins from UniProt KB
    :param project: project object to communicate with
    :param force_update: overwrite even if uniprot data exists
    :param overwrite_fasta: overwrite name and gene values from fasta file
    :return: Iterator of tuples (last processed protein_id, total amount of proteins)
    """

    all_idents = await project.get_identified_proteins()
    total = len(all_idents)
    for protein in all_idents:
        await enrich_protein(project, protein, force_update, overwrite_fasta)
        yield protein, total