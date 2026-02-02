"""FASTA format parser for protein sequences."""

import re
from pathlib import Path
from typing import AsyncIterator
import pandas as pd
import aiofiles
from uniprot_meta_tool import UniprotData

from utils.logger import logger


class FastaParser:
    """
    Parser for FASTA format protein sequence files.
    
    Supports both UniProt-formatted headers and generic FASTA headers.
    
    Usage:
        parser = FastaParser("proteins.fasta", is_uniprot=True)
        
        if await parser.validate():
            async for batch in parser.parse_batch(batch_size=100):
                # batch is a DataFrame with columns:
                # id, is_uniprot, fasta_name, sequence, gene
                await project.add_proteins_batch(batch)
    """
    
    def __init__(
        self,
        file_path: str,
        is_uniprot: bool = True,
        enrich_from_uniprot: bool = False
    ):
        """
        Initialize FASTA parser.
        
        Args:
            file_path: Path to FASTA file
            is_uniprot: If True, parse UniProt-formatted headers
            enrich_from_uniprot: If True, enrich data from UniProt API (not yet implemented)
        """
        self.file_path = Path(file_path)
        self.is_uniprot = is_uniprot
        self.enrich_from_uniprot = enrich_from_uniprot
        
        # UniProt header regex
        # Format: >sp|P12345|PROT_HUMAN Protein name OS=Homo sapiens GN=GENE PE=1 SV=1
        self.uniprot_id_pattern = re.compile(r'>(?:sp|tr)\|([A-Z0-9]+)\|')
        self.uniprot_gene_pattern = re.compile(r'GN=(\S+)')
    
    async def validate(self) -> bool:
        """
        Validate FASTA file format.
        
        Returns:
            True if file is valid FASTA format, False otherwise
        """
        try:
            if not self.file_path.exists():
                logger.error(f"FASTA file not found: {self.file_path}")
                return False
            
            # Check if file is readable and contains valid FASTA entries
            async with aiofiles.open(self.file_path, 'r') as f:
                found_header = False
                found_sequence = False
                
                async for line in f:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('>'):
                        found_header = True
                    elif found_header and re.match(r'^[A-Z]+$', line, re.IGNORECASE):
                        found_sequence = True
                        break
                
                if not (found_header and found_sequence):
                    logger.error(f"Invalid FASTA format: {self.file_path}")
                    return False
                
                logger.info(f"FASTA file validated: {self.file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error validating FASTA file: {e}", exc_info=True)
            return False
    
    async def parse_batch(self, batch_size: int = 100) -> AsyncIterator[pd.DataFrame]:
        """
        Parse FASTA file in batches.
        
        Args:
            batch_size: Number of proteins per batch
            
        Yields:
            DataFrame with columns: id, is_uniprot, fasta_name, sequence, gene
        """
        batch = []
        current_protein = None
        
        try:
            async with aiofiles.open(self.file_path, 'r') as f:
                async for line in f:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith('>'):
                        # Save previous protein if exists
                        if current_protein is not None:
                            batch.append(current_protein)
                            
                            # Yield batch if full
                            if len(batch) >= batch_size:
                                yield pd.DataFrame(batch)
                                batch = []
                        
                        # Parse header
                        header = line[1:]  # Remove '>'
                        protein_id, gene = self._parse_header(line)  # Pass full line with '>'
                        
                        current_protein = {
                            'id': protein_id,
                            'is_uniprot': self.is_uniprot,
                            'fasta_name': header,
                            'sequence': '',
                            'gene': gene
                        }
                    
                    elif current_protein is not None:
                        # Append to sequence
                        current_protein['sequence'] += line.upper()
                
                # Add last protein
                if current_protein is not None:
                    batch.append(current_protein)
                
                # Yield remaining batch
                if batch:
                    yield pd.DataFrame(batch)
                    
            logger.info(f"Finished parsing FASTA file: {self.file_path}")
            
        except Exception as e:
            logger.error(f"Error parsing FASTA file: {e}", exc_info=True)
            raise
    
    def _parse_header(self, header_line: str) -> tuple[str, str | None]:
        """
        Parse FASTA header to extract protein ID and gene name.
        
        Args:
            header_line: Full FASTA header line (with '>')
            
        Returns:
            Tuple of (protein_id, gene_name)
        """
        if self.is_uniprot:
            # Try to match UniProt format
            id_match = self.uniprot_id_pattern.match(header_line)
            if id_match:
                protein_id = id_match.group(1)
                
                # Extract gene name
                gene_match = self.uniprot_gene_pattern.search(header_line)
                gene = gene_match.group(1) if gene_match else None
                
                return protein_id, gene
        
        # Fallback: use first word after '>' as ID
        header = header_line[1:] if header_line.startswith('>') else header_line
        protein_id = header.split()[0] if header else 'UNKNOWN'
        return protein_id, None
    
    async def enrich_with_uniprot(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich protein data with UniProt API.
        
        Args:
            df: DataFrame with protein data
            
        Returns:
            Enriched DataFrame
            
        Note:
            This is a placeholder for future implementation.
            Currently returns the input DataFrame unchanged.
        """
        if not self.enrich_from_uniprot:
            return df
        else:

        
        logger.warning("UniProt enrichment not yet implemented")
        # TODO: Implement UniProt API integration
        # - Fetch additional data for each protein ID
        # - Add columns: full_name, organism, reviewed, etc.
        
        return df
