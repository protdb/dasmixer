import re
from pyteomics.proforma import parse, to_proforma, GenericModification, TagBase
from dasmixer.utils.seqfixer_utils import PTMS, FixedPTM

PTMS = 'S-pyridylethyl+C(20);S-pyridylethyl+C(21);S-pyridylethyl+C(*)'
SEQ = 'AEFAEVSKLVTDLTKVHTECCHGDLLECADDR'


ptm_renames = {
    'S-pyridylethyl': 'Pyridylethyl',
    'Deamidation': 'Deamidated',

}

ptm_parser_re = re.compile(r'([^;+]+?)\+([A-Z*])\((\d+|\*)\)')

ptm_list = ptm_parser_re.findall(PTMS)

proforma_obj = parse(SEQ)

print(proforma_obj)
pf_seq = proforma_obj[0]
pf_params = proforma_obj[1]
print(pf_seq)
print(pf_params)
print(ptm_list)

for name, aa, index in ptm_list:
    ptm_obj = GenericModification(ptm_renames.get(name, name))
    if index != '*':
        proforma_idx = int(index) - 1
        if pf_seq[proforma_idx][0] != aa:
            print(f'Warning: PTM mismatch @ {index}: {pf_seq[proforma_idx]} != {aa}')
        if pf_seq[proforma_idx][1] is None:
            pf_seq[proforma_idx] = (pf_seq[proforma_idx][0], [ptm_obj])
        else:
            pf_seq[proforma_idx][1].append(ptm_obj)
    else:
        pf_params['unlocalized_modifications'].append(ptm_obj)

res_seq = to_proforma(
    pf_seq,
    **pf_params
)


print(res_seq)