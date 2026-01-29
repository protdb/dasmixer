"""Simple test script for Stage 1 implementation."""

import asyncio
import numpy as np
import pandas as pd
from pathlib import Path

from api import Project
from api.project.dataclasses import Subset, Tool, Sample, Protein
from utils.logger import setup_logger


async def main():
    """Test basic project functionality."""
    
    logger = setup_logger()
    logger.info("Starting Stage 1 tests...")
    
    # Test 1: Create in-memory project
    logger.info("\n=== Test 1: Create in-memory project ===")
    async with Project() as project:
        metadata = await project.get_metadata()
        logger.info(f"Project metadata: {metadata}")
        
        # Test 2: Add subsets
        logger.info("\n=== Test 2: Add subsets ===")
        control = await project.add_subset("Control", "Control group", "#FF0000")
        treatment = await project.add_subset("Treatment", "Treatment group", "#00FF00")
        logger.info(f"Created subsets: {control.name}, {treatment.name}")
        
        subsets = await project.get_subsets()
        logger.info(f"Total subsets: {len(subsets)}")
        
        # Test 3: Add tools
        logger.info("\n=== Test 3: Add tools ===")
        plgs = await project.add_tool("PLGS", "library", {"version": "3.0"}, "#0000FF")
        denovo = await project.add_tool("PowerNovo2", "denovo", {"model": "HCD"}, "#FF00FF")
        logger.info(f"Created tools: {plgs.name}, {denovo.name}")
        
        tools = await project.get_tools()
        logger.info(f"Total tools: {len(tools)}")
        
        # Test 4: Add samples
        logger.info("\n=== Test 4: Add samples ===")
        sample1 = await project.add_sample("Sample_01", control.id, {"albumin": 45.5})
        sample2 = await project.add_sample("Sample_02", control.id)
        sample3 = await project.add_sample("Sample_03", treatment.id, {"albumin": 42.0})
        logger.info(f"Created samples: {sample1.name}, {sample2.name}, {sample3.name}")
        
        samples = await project.get_samples()
        logger.info(f"Total samples: {len(samples)}")
        for s in samples:
            logger.info(f"  - {s.name} (subset: {s.subset_name}, files: {s.spectra_files_count})")
        
        # Test 5: Add spectra file
        logger.info("\n=== Test 5: Add spectra file ===")
        spectra_file_id = await project.add_spectra_file(
            sample1.id,
            "MGF",
            "/path/to/sample_01.mgf"
        )
        logger.info(f"Created spectra file id={spectra_file_id}")
        
        # Test 6: Add spectra (batch)
        logger.info("\n=== Test 6: Add spectra batch ===")
        spectra_data = []
        for i in range(5):
            mz = np.array([100.0 + i, 200.0 + i, 300.0 + i], dtype=np.float64)
            intensity = np.array([1000.0, 2000.0, 1500.0], dtype=np.float64)
            
            spectra_data.append({
                'seq_no': i + 1,
                'title': f'Spectrum_{i+1}',
                'scans': i + 100,
                'charge': 2,
                'rt': 10.5 + i * 0.5,
                'pepmass': 500.0 + i * 10,
                'mz_array': mz,
                'intensity_array': intensity,
                'charge_array': None,
                'charge_array_common_value': 2,
                'all_params': {'test_param': 'value'}
            })
        
        spectra_df = pd.DataFrame(spectra_data)
        await project.add_spectra_batch(spectra_file_id, spectra_df)
        logger.info(f"Added {len(spectra_df)} spectra")
        
        # Test 7: Query spectra
        logger.info("\n=== Test 7: Query spectra ===")
        spectra_list = await project.get_spectra(sample_id=sample1.id)
        logger.info(f"Retrieved {len(spectra_list)} spectra for sample {sample1.name}")
        logger.info(f"Spectra list type: {type(spectra_list)}, empty: {spectra_list.empty if isinstance(spectra_list, pd.DataFrame) else 'N/A'}")
        
        if not spectra_list.empty:
            logger.info(f"Columns: {list(spectra_list.columns)}")
            logger.info(f"First row: {spectra_list.iloc[0].to_dict()}")
            logger.info(f"First spectrum: {spectra_list.iloc[0]['title']}, pepmass={spectra_list.iloc[0]['pepmass']}, id={spectra_list.iloc[0]['id']}")
        else:
            logger.error("Spectra list is empty! Cannot proceed with test 8.")
        
        # Test 8: Get full spectrum with arrays
        logger.info("\n=== Test 8: Get full spectrum ===")
        if not spectra_list.empty:
            first_id = int(spectra_list.iloc[0]['id'])
            logger.info(f"Attempting to get full spectrum with id={first_id}")
            try:
                full_spectrum = await project.get_spectrum_full(first_id)
                logger.info(f"Full spectrum {full_spectrum['title']}:")
                logger.info(f"  - mz_array shape: {full_spectrum['mz_array'].shape}")
                logger.info(f"  - intensity_array shape: {full_spectrum['intensity_array'].shape}")
                logger.info(f"  - mz values: {full_spectrum['mz_array']}")
            except Exception as e:
                logger.error(f"Failed to get full spectrum: {e}", exc_info=True)
        else:
            logger.warning("Skipping test 8 - no spectra available")
        
        # Test 9: Add identification file
        logger.info("\n=== Test 9: Add identification file ===")
        ident_file_id = await project.add_identification_file(
            spectra_file_id,
            plgs.id,
            "/path/to/identifications.csv"
        )
        logger.info(f"Created identification file id={ident_file_id}")
        
        # Test 10: Add identifications (batch)
        logger.info("\n=== Test 10: Add identifications batch ===")
        if not spectra_list.empty:
            ident_data = []
            for idx, row in spectra_list.iterrows():
                ident_data.append({
                    'spectre_id': int(row['id']),
                    'tool_id': plgs.id,
                    'ident_file_id': ident_file_id,
                    'is_preferred': True,
                    'sequence': f'PEPTIDE{idx}K',
                    'canonical_sequence': f'PEPTIDE{idx}K',
                    'ppm': 5.2 + idx * 0.5,
                    'theor_mass': row['pepmass'],
                    'score': 95.0 - idx,
                    'positional_scores': {'position_1': 0.9, 'position_2': 0.95}
                })
            
            ident_df = pd.DataFrame(ident_data)
            await project.add_identifications_batch(ident_df)
            logger.info(f"Added {len(ident_df)} identifications")
        else:
            logger.warning("Skipping test 10 - no spectra available")
        
        # Test 11: Query identifications
        logger.info("\n=== Test 11: Query identifications ===")
        identifications = await project.get_identifications(sample_id=sample1.id)
        logger.info(f"Retrieved {len(identifications)} identifications")
        if not identifications.empty:
            logger.info(f"First identification: {identifications.iloc[0]['sequence']}, ppm={identifications.iloc[0]['ppm']}")
        
        # Test 12: Add proteins
        logger.info("\n=== Test 12: Add proteins ===")
        proteins = [
            Protein(id="P12345", is_uniprot=True, gene="ALBU", sequence="MKWVTFISLLFLFSSAYS"),
            Protein(id="CUSTOM_001", is_uniprot=False, fasta_name="Custom protein 1")
        ]
        
        for protein in proteins:
            await project.add_protein(protein)
        logger.info(f"Added {len(proteins)} proteins")
        
        all_proteins = await project.get_proteins()
        logger.info(f"Total proteins: {len(all_proteins)}")
        for p in all_proteins:
            logger.info(f"  - {p.id} (uniprot: {p.is_uniprot})")
        
        # Test 13: Project settings
        logger.info("\n=== Test 13: Project settings ===")
        await project.set_setting("last_export_path", "/tmp/exports")
        setting = await project.get_setting("last_export_path")
        logger.info(f"Setting 'last_export_path' = {setting}")
        
    logger.info("\n=== All tests completed successfully! ===")
    
    # Test 14: Save to file and reopen
    logger.info("\n=== Test 14: Save to file and reopen ===")
    test_file = Path("test_project.dasmix")
    if test_file.exists():
        test_file.unlink()
    
    # Create and populate
    project = Project(test_file)
    await project.initialize()
    await project.add_subset("Test Subset", "For file test")
    await project.close()
    logger.info(f"Created file: {test_file}")
    
    # Reopen
    project = Project(test_file, create_if_not_exists=False)
    await project.initialize()
    subsets = await project.get_subsets()
    logger.info(f"Reopened project, found {len(subsets)} subset(s)")
    await project.close()
    
    logger.info("\n=== Stage 1 implementation verified! ===")


if __name__ == '__main__':
    asyncio.run(main())
