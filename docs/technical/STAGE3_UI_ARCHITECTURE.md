# Stage 3 UI Architecture

Visual documentation of the Samples Tab architecture.

---

## UI Layout

```
┌────────────────────────────────────────────────────────────┐
│ DASMixer - Mass Spectrometry Data Integration             │
│ ☰ File                                                     │
└────────────────────────────────────────────────────────────┘

┌─ SAMPLES TAB ──────────────────────────────────────────────┐
│                                                            │
│ ┌─ Comparison Groups ─────────────────────────────────┐   │
│ │ 📁 Control                      3 samples            │   │
│ │ 📁 Treatment                    3 samples            │   │
│ │                                                      │   │
│ │ [+ Add Group] [🗑️ Delete Selected]                  │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                            │
│ ┌─ Import Spectra ────────────────────────────────────┐   │
│ │ [📤 Import Spectra Files]                           │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                            │
│ ┌─ Identification Tools ──────────────────────────────┐   │
│ │ 🧬 PowerNovo2        2 file(s) • Type: PowerNovo2   │   │
│ │                     [📤 Import Identifications] ←────┼──┐│
│ │                                                      │  ││
│ │ 🧬 MaxQuant          0 file(s) • Type: MaxQuant     │  ││
│ │                     [📤 Import Identifications] ←────┼──┤│
│ │                                                      │  ││
│ │ [+ Add Tool]                                        │  ││
│ └──────────────────────────────────────────────────────┘  ││
│                                                           ││
│ ┌─ Samples ────────────────────────────────────────────┐  ││
│ │ 🧪 Sample01                                          │  ││
│ │    Group: Control • Files: 1 • ✓ PowerNovo2, ✓ MQ   │  ││
│ │                                                      │  ││
│ │ 🧪 Sample02                                          │  ││
│ │    Group: Treatment • Files: 1 • ✓ PowerNovo2       │  ││
│ │                                                      │  ││
│ │ 🧪 Sample03                                          │  ││
│ │    Group: Control • Files: 1 • No identifications   │  ││
│ └──────────────────────────────────────────────────────┘  ││
│                                                           ││
└───────────────────────────────────────────────────────────┘│
                                                             │
  Each Tool has Import button ───────────────────────────────┘
```

---

## Component Hierarchy

```
SamplesTab (Container)
│
├── groups_section (Container)
│   ├── "Comparison Groups" (Text)
│   ├── groups_list (Column)
│   │   └── [ListTile for each Group]
│   └── Row([Add Group, Delete])
│
├── import_section (Container)
│   ├── "Import Spectra" (Text)
│   └── [Import Spectra Files] (Button)
│
├── tools_section (Container)  ← NEW!
│   ├── "Identification Tools" (Text)
│   ├── tools_list (Column)
│   │   └── [ListTile with Import button for each Tool]
│   └── [Add Tool] (Button)
│
└── samples_container (Container)
    ├── "Samples" (Text)
    └── Column([ListTile for each Sample])
```

---

## State Management

### Component State

```python
class SamplesTab:
    # UI Components
    groups_list: ft.Column      # Dynamic list of groups
    tools_list: ft.Column       # Dynamic list of tools
    samples_container: ft.Container  # Dynamic samples display
    
    # Data
    project: Project            # Project instance
```

### Refresh Methods

```python
async def did_mount_async():
    """Called when tab is first mounted"""
    await refresh_groups()    # Load groups
    await refresh_tools()     # Load tools
    await refresh_samples()   # Load samples

# Called after:
# - Import spectra  → refresh_groups() + refresh_samples()
# - Import idents   → refresh_tools() + refresh_samples()
# - Add group       → refresh_groups()
# - Add tool        → refresh_tools()
```

---

## Data Flow Diagrams

### Import Spectra Flow

