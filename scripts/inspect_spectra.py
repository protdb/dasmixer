"""
Diagnostic script: inspect spectrum fields relevant for MGF export.

Usage:
    python scripts/inspect_spectra.py <path_to_project.dasmix> [limit]

Example:
    python scripts/inspect_spectra.py ~/data/my_project.dasmix 5
"""

import asyncio
import sys
import json

sys.path.insert(0, "dasmixer-core/src")

from dasmixer.api.project.project import Project


async def inspect_spectra(project_path: str, limit: int = 3):
    async with Project(path=project_path, create_if_not_exists=False) as project:

        # Get all spectre_files
        sf_rows = await project.execute_query(
            "SELECT id, sample_id, format, path FROM spectre_file LIMIT 3"
        )
        if not sf_rows:
            print("No spectra files found in project")
            return

        print(f"Found {len(sf_rows)} spectre_file(s), inspecting first one:")
        sf = sf_rows[0]
        print(f"  spectre_file id={sf['id']}, format={sf['format']}, path={sf['path']}")

        # Get spectrum IDs from this file
        spec_rows = await project.execute_query(
            "SELECT id FROM spectre WHERE spectre_file_id = ? ORDER BY id LIMIT ?",
            [sf["id"], limit],
        )
        if not spec_rows:
            print("  No spectra found in this spectre_file")
            return

        print(f"\n--- Inspecting {len(spec_rows)} spectrum/spectra ---\n")

        for sr in spec_rows:
            spec_id = sr["id"]
            full = await project.get_spectrum_full(spec_id)

            print(f"=== Spectrum id={spec_id} ===")
            print(f"  charge                    : {full.get('charge')!r}  (type: {type(full.get('charge')).__name__})")
            print(f"  charge_array_common_value : {full.get('charge_array_common_value')!r}")

            ca = full.get("charge_array")
            if ca is not None:
                import numpy as np
                print(f"  charge_array type         : {type(ca).__name__}, dtype={ca.dtype}, shape={ca.shape}")
                print(f"  charge_array[:5]          : {ca[:5].tolist()}")
            else:
                print(f"  charge_array              : None")

            print(f"  pepmass                   : {full.get('pepmass')!r}  (type: {type(full.get('pepmass')).__name__})")
            print(f"  intensity                 : {full.get('intensity')!r}")
            print(f"  scans                     : {full.get('scans')!r}")
            print(f"  rt                        : {full.get('rt')!r}")

            all_params = full.get("all_params")
            if all_params:
                print(f"  all_params keys           : {list(all_params.keys())}")
                print(f"  all_params                : {json.dumps(all_params, ensure_ascii=False, default=str)}")
            else:
                print(f"  all_params                : None / empty")

            mz = full.get("mz_array")
            if mz is not None:
                print(f"  mz_array shape            : {mz.shape}, first 3 values: {mz[:3].tolist()}")
            int_arr = full.get("intensity_array")
            if int_arr is not None:
                print(f"  intensity_array shape     : {int_arr.shape}, first 3 values: {int_arr[:3].tolist()}")

            print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    asyncio.run(inspect_spectra(path, limit))
