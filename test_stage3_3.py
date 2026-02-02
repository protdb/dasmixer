"""Integration tests for Stage 3.3: Peptides tab functionality."""

import pytest
from pathlib import Path
from api.project.project import Project
from api.inputs.proteins.fasta import FastaParser


@pytest.mark.asyncio
async def test_fasta_parser_validation():
    """Test FASTA parser validation functionality."""
    # Test with valid file
    test_file = Path("TEST_DATA/test.fasta")
    
    parser = FastaParser(str(test_file), is_uniprot=True)
    
    # Validate
    is_valid = await parser.validate()
    assert is_valid, "FASTA file should be valid"
    
    print(f"✓ FASTA validation passed")


@pytest.mark.asyncio
async def test_fasta_parser_parsing():
    """Test FASTA parser parsing functionality."""
    test_file = Path("TEST_DATA/test.fasta")
    
    parser = FastaParser(str(test_file), is_uniprot=True)
    
    # Parse
    proteins = []
    async for batch in parser.parse_batch(batch_size=10):
        proteins.extend(batch.to_dict('records'))
    
    assert len(proteins) > 0, "Should parse proteins"
    assert len(proteins) == 5, f"Should parse 5 proteins, got {len(proteins)}"
    
    # Check first protein
    first_protein = proteins[0]
    assert 'id' in first_protein, "Should have id field"
    assert 'sequence' in first_protein, "Should have sequence field"
    assert 'fasta_name' in first_protein, "Should have fasta_name field"
    assert 'gene' in first_protein, "Should have gene field"
    assert 'is_uniprot' in first_protein, "Should have is_uniprot field"
    
    # Check UniProt parsing
    assert first_protein['id'] == 'P12345', f"Should parse UniProt ID correctly, got {first_protein['id']}"
    assert first_protein['gene'] == 'TEST1', f"Should parse gene name correctly, got {first_protein['gene']}"
    assert first_protein['is_uniprot'] == True, "Should mark as UniProt"
    
    print(f"✓ FASTA parsing passed: {len(proteins)} proteins")
    print(f"  First protein: {first_protein['id']} ({first_protein['gene']})")


@pytest.mark.asyncio
async def test_project_protein_storage():
    """Test storing proteins in project."""
    async with Project(path=None) as project:
        # Parse FASTA
        test_file = Path("TEST_DATA/test.fasta")
        parser = FastaParser(str(test_file))
        
        # Import to project
        total_proteins = 0
        async for batch in parser.parse_batch():
            await project.add_proteins_batch(batch)
            total_proteins += len(batch)
        
        # Verify
        proteins = await project.get_proteins()
        assert len(proteins) > 0, "Should store proteins"
        assert len(proteins) == 5, f"Should store 5 proteins, got {len(proteins)}"
        
        # Check retrieval
        first_protein = await project.get_protein('P12345')
        assert first_protein is not None, "Should retrieve protein by ID"
        assert first_protein.id == 'P12345', "Should have correct ID"
        assert first_protein.gene == 'TEST1', "Should have correct gene"
        
        print(f"✓ Protein storage passed: stored {total_proteins} proteins")
        print(f"  Retrieved: {first_protein.id} ({first_protein.gene})")


@pytest.mark.asyncio
async def test_tool_settings_storage():
    """Test tool settings storage and retrieval."""
    async with Project(path=None) as project:
        # Add tool
        tool = await project.add_tool("TestTool", "test_parser")
        
        # Update settings
        tool.settings = {
            'max_ppm': 50.0,
            'min_score': 0.8,
            'min_ion_intensity_coverage': 25.0,
            'use_protein_from_file': False,
            'min_protein_identity': 0.75,
            'denovo_correction': True
        }
        await project.update_tool(tool)
        
        # Retrieve
        loaded_tool = await project.get_tool(tool.id)
        assert loaded_tool.settings['max_ppm'] == 50.0
        assert loaded_tool.settings['min_score'] == 0.8
        assert loaded_tool.settings['min_ion_intensity_coverage'] == 25.0
        assert loaded_tool.settings['use_protein_from_file'] == False
        assert loaded_tool.settings['min_protein_identity'] == 0.75
        assert loaded_tool.settings['denovo_correction'] == True
        
        print(f"✓ Tool settings storage passed")
        print(f"  Settings: {loaded_tool.settings}")


@pytest.mark.asyncio
async def test_ion_settings_storage():
    """Test ion matching settings storage."""
    async with Project(path=None) as project:
        # Save settings
        await project.set_setting('ion_types', 'b,y')
        await project.set_setting('water_loss', '1')
        await project.set_setting('nh3_loss', '0')
        await project.set_setting('ion_ppm_threshold', '20')
        
        # Retrieve
        ion_types = await project.get_setting('ion_types')
        assert ion_types == 'b,y', f"Should store ion types, got {ion_types}"
        
        water_loss = await project.get_setting('water_loss')
        assert water_loss == '1', f"Should store water loss, got {water_loss}"
        
        nh3_loss = await project.get_setting('nh3_loss')
        assert nh3_loss == '0', f"Should store nh3 loss, got {nh3_loss}"
        
        ppm_threshold = await project.get_setting('ion_ppm_threshold')
        assert ppm_threshold == '20', f"Should store ppm threshold, got {ppm_threshold}"
        
        print(f"✓ Ion settings storage passed")
        print(f"  Ion types: {ion_types}")
        print(f"  Water loss: {water_loss}, NH3 loss: {nh3_loss}, PPM: {ppm_threshold}")


@pytest.mark.asyncio
async def test_fasta_parser_invalid_file():
    """Test FASTA parser with invalid file."""
    parser = FastaParser("nonexistent_file.fasta")
    
    is_valid = await parser.validate()
    assert not is_valid, "Should reject nonexistent file"
    
    print(f"✓ Invalid file handling passed")


if __name__ == "__main__":
    import asyncio
    
    print("Running Stage 3.3 Integration Tests\n")
    print("=" * 60)
    
    async def run_all_tests():
        print("\n1. Testing FASTA validation...")
        await test_fasta_parser_validation()
        
        print("\n2. Testing FASTA parsing...")
        await test_fasta_parser_parsing()
        
        print("\n3. Testing protein storage...")
        await test_project_protein_storage()
        
        print("\n4. Testing tool settings storage...")
        await test_tool_settings_storage()
        
        print("\n5. Testing ion settings storage...")
        await test_ion_settings_storage()
        
        print("\n6. Testing invalid file handling...")
        await test_fasta_parser_invalid_file()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
    
    asyncio.run(run_all_tests())
