"""
Example script to test report export functionality.

This demonstrates how to:
1. Load a report from database
2. Export to HTML, Word, and Excel
3. Check created files

Usage:
    python export_test_example.py /path/to/project.dasmixer /output/folder
"""

import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dasmixer.api.project.project import Project
from dasmixer.api.reporting.reports.sample_report import SampleReport


async def test_export():
    """Test report export functionality."""
    
    # Check arguments
    if len(sys.argv) < 3:
        print("Usage: python export_test_example.py <project_path> <output_folder>")
        sys.exit(1)
    
    project_path = Path(sys.argv[1])
    output_folder = Path(sys.argv[2])
    
    # Validate paths
    if not project_path.exists():
        print(f"Error: Project file not found: {project_path}")
        sys.exit(1)
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"Opening project: {project_path}")
    print(f"Output folder: {output_folder}")
    print("-" * 60)
    
    # Open project
    async with Project(project_path) as project:
        print("✓ Project opened")
        
        # Check if we have saved reports
        saved_reports = await project.get_generated_reports("Sample Report")
        
        if not saved_reports:
            print("\nNo saved reports found. Generating new one...")
            
            # Create and generate report
            report = SampleReport(project)
            params = {
                'max_samples': '5',
                'include_table': 'Y',
                'chart_type': 'bar'
            }
            
            await report.generate(params)
            print("✓ Report generated")
            
            # Reload saved reports
            saved_reports = await project.get_generated_reports("Sample Report")
        
        # Use the first saved report
        report_id = saved_reports[0]['id']
        report_date = saved_reports[0]['created_at']
        
        print(f"\nUsing report ID: {report_id}")
        print(f"Created at: {report_date}")
        print("-" * 60)
        
        # Load report from DB
        print("\nLoading report from database...")
        report = await SampleReport.load_from_db(project, report_id)
        print("✓ Report loaded")
        
        # Check report data
        print(f"\nReport contains:")
        print(f"  - Plots: {len(report._plots) if report._plots else 0}")
        print(f"  - Tables: {len(report._tables) if report._tables else 0}")
        
        # Test HTML rendering
        print("\nRendering HTML...")
        html = report._render_html()
        print(f"✓ HTML rendered ({len(html)} characters)")
        
        # Test context generation
        print("\nGenerating export context...")
        context = report.get_context()
        print(f"✓ Context generated:")
        print(f"  - Figures: {len(context['figures'])}")
        print(f"  - Tables: {len(context['tables'])}")
        print(f"  - Settings included: {context['show_parameters']}")
        
        # Export to all formats
        print("\nExporting to all formats...")
        created_files = await report.export(output_folder)
        
        print("\n✓ Export completed! Created files:")
        for format_name, file_path in created_files.items():
            size_kb = file_path.stat().st_size / 1024
            print(f"  - {format_name.upper()}: {file_path.name} ({size_kb:.1f} KB)")
        
        # Verify files exist and are not empty
        print("\nVerifying files...")
        all_valid = True
        for format_name, file_path in created_files.items():
            if not file_path.exists():
                print(f"  ✗ {format_name}: File not found!")
                all_valid = False
            elif file_path.stat().st_size == 0:
                print(f"  ✗ {format_name}: File is empty!")
                all_valid = False
            else:
                print(f"  ✓ {format_name}: Valid")
        
        if all_valid:
            print("\n" + "=" * 60)
            print("SUCCESS! All files exported correctly.")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("WARNING! Some files have issues.")
            print("=" * 60)
            sys.exit(1)


def main():
    """Main entry point."""
    try:
        asyncio.run(test_export())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
