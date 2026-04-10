#!/bin/bash
# Quick test script for Stage 3.2 functionality

echo "==================================="
echo "DASMixer Stage 3.2 - Quick Test"
echo "==================================="
echo ""

# Test 1: Version
echo "Test 1: Show version"
python main.py --version
echo ""

# Test 2: Help
echo "Test 2: Show help"
python main.py --help
echo ""

# Test 3: Create project
echo "Test 3: Create project"
python main.py test_quick.dasmix create
echo ""

# Test 4: List groups
echo "Test 4: List groups (should show Control)"
python main.py test_quick.dasmix subset list
echo ""

# Test 5: Add group
echo "Test 5: Add Treatment group"
python main.py test_quick.dasmix subset add --name "Treatment" --color "#FF5733"
echo ""

# Test 6: Add another group
echo "Test 6: Add Knockout group"
python main.py test_quick.dasmix subset add --name "Knockout" --color "#33FF57" --details "KO samples"
echo ""

# Test 7: List all groups
echo "Test 7: List all groups"
python main.py test_quick.dasmix subset list
echo ""

# Test 8: Delete group
echo "Test 8: Delete Knockout group"
python main.py test_quick.dasmix subset delete --name "Knockout" << EOF
y
EOF
echo ""

# Test 9: Final list
echo "Test 9: Final group list"
python main.py test_quick.dasmix subset list
echo ""

# Test 10: Import help
echo "Test 10: Show import commands"
python main.py test_quick.dasmix import --help
echo ""

echo "==================================="
echo "All tests completed!"
echo "==================================="
echo ""
echo "Project file created: test_quick.dasmix"
echo "You can open it in GUI: python main.py test_quick.dasmix"
echo ""
echo "To test import (requires MGF file):"
echo "python main.py test_quick.dasmix import mgf-file \\"
echo "    --file path/to/file.mgf \\"
echo "    --sample-id 'Sample1' \\"
echo "    --group Control"
echo ""
