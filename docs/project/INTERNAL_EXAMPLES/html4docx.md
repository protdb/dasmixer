# Пример использования HTML4docx для экспорта отчетов:

```python
from docx import Document
from html4docx import HtmlToDocx


with open('example.html', 'r') as f:
    HTML = f.read()
doc = Document()

HtmlToDocx().add_html_to_document(HTML, doc)

doc.save('example.docx')
```