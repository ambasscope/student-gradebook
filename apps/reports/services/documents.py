"""Render and combine pages from the single, text-only module-record template."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import re
import json
import math
import unicodedata
from docx import Document

TOKEN = re.compile(r"{{\s*([a-z][a-z0-9_]*)\s*}}")


def paragraphs(container):
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from paragraphs(cell)


def fill_paragraph(paragraph, context):
    runs = list(paragraph.runs)
    text = "".join(run.text for run in runs)
    offsets, cursor = [], 0
    for run in runs:
        offsets.append(cursor)
        cursor += len(run.text)
    for match in reversed(list(TOKEN.finditer(text))):
        key = match.group(1)
        if key not in context:
            raise ValueError("Unknown template placeholder: " + key)
        value = str(context[key])
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise ValueError("Invalid document text")
        start = next(i for i, run in enumerate(runs) if offsets[i] <= match.start() < offsets[i] + len(run.text))
        end = next(i for i, run in enumerate(runs) if offsets[i] <= match.end() - 1 < offsets[i] + len(run.text))
        prefix = runs[start].text[:match.start() - offsets[start]]
        suffix = runs[end].text[match.end() - offsets[end]:]
        runs[start].text = prefix + value + (suffix if start == end else "")
        if start != end:
            for i in range(start + 1, end):
                runs[i].text = ""
            runs[end].text = suffix



class LayoutError(ValueError):
    pass


def check_page_fit(context, template_path=None):
    """Conservative line budget for the supplied paragraph-only A4 template.

    Uses advance widths (not bundled font files), with room for word wrapping
    and differences between Word renderers. It never truncates saved wording.
    """
    if template_path is None:
        from django.conf import settings
        template_path = Path(settings.BASE_DIR) / "apps/reports/document_templates/module-record.docx"
    template_path = Path(template_path)
    document = Document(template_path)
    if document.tables:
        raise ValueError("The module record must use paragraph text only")
    widths = json.loads((template_path.parent / "line-widths.json").read_text())
    section = document.sections[0]
    points = lambda value: value / 12700 if value is not None else 0
    available = points(section.page_width - section.left_margin - section.right_margin)
    normal = document.styles['Normal']
    normal_size = normal.font.size.pt if normal.font.size else 16
    height = 0
    for paragraph in document.paragraphs:
        fill_paragraph(paragraph, context)
        formatting = paragraph.paragraph_format
        width = available - points(formatting.left_indent) - points(formatting.right_indent)
        if width <= 0:
            raise ValueError("Invalid template margins")
        advance = 0
        for run in paragraph.runs:
            size = run.font.size.pt if run.font.size else normal_size
            for char in run.text:
                em = widths.get(str(ord(char)))
                if em is None:
                    em = 0 if unicodedata.combining(char) or ord(char) in {0xfe0e, 0xfe0f} else 1
                advance += em * size
        lines = max(1, math.ceil(advance * 1.05 / width))
        spacing = formatting.line_spacing or normal.paragraph_format.line_spacing
        line_height = spacing.pt if hasattr(spacing, 'pt') else normal_size * 1.15
        height += lines * line_height + points(formatting.space_before) + points(formatting.space_after)
    capacity = points(section.page_height - section.top_margin - section.bottom_margin)
    if height > capacity - 12:
        raise LayoutError("Report text exceeds the one-page layout budget")

def render_module_records(contexts, template_path=None):
    if not contexts or len(contexts) > 50:
        raise ValueError("Choose between 1 and 50 module records")
    if template_path is None:
        from django.conf import settings
        template_path = Path(settings.BASE_DIR) / "apps/reports/document_templates/module-record.docx"
    template_bytes = Path(template_path).read_bytes()
    combined = None
    for context in contexts:
        check_page_fit(context, template_path)
        document = Document(BytesIO(template_bytes))
        # All pages share the same style/section definitions. Imported media or
        # numbered lists would need relationship/numbering remapping, so reject them.
        if len(document.sections) != 1 or document.inline_shapes or document.element.xpath('.//w:numPr | .//w:hyperlink | .//w:altChunk | .//w:drawing | .//w:pict'):
            raise ValueError("Use a single-section, text-only module-record template")
        for paragraph in paragraphs(document):
            fill_paragraph(paragraph, context)
        if combined is None:
            combined = document
        else:
            document.paragraphs[0].paragraph_format.page_break_before = True
            body = combined.element.body
            for element in document.element.body:
                if element.tag.endswith('}sectPr'):
                    continue
                body.insert(len(body) - 1, deepcopy(element))
    output = BytesIO()
    combined.save(output)
    return output.getvalue()
