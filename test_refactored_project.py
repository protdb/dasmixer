"""Test script to verify refactored Project class."""

import asyncio
from dasmixer.api.project import Project


async def test_basic_operations():
    """Test basic project operations with refactored structure."""
    
    print("=" * 60)
    print("Testing Refactored Project Class")
    print("=" * 60)
    
    # Test 1: Create in-memory project
    print("\n1. Creating in-memory project...")
    async with Project(path=None) as project:
        print("   ✓ Project created and initialized")
        
        # Test 2: Add subset
        print("\n2. Testing SubsetMixin - Adding subset...")
        subset = await project.add_subset(
            name="Control",
            details="Control group",
            display_color="#FF0000"
        )
        print(f"   ✓ Subset created: {subset.name} (id={subset.id})")
        
        # Test 3: Get subsets
        print("\n3. Testing SubsetMixin - Getting subsets...")
        subsets = await project.get_subsets()
        print(f"   ✓ Retrieved {len(subsets)} subset(s)")
        
        # Test 4: Add tool
        print("\n4. Testing ToolMixin - Adding tool...")
        tool = await project.add_tool(
            name="PowerNovo2",
            type="De Novo",
            parser="powernovo2",
            settings={"tolerance": 20.0}
        )
        print(f"   ✓ Tool created: {tool.name} (id={tool.id})")
        
        # Test 5: Add sample
        print("\n5. Testing SampleMixin - Adding sample...")
        sample = await project.add_sample(
            name="Sample_001",
            subset_id=subset.id,
            additions={"albumin": 45.0}
        )
        print(f"   ✓ Sample created: {sample.name} (id={sample.id})")
        
        # Test 6: Get metadata
        print("\n6. Testing ProjectLifecycle - Getting metadata...")
        metadata = await project.get_metadata()
        print(f"   ✓ Metadata retrieved: version={metadata.get('version')}")
        
        # Test 7: Set and get setting
        print("\n7. Testing ProjectLifecycle - Settings...")
        await project.set_setting("test_key", "test_value")
        value = await project.get_setting("test_key")
        print(f"   ✓ Setting retrieved: {value}")
        
        # Test 8: Execute query
        print("\n8. Testing QueryMixin - Raw SQL query...")
        results = await project.execute_query("SELECT COUNT(*) as count FROM subset")
        print(f"   ✓ Query executed: {results[0]['count']} subset(s) in DB")
        
        # Test 9: Get protein count (should be 0)
        print("\n9. Testing ProteinMixin - Get protein count...")
        count = await project.get_protein_count()
        print(f"   ✓ Protein count: {count}")
        
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


async def test_mro():
    """Test Method Resolution Order."""
    print("\n" + "=" * 60)
    print("Method Resolution Order (MRO):")
    print("=" * 60)
    for i, cls in enumerate(Project.__mro__, 1):
        print(f"{i}. {cls.__name__}")
    print("=" * 60)


if __name__ == "__main__":
    # Run MRO test
    asyncio.run(test_mro())
    
    # Run basic operations test
    asyncio.run(test_basic_operations())
