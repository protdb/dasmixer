import sys
sys.path.insert(0, '.')

from utils.seqfixer_utils import PTMS
from api.calculations.ppm.seqfixer import SeqFixer

fixer = SeqFixer(
    ptm_list=PTMS,
    max_ptm=5,
    target_ppm=10,
    override_charges=(1, 5),
    max_isotope_offset=2,
    force_isotope_offset_lookover=True
)

result = fixer.get_ppm(
    sequence='CLN[Deamidated]NQQLHFLHIGSCQDGR',
    pepmass=798.7205,
    mgf_charge=None,
)

print("=== original ===")
o = result.original
print(f"  sequence : {o.sequence}")
print(f"  charge   : {o.charge}")
print(f"  ppm      : {o.ppm}")
print(f"  abs_ppm  : {o.abs_ppm}")
print(f"  iso_off  : {o.isotope_offset}")

print("\n=== override ===")
if result.override:
    for i, v in enumerate(result.override):
        print(f"  [{i}] seq={v.sequence}  charge={v.charge}  ppm={v.ppm:.4f}  iso={v.isotope_offset}")
else:
    print("  None")