```
User Action                  UI Method                    Project API
───────────                  ─────────                    ───────────

[Import Spectra] ──────→ show_import_mode_dialog()
                              ↓
                         Choose: Single/Pattern
                              ↓
                    show_import_pattern_dialog()
                              ↓
                    Select: Folder, Pattern, Parser, Group
                              ↓
                    [Preview Files] → seek_files()
                              ↓
                         [Import] ──────→ import_spectra_files()
                                                ↓
                                          For each file:
                                            get_sample_by_name()
                                            OR
                                            add_sample(subset_id) ──→ INSERT sample
                                                ↓
                                            add_spectra_file() ──→ INSERT spectre_file
                                                ↓
                                            Parser.parse_batch()
                                                ↓
                                            add_spectra_batch() ──→ INSERT spectre (×N)
                                                ↓
                                          refresh_samples()
                                          refresh_groups()
```

### Import Identifications Flow

```
User Action                  UI Method                    Project API
───────────                  ─────────                    ───────────

[Add Tool] ──────────→ show_add_tool_dialog()
                              ↓
                    Select: Name, Parser (from registry)
                              ↓
                    [Add] ───────────→ project.add_tool() ──→ INSERT tool
                              ↓
                    refresh_tools()


[Import Identifications]  show_import_mode_dialog(tool_id)
  on Tool ────────────→         ↓
                         Choose: Single/Pattern
                              ↓
                    show_import_pattern_dialog(tool_id)
                              ↓
                    Select: Folder, Pattern
                    (Parser = tool.type, автоматически!)
                              ↓
                         [Import] ──────→ import_identification_files(tool_id)
                                                ↓
                                          get_tool(tool_id)
                                          parser = registry.get_parser(tool.type)
                                                ↓
                                          For each file:
                                            get_sample_by_name() ──→ SELECT sample
                                                ↓
                                            get_spectra_files() ──→ SELECT spectre_file
                                                ↓
                                            add_identification_file() ──→ INSERT ident_file
                                                ↓
                                            get_spectra_idlist(by=parser.spectra_id_field)
                                                ↓
                                            Parser.parse_batch()
                                                ↓
                                            batch['spectre_id'] = map(spectra_mapping)
                                            batch['tool_id'] = tool.id
                                                ↓
                                            add_identifications_batch() ──→ INSERT identification (×N)
                                                ↓
                                          refresh_tools()
                                          refresh_samples()
```

---

## Registry Integration

### Spectra Parsers

```
registry.get_spectra_parsers()
    ↓
{'MGF': MGFParser, 'MZML': MZMLParser, ...}
    ↓
Dropdown Options:
  - MGF - Mascot Generic Format
  - MZML - ...
    ↓
User selects: "MGF"
    ↓
parser_class = registry.get_parser("MGF", "spectra")
    ↓
parser = MGFParser(file_path)
```

### Identification Parsers

```
registry.get_identification_parsers()
    ↓
{'PowerNovo2': PowerNovo2Importer, 'MaxQuant': MaxQuantParser, ...}
    ↓
User adds Tool:
  Name: "PowerNovo2"
  Type: "PowerNovo2" ← From registry
    ↓
Tool stored in DB (id=5, type="PowerNovo2")
    ↓
User imports for Tool(id=5):
    ↓
tool = get_tool(5)
tool.type = "PowerNovo2"
    ↓
parser_class = registry.get_parser(tool.type, "identification")
    ↓
parser = PowerNovo2Importer(file_path)
```

---

## Error Handling Strategy

### Validation Chain

```
Import Request
    ↓
Check Prerequisites
    ├→ Spectra: Group exists?
    └→ Identifications: Sample exists? Spectra files exist?
        ↓
Select Files
    ↓
Validate File Format
    ├→ parser.validate()
    └→ If invalid: Show error, stop
        ↓
Import Batches
    ├→ For spectra: direct insert
    └→ For identifications: map IDs, filter non-matching
        ↓
Update UI
    └→ refresh_*() methods
```

### Error Messages

| Error | Message | Action |
|-------|---------|--------|
| No groups | "Create at least one group first" | Stop |
| No samples | "Import spectra first" | Stop |
| Invalid file | "Invalid file format: {name}" | Stop |
| Sample not found | "Sample '{id}' not found" | Stop |
| No spectra files | "No spectra files for sample" | Stop |

