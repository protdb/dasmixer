# Stage 5 Implementation: Report System

## Overview

Implemented complete report system including:
- Database schema updates
- Base report infrastructure
- Report registry
- Sample report example
- PyWebview integration
- GUI components

## Changes Summary

### 1. Database Schema (`api/project/schema.py`)

**Updated:**
- Replaced `generated_report` table with `generated_reports`
- Added `report_parameters` table

**New Tables:**

```sql
-- Generated reports (updated)
CREATE TABLE IF NOT EXISTS generated_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    plots BLOB,  -- pickle + gzip
    tables BLOB,  -- pickle + gzip
    project_settings TEXT,  -- JSON
    tools_settings TEXT,  -- JSON
    report_settings TEXT  -- JSON
);

-- Report parameters
CREATE TABLE IF NOT EXISTS report_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT UNIQUE NOT NULL,
    parameters TEXT NOT NULL
);
```

### 2. Report Infrastructure (`api/reporting/`)

**Created Files:**

1. **`base.py`** - BaseReport class
   - Abstract base for all reports
   - Parameter validation
   - Database save/load
   - Context building for export
   - HTML export implementation
   - Word/Excel export stubs

2. **`registry.py`** - ReportRegistry
   - Registration system for reports
   - Similar to InputTypesRegistry
   - Auto-registration on import

3. **`viewer.py`** - ReportViewer
   - PyWebview integration
   - Multiprocessing wrapper
   - HTML display in separate window

4. **`templates/report.html.j2`** - Jinja2 template
   - HTML report layout
   - Plotly integration
   - Settings display
   - Tables rendering

5. **`reports/sample_report.py`** - Example report
   - Demonstrates report architecture
   - Shows parameter handling
   - Creates sample plots and tables

### 3. Project Integration

**`api/project/mixins/report_mixin.py`** - New mixin:
- `get_generated_reports()` - List saved reports
- `delete_generated_report()` - Delete report
- `save_report_parameters()` - Save user parameters
- `get_report_parameters()` - Load user parameters

**Updated `api/project/project.py`:**
- Added ReportMixin to Project class

### 4. GUI Components (`gui/views/tabs/reports/`)

**Created Files:**

1. **`shared_state.py`**
   - ReportsTabState dataclass
   - Plot settings
   - Selected reports tracking

2. **`settings_section.py`**
   - Global settings UI
   - Font size, dimensions
   - Batch operations

3. **`report_item.py`**
   - Individual report component
   - Parameter editing
   - Generate/View/Export buttons
   - Saved reports dropdown

4. **`reports_tab.py`**
   - Main tab container
   - Reports list
   - Data loading
   - Batch operations

**Updated `gui/views/project_view.py`:**
- Added Reports tab to main window

## Architecture

### Report Lifecycle

1. **Generation:**
   ```python
   report = SampleReport(project)
   await report.generate({'param': 'value'})
   # Automatically saves to DB
   ```

2. **Loading:**
   ```python
   report = await SampleReport.load_from_db(project, report_id)
   ```

3. **Viewing:**
   ```python
   context = report.get_context()
   html = render_template(context)
   ReportViewer.show_report(html)
   ```

4. **Exporting:**
   ```python
   await report.export(output_folder)
   # Creates HTML (Word/Excel stubs)
   ```

### Data Flow

```
User Input (GUI)
    ↓
Report.generate(params)
    ↓
_validate_parameters() → _collect_settings() → _generate_impl()
    ↓
_apply_settings_to_figure() → _save_to_db()
    ↓
Database (generated_reports table)
    ↓
load_from_db() → get_context() → Export/View
```

### Parameter Handling

Reports define parameters via `get_parameter_defaults()`:

```python
@staticmethod
def get_parameter_defaults() -> dict[str, tuple[type, str]]:
    return {
        'max_samples': (int, '10'),
        'include_table': (str, 'Y'),
        'chart_type': (str, 'bar')
    }
```

UI displays these in text field format:
```
max_samples=10
include_table=Y
chart_type=bar
```

### PyWebview Integration

Uses multiprocessing to avoid blocking UI:

```python
def _show_html_in_webview(html_content, title):
    window = webview.create_window(title, html=html_content)
    webview.start()

# Called from main process
process = multiprocessing.Process(target=_show_html_in_webview, args=(html, title))
process.start()
# No join() - independent process
```

## Dependencies

Required packages (already in project):
- jinja2 - HTML templating
- pywebview - Interactive viewing
- plotly - Charts
- pandas - Tables
- pickle, gzip - Serialization

## Usage Examples

### Creating a New Report

```python
from api.reporting.base import BaseReport
import plotly.graph_objects as go
import pandas as pd

class MyReport(BaseReport):
    name = "My Custom Report"
    description = "Custom analysis report"
    icon = "analytics"
    
    @staticmethod
    def get_parameter_defaults():
        return {
            'threshold': (float, '0.05'),
            'max_items': (int, '100')
        }
    
    async def _generate_impl(self, params):
        # Get data
        data = await self.project.get_some_data()
        
        # Create plot
        fig = go.Figure(...)
        
        # Create table
        df = pd.DataFrame(data)
        
        return [("My Plot", fig)], [("My Table", df, True)]

# Register
from api.reporting.registry import registry
registry.register(MyReport)
```

### Using in GUI

Reports are automatically discovered and displayed in the Reports tab.

## Testing

To test the implementation:

1. Open a project with samples
2. Navigate to Reports tab
3. Configure Sample Report parameters
4. Click Generate
5. Select generated report from dropdown
6. Click View to see in PyWebview
7. Click Export to save HTML

## Future Enhancements

1. **Word Export** - Implement `_export_word()` using docxtpl
2. **Excel Export** - Implement `_export_excel()` with tables on sheets
3. **Combined Export** - One document with all selected reports
4. **Progress Bars** - Show generation progress
5. **Report Templates** - Save/load parameter sets
6. **Caching** - Cache intermediate results for large datasets

## Files Changed/Created

### Created:
- `api/reporting/base.py`
- `api/reporting/registry.py`
- `api/reporting/viewer.py`
- `api/reporting/templates/report.html.j2`
- `api/reporting/reports/__init__.py`
- `api/reporting/reports/sample_report.py`
- `api/project/mixins/report_mixin.py`
- `gui/views/tabs/reports/__init__.py`
- `gui/views/tabs/reports/shared_state.py`
- `gui/views/tabs/reports/settings_section.py`
- `gui/views/tabs/reports/report_item.py`
- `gui/views/tabs/reports/reports_tab.py`
- `docs/project/spec/STAGE5_SPEC.md`
- `docs/project/STAGE5_IMPLEMENTATION.md`

### Modified:
- `api/project/schema.py` - Updated tables
- `api/project/mixins/__init__.py` - Added ReportMixin
- `api/project/project.py` - Added ReportMixin to class
- `api/reporting/__init__.py` - Added exports
- `gui/views/project_view.py` - Added Reports tab

## Testing Checklist

- [ ] Database schema creates successfully
- [ ] SampleReport generates without errors
- [ ] Report saves to database
- [ ] Saved reports appear in dropdown
- [ ] View opens PyWebview window
- [ ] HTML export creates valid file
- [ ] Parameters persist between sessions
- [ ] Global settings save/load correctly
- [ ] Batch generation works
- [ ] Error handling works properly

## Notes

- PyWebview must run in separate process to avoid blocking
- All report data serialized with pickle+gzip
- Settings applied at generation time, stored with report
- Template-based HTML generation for extensibility
- Registry pattern allows plugin architecture
