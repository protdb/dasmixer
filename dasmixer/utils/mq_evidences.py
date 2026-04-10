import csv
import os
from pathlib import Path

KEEP_KOLS = [
    'Raw file',
    'Sequence',
    'MS/MS scan number',
    'Length',
    'Score',
    'Modified sequence',
    'Missed cleavages',
    'Leading proteins',
    'Leading razor protein',
    'MS/MS m/z',
    'Charge',
    'Retention time',
    'Mass error [ppm]',
]

def preprocess_mq_evidences(source_path: Path, result_folder: Path):
    possible_paths = [
            source_path,
            source_path / 'evidence.txt',
            source_path / 'txt' / 'evidence.txt',
        ]
    path = None
    for pos_path in possible_paths:
        if pos_path.exists():
            path = pos_path
            break
    if path is None:
        raise FileNotFoundError(str(possible_paths))
    os.makedirs(result_folder, exist_ok=True)
    with open(path, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            result_file = result_folder / (row['Raw file']+'.csv')
            mode = 'a' if result_file.exists() else 'w'
            with open(result_file, mode) as fo:
                writer = csv.DictWriter(fo, delimiter='\t', fieldnames=KEEP_KOLS)
                if mode == 'w':
                    writer.writeheader()
                writer.writerow({k: v for k, v in row.items() if k in KEEP_KOLS})

if __name__ == '__main__':
    src_dir = Path('/home/gluck/MS_DATA/evidence_txt/')
    out_root = Path('/home/gluck/MS_DATA/MQ_Evidence_ALL')
    for dataset in src_dir.iterdir():
        out_dir = out_root / dataset.name
        for source in dataset.rglob('evidence.txt'):
            print(f'Processing {source}')
            preprocess_mq_evidences(source, out_dir)