---

## Performance Considerations

### Batch Processing

```python
# Spectra: 1000 per batch
async for batch in parser.parse_batch(batch_size=1000):
    await project.add_spectra_batch(file_id, batch)
    # Progress update

# Identifications: 1000 per batch
async for batch in parser.parse_batch(batch_size=1000):
    batch['spectre_id'] = batch['scans'].map(mapping)
    await project.add_identifications_batch(batch)
    # Progress update
```

### Async Operations

All database operations are async:
- Non-blocking UI
- Progress updates during import
- Can be cancelled (future improvement)

### Memory Management

- Batched processing (not all in memory)
- Numpy arrays compressed in DB
- Streaming parsers

---

## Extension Points

### Adding New Parsers

```python
# 1. Create parser class
class MZMLParser(SpectralDataParser):
    async def validate(self): ...
    async def parse_batch(self): ...

# 2. Register in api/inputs/__init__.py
registry.add_spectra_parser("MZML", MZMLParser)

# 3. Done! Appears in UI automatically
```

### Adding New Tool

```python
# 1. User clicks "Add Tool"
# 2. Selects parser from registry
# 3. Tool created with parser as type
# 4. Import button appears automatically
```

---

## Visual Mock-ups

### Add Group Dialog

```
┌─ Add Comparison Group ────────────┐
│                                   │
│ Group Name: [Control____________] │
│                                   │
│ Description: [Default control    │
│ (optional)    group              ]│
│                                   │
│ Color (hex): [3B82F6____________] │
│                                   │
│              [Cancel]  [Add]      │
└───────────────────────────────────┘
```

### Add Tool Dialog

```
┌─ Add Identification Tool ─────────┐
│                                   │
│ Tool Name: [PowerNovo2__________] │
│                                   │
│ Parser:    [PowerNovo2 ▼       ] │
│                                   │
│ Color (hex): [9333EA____________] │
│                                   │
│ Tool represents an identification │
│ method (e.g., de novo, database)  │
│                                   │
│              [Cancel]  [Add]      │
└───────────────────────────────────┘
```

### Import Dialog (Pattern Matching)

```
┌─ Import Spectra - Pattern Matching ─────────────────┐
│                                                      │
│ Folder: [/path/to/files____________] [📁]          │
│                                                      │
│ File pattern: [*.mgf____] Sample ID: [{id}*.mgf___] │
│                                                      │
│ Parser: [MGF - Mascot Generic ▼] Group: [Control ▼] │
│                                                      │
│ [🔍 Preview Files]                                   │
│                                                      │
│ ┌─ Preview ───────────────────────────────────────┐ │
│ │ Found 3 file(s):                                │ │
│ │ 📄 sample01.mgf    Sample ID: sample01          │ │
│ │ 📄 sample02.mgf    Sample ID: sample02          │ │
│ │ 📄 sample03.mgf    Sample ID: sample03          │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│                            [Cancel]  [⬇️ Import]     │
└──────────────────────────────────────────────────────┘
```

### Progress Dialog

```
┌─ Importing Spectra ──────────────┐
│                                  │
│ Importing sample01.mgf (1/3)... │
│                                  │
│ [████████████░░░░░░░░] 60%      │
│                                  │
│ Imported 1523 spectra (batch 2) │
│                                  │
└──────────────────────────────────┘
```

---

## Component Interaction Matrix

| Component | Triggers | Updates | Reads From |
|-----------|----------|---------|------------|
| Groups List | add_group, delete_group | refresh_groups() | project.get_subsets() |
| Tools List | add_tool | refresh_tools() | project.get_tools() |
| Samples List | import_spectra, import_ident | refresh_samples() | project.get_samples() |
| Import Spectra | User click | Creates samples | registry, project |
| Import Idents | Tool's button click | Links to tool | tool_id, registry, project |

---

## Method Call Graph

```
SamplesTab.__init__()
    └→ _build_content()
        ├→ groups_section
        ├→ import_section
        ├→ tools_section
        └→ samples_container

page.add(SamplesTab)
    └→ did_mount_async()
        ├→ refresh_groups()
        │   ├→ project.get_subsets()
        │   ├→ project.get_samples(subset_id)
        │   └→ groups_list.update()
        │
        ├→ refresh_tools()
        │   ├→ project.get_tools()
        │   ├→ project.get_identification_files(tool_id)
        │   └→ tools_list.update()
        │
        └→ refresh_samples()
            ├→ project.get_samples()
            ├→ project.get_spectra_files(sample_id)
            ├→ project.get_identification_files(spectra_file_id)
            └→ samples_container.update()

User clicks "Import Spectra Files"
    └→ show_import_mode_dialog(e, "spectra", None)
        └→ show_import_pattern_dialog("spectra", None)
            └→ import_spectra_files(files, subset_id, parser)
                ├→ project.add_sample()
                ├→ project.add_spectra_file()
                └→ project.add_spectra_batch()

User clicks "Add Tool"
    └→ show_add_tool_dialog(e)
        └→ project.add_tool(name, type=parser)
            └→ refresh_tools()

User clicks "Import Identifications" on Tool
    └→ show_import_mode_dialog(e, "identifications", tool_id)
        └→ show_import_pattern_dialog("identifications", tool_id)
            └→ import_identification_files(files, tool_id)
                ├→ project.get_tool(tool_id)
                ├→ project.add_identification_file(tool_id=tool_id)
                └→ project.add_identifications_batch()
```

---

## Database Schema Mapping

### UI → Database

```
Comparison Group
    name: "Control"
    ↓
    INSERT INTO subset (name, details, display_color)
    ↓
    subset.id = 1

Tool
    name: "PowerNovo2"
    type: "PowerNovo2"  ← Parser name from registry
    ↓
    INSERT INTO tool (name, type, settings, display_color)
    ↓
    tool.id = 5

Sample
    name: "Sample01"
    subset_id: 1  ← FK to subset
    ↓
    INSERT INTO sample (name, subset_id)
    ↓
    sample.id = 10

Spectra File
    sample_id: 10  ← FK to sample
    format: "MGF"
    ↓
    INSERT INTO spectre_file (sample_id, format, path)
    ↓
    spectre_file.id = 20

Identification File
    spectre_file_id: 20  ← FK to spectre_file
    tool_id: 5           ← FK to tool (from UI!)
    ↓
    INSERT INTO identification_file (spectre_file_id, tool_id, file_path)
    ↓
    identification_file.id = 30

Identification
    spectre_id: 123      ← FK to spectre
    tool_id: 5           ← FK to tool (from UI!)
    ident_file_id: 30    ← FK to identification_file
    ↓
    INSERT INTO identification (...)
```

---

## Critical Design Decisions

### 1. Tool determines Parser

**Rationale:**
- One Tool = one identification method
- Consistent parser for all files of a Tool
- Simplifies UI (no parser selection on import)
- Allows tool-specific settings

### 2. tool_id in UI, not auto-created

**Rationale:**
- Explicit user control
- Support multiple Tools in one project
- Enable comparison of methods
- Clear separation of results

### 3. Separate import buttons per Tool

**Rationale:**
- Clear which Tool data belongs to
- Prevents accidental mixing
- Visual feedback (file count per Tool)

### 4. Samples must exist before identifications

**Rationale:**
- Identifications link to spectra
- Spectra link to samples
- Enforces correct order: Spectra → Identifications

---

## Future Enhancements

### Planned (Stage 4+):

1. **Tool Settings**
   ```python
   tool.settings = {
       'ppm_threshold': 10,
       'min_score': 0.5,
       ...
   }
   ```

2. **Tool Statistics**
   ```
   PowerNovo2
     • 2 files
     • 5,432 identifications
     • Avg score: 0.87
   ```

3. **Delete Tool**
   - Check for identifications
   - Cascade or warn

4. **Edit Tool**
   - Change name, color
   - Update settings

5. **Tool Comparison**
   - Venn diagram
   - Overlap statistics

---

**Version:** 1.0  
**Last Updated:** 2026-01-30  
**Author:** Goose AI
