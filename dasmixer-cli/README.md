# DASMixer CLI

Command-line tools for managing DASMixer projects without a graphical interface.

## Installation

```bash
pip install dasmixer-cli
```

## Usage

```bash
dasmixer-cli --help
dasmixer-cli create path/to/project.dasmix
dasmixer-cli subset list path/to/project.dasmix
dasmixer-cli subset add path/to/project.dasmix --name "Treatment" --color "#FF5733"
dasmixer-cli import mgf-file path/to/project.dasmix --sample "Sample1" --file spectra.mgf
dasmixer-cli import mgf-pattern path/to/project.dasmix --sample "Sample1" --folder ./spectra/ --pattern "*.mgf"
```

## Commands

| Command | Description |
|---|---|
| `create <project>` | Create a new empty project |
| `subset list <project>` | List comparison groups |
| `subset add <project> --name` | Add a comparison group |
| `subset delete <project> --name` | Delete a comparison group |
| `import mgf-file <project>` | Import a single MGF file |
| `import mgf-pattern <project>` | Batch import MGF files by pattern |
| `import ident-file <project>` | Import an identification file |
| `import ident-pattern <project>` | Batch import identification files |

Documentation: https://github.com/protdb/dasmixer