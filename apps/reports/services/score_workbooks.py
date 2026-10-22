"""Portable XLSX score export using a versioned style template and SpreadsheetML.

Only Python's standard library is needed at runtime. Formulas include cached
results from the shared grading service, so downloads also display in viewers
that do not calculate Excel formulas. Native Excel recalculates edited marks.
"""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import json
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
C = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("x", S)
ET.register_namespace("r", R)
PENDING = "รอการประเมิน"
ROOT = Path(__file__).resolve().parents[1]


def node(parent, tag, attributes=None, text=None):
    element = ET.SubElement(parent, "{" + S + "}" + tag, {key: str(value) for key, value in (attributes or {}).items()})
    if text is not None:
        element.text = str(text)
    return element


def xml(element):
    # OPC package metadata uses the default namespace for compatibility with
    # native Office package readers (as does the original style template).
    if element.tag in {"{" + C + "}Types", "{" + P + "}Relationships"}:
        namespace = element.tag.split("}", 1)[0][1:]
        element = deepcopy(element)
        for child in element.iter():
            child.tag = child.tag.split("}", 1)[-1]
        element.set("xmlns", namespace)
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def column(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def quoted_sheet(name):
    return "'" + name.replace("'", "''") + "'"


def sheet_name(label, used):
    label = re.sub(r"[\x00-\x1f\[\]:*?/\\]", "-", str(label)).strip(" '") or "คะแนน"
    label = label[:31]
    candidate, suffix = label, 1
    while candidate.casefold() in used:
        suffix += 1
        tail = "-" + str(suffix)
        candidate = label[:31 - len(tail)] + tail
    used.add(candidate.casefold())
    return candidate


def clean_text(value):
    # XML 1.0 rejects control characters that may arrive in an imported name.
    return "".join(char for char in str(value) if char in "\t\n\r" or 32 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)


class Sheet:
    def __init__(self, name, widths, styles, metrics, categories):
        self.name, self.widths, self.styles, self.metrics = name, widths, styles, metrics
        self.categories = categories
        self.root = ET.Element("{" + S + "}worksheet")
        properties = node(self.root, "sheetPr")
        node(properties, "pageSetUpPr", {"fitToPage": 1, "autoPageBreaks": 1})
        views = node(self.root, "sheetViews")
        view = node(views, "sheetView", {"showGridLines": 0, "workbookViewId": 0})
        node(view, "pane", {"xSplit": 2, "ySplit": 8, "topLeftCell": "C9", "activePane": "bottomRight", "state": "frozen"})
        node(view, "selection", {"pane": "bottomRight", "activeCell": "C9", "sqref": "C9"})
        node(self.root, "sheetFormatPr", {"defaultRowHeight": 24})
        cols = node(self.root, "cols")
        for index, width in enumerate(widths, 1):
            node(cols, "col", {"min": index, "max": index, "width": width, "customWidth": 1})
        self.data = node(self.root, "sheetData")
        self.rows, self.merges = {}, []

    def row(self, number, height=24):
        if number not in self.rows:
            self.rows[number] = node(self.data, "row", {"r": number, "ht": round(height, 2), "customHeight": 1})
        return self.rows[number]

    def cell(self, row, col, value=None, style="name", formula=None):
        attributes = {"r": column(col) + str(row), "s": self.styles[style]}
        numeric = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
        if formula is not None:
            if not numeric:
                attributes["t"] = "str"
            element = node(self.row(row), "c", attributes)
            node(element, "f", text=formula)
            node(element, "v", text="" if value is None else clean_text(value))
        elif numeric:
            element = node(self.row(row), "c", attributes)
            node(element, "v", text=value)
        elif value is not None:
            attributes["t"] = "inlineStr"
            element = node(self.row(row), "c", attributes)
            inline = node(element, "is")
            text = node(inline, "t", text=clean_text(value))
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        else:
            node(self.row(row), "c", attributes)

    def merge(self, first_row, first_col, last_row, last_col):
        self.merges.append(f"{column(first_col)}{first_row}:{column(last_col)}{last_row}")

    def advance(self, text, size):
        return sum(self.metrics.get(str(ord(char)), 0 if unicodedata.combining(char) else 0.75) * size for char in str(text))

    def text_height(self, text, width, size=16, minimum=24):
        available = max(12, (width * 7 + 5) * 0.75 - 8)
        lines = sum(max(1, math.ceil(self.advance(part, size) * 1.05 / available)) for part in str(text).split("\n"))
        return min(409, max(minimum, lines * (size + 2) + 6))

    def titles(self, context, module, section):
        titles = [
            f"แบบบันทึกคะแนนประกอบรายวิชา {context['course_name']} ปีการศึกษา {context['academic_year']}",
            f"แผนการเรียนรู้ที่ {module['number']} ชื่อแผน {module['name']}",
            f"ชั้นมัธยมศึกษาปีที่ {context['classroom']}",
            section,
        ]
        for row, title in enumerate(titles, 1):
            height = self.text_height(title, sum(self.widths), 18 if row == 1 else 16)
            self.row(row, height)
            self.cell(row, 1, title, "title" if row == 1 else "section" if row == 4 else "subtitle")
            self.merge(row, 1, row, len(self.widths))
        self.row(5, 8)

    def headers(self, labels):
        height = min(240, max(72, max((self.advance(label, 14) for label in labels), default=60) + 14))
        self.row(6, height)
        self.row(7, 40)
        self.row(8, 21)
        self.cell(6, 1, "เลขที่", "heading")
        self.cell(6, 2, "ชื่อ-นามสกุล", "heading")
        self.merge(6, 1, 8, 1)
        self.merge(6, 2, 8, 2)

    def finish(self, final_row):
        # Rows and cells must be sorted even when title merges or rules are added later.
        for row in list(self.data):
            row[:] = sorted(row, key=lambda cell: (len(re.match(r"[A-Z]+", cell.get("r")).group()), re.match(r"[A-Z]+", cell.get("r")).group()))
        self.data[:] = sorted(self.data, key=lambda row: int(row.get("r")))
        merges = node(self.root, "mergeCells", {"count": len(self.merges)})
        for reference in self.merges:
            node(merges, "mergeCell", {"ref": reference})
        node(self.root, "printOptions", {"horizontalCentered": 1, "gridLines": 0, "headings": 0})
        node(self.root, "pageMargins", {"left": 0.5, "right": 0.5, "top": 0.5, "bottom": 0.5, "header": 0.18, "footer": 0.18})
        node(self.root, "pageSetup", {"paperSize": 9, "orientation": "portrait", "fitToWidth": 1, "fitToHeight": 0, "pageOrder": "downThenOver"})
        footer = node(self.root, "headerFooter")
        node(footer, "oddFooter", text='&C&"TH Sarabun New,Regular"&12หน้า &P / &N')
        self.final_row = final_row
        return xml(self.root)


def aggregate_formula(marks, category, weights=None):
    mode = category["aggregation"]
    if mode == "weighted_average":
        return f"SUMPRODUCT({marks},{weights})/SUM({weights})"
    if mode == "average":
        return f"SUM({marks})/{len(category['criteria'])}"
    return f"SUM({marks})"


def evaluate_formula(first, last, row, rule_start, rubric_count, weights=None):
    if first > last:
        return '"' + PENDING + '"'
    marks = f"{column(first)}{row}:{column(last)}{row}"
    maxima = f"{column(first)}$8:{column(last)}$8"
    result = '"' + PENDING + '"'
    # Integer hundredths avoid binary floating-point changing exact band boundaries.
    for index in reversed(range(rubric_count)):
        rule = rule_start + index
        numerator = f"ROUND(SUMPRODUCT({marks},{weights})*10000,0)" if weights else f"ROUND(SUM({marks})*100,0)"
        denominator = f"ROUND(SUMPRODUCT({maxima},{weights})*10000,0)" if weights else f"ROUND(SUM({maxima})*100,0)"
        condition = f"{numerator}*10000>={denominator}*ROUND($B${rule}*100,0)"
        result = f"IF({condition},$C${rule},{result})"
    return f'IF(COUNT({marks})<>{last-first+1},"{PENDING}",{result})'


def render_score_workbook(context, template_dir=None):
    template_dir = Path(template_dir or ROOT / "spreadsheet_templates")
    with ZipFile(template_dir / "score-styles.xlsx") as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    style_cells = json.loads((template_dir / "style-cells.json").read_text())
    prototype = ET.fromstring(parts["xl/worksheets/sheet1.xml"])
    cells = {cell.get("r"): cell.get("s", "0") for cell in prototype.findall(".//{" + S + "}c")}
    styles = {name: cells[reference] for name, reference in style_cells.items()}
    style_root = ET.fromstring(parts["xl/styles.xml"])
    formats = style_root.find("{" + S + "}cellXfs")
    # General displays numeric values using only necessary digits. Summary
    # formulas round their displayed result to the same precision as the app;
    # qualitative formulas continue comparing the original raw marks exactly.
    for key in ("number", "maximum"):
        formats[int(styles[key])].set("numFmtId", "0")
        formats[int(styles[key])].set("applyNumberFormat", "1")
    rotated = deepcopy(formats[int(styles["rotated"])])
    alignment = rotated.find("{" + S + "}alignment")
    if alignment is None:
        alignment = node(rotated, "alignment")
    alignment.set("textRotation", "90")
    alignment.set("wrapText", "1")
    rotated.set("applyAlignment", "1")
    styles["rotated"] = str(len(formats))
    formats.append(rotated)
    fills = style_root.find("{" + S + "}fills")
    grey_fill = len(fills)
    pattern = node(node(fills, "fill"), "patternFill", {"patternType": "solid"})
    node(pattern, "fgColor", {"rgb": "FFD9D9D9"})
    node(pattern, "bgColor", {"indexed": "64"})
    fills.set("count", str(len(fills)))
    for key in ("roll", "name", "number", "evaluation"):
        grey = deepcopy(formats[int(styles[key])])
        grey.set("fillId", str(grey_fill))
        grey.set("applyFill", "1")
        styles["grey_" + key] = str(len(formats))
        formats.append(grey)
    formats.set("count", str(len(formats)))
    metrics = json.loads((ROOT / "document_templates/line-widths.json").read_text())
    sheets, used = [], set()
    for module in context["modules"]:
        categories = module["categories"]
        summary_name = sheet_name(f"{module['number'].zfill(2)}-สรุป", used)
        category_names = [sheet_name(f"{module['number'].zfill(2)}-{index}-{category['name']}", used) for index, category in enumerate(categories, 1)]
        summary = Sheet(summary_name, [5, 33] + [7.5, 10] * len(categories), styles, metrics, categories)
        summary.titles(context, module, "สรุปคะแนนรายหมวด")
        summary.headers([category["name"] for category in categories])
        details = []
        for index, category in enumerate(categories):
            count = len(category["criteria"])
            rubric = category["rubric"]
            aggregation = category["aggregation"]
            method = {"sum": "ผลรวม", "average": "ค่าเฉลี่ย", "weighted_average": "ค่าเฉลี่ยถ่วงน้ำหนัก"}[aggregation]
            target_width = max(108, sum(summary.widths))
            raw_width = max(7.5, (target_width - 5 - 33 - 14) / count) if count else 0
            widths = [5, 33] + [raw_width] * count + [14 if count else target_width - 38]
            detail = Sheet(category_names[index], widths, styles, metrics, categories)
            detail.titles(context, module, "หมวดคะแนน " + category["name"] + " · " + method)
            detail.headers([item["name"] for item in category["criteria"]] + ["ผลการประเมิน"])
            for offset, criterion in enumerate(category["criteria"], 3):
                detail.cell(6, offset, criterion["name"], "rotated")
                detail.cell(7, offset, "คะแนนเต็ม", "heading")
                detail.cell(8, offset, Decimal(criterion["maximum"]), "maximum")
            evaluation_col = count + 3
            detail.cell(6, evaluation_col, "ผลการประเมิน", "rotated")
            detail.merge(6, evaluation_col, 8, evaluation_col)
            rule_title = 12 + len(module["rows"])
            rule_start = rule_title + 2
            detail.cell(rule_title, 1, "เกณฑ์การประเมิน", "section")
            detail.merge(rule_title, 1, rule_title, len(widths))
            detail.cell(rule_title + 1, 2, "ขั้นต่ำ (%)", "rule")
            detail.cell(rule_title + 1, 3, "ผลการประเมิน", "rule")
            for band_index, band in enumerate(rubric):
                detail.row(rule_start + band_index, detail.text_height(band["label"], widths[2], 14))
                detail.cell(rule_start + band_index, 2, Decimal(band["minimum"]), "number")
                detail.cell(rule_start + band_index, 3, band["label"], "rule")
            weight_row = rule_start + len(rubric) + 2
            weights = f"C${weight_row}:{column(count + 2)}${weight_row}" if aggregation == "weighted_average" and count else None
            if weights:
                detail.cell(weight_row, 2, "น้ำหนัก", "rule")
                for raw_col, criterion in enumerate(category["criteria"], 3):
                    detail.cell(weight_row, raw_col, Decimal(criterion["weight"]), "number")
            for offset, student in enumerate(module["rows"], 9):
                if student.get("resigned"):
                    detail.row(offset, detail.text_height(student["name"], widths[1]))
                    detail.cell(offset, 1, student["roll"], "grey_roll")
                    detail.cell(offset, 2, student["name"], "grey_name")
                    for col in range(3, len(widths) + 1):
                        detail.cell(offset, col, style="grey_number")
                    continue
                result = student["categories"][str(category["id"])]
                height = max(detail.text_height(student["name"], widths[1]), detail.text_height(result["evaluation"], widths[-1], 14))
                detail.row(offset, height)
                detail.cell(offset, 1, student["roll"], "roll")
                detail.cell(offset, 2, student["name"], "name")
                for raw_col, criterion in enumerate(category["criteria"], 3):
                    value = student["values"].get(str(criterion["id"]))
                    detail.cell(offset, raw_col, Decimal(value) if value is not None else None, "number")
                detail.cell(offset, evaluation_col, result["evaluation"], "evaluation", evaluate_formula(3, count + 2, offset, rule_start, len(rubric), weights))
            details.append(detail)
            score_col = 3 + index * 2
            summary.cell(6, score_col, category["name"], "rotated")
            summary.merge(6, score_col, 6, score_col + 1)
            summary.cell(7, score_col, {"sum": "รวม\n(เต็ม)", "average": "เฉลี่ย\n(เต็ม)", "weighted_average": "เฉลี่ยถ่วง\n(เต็ม)"}[aggregation], "heading")
            maxima = [Decimal(item["maximum"]) for item in category["criteria"]]
            maximum = sum(maxima, Decimal(0)) if aggregation == "sum" else (maxima[0] if maxima else Decimal(0))
            maxima_reference = f"{quoted_sheet(detail.name)}!C8:{column(count + 2)}8"
            weight_reference = f"{quoted_sheet(detail.name)}!{weights}" if weights else None
            maximum_formula = aggregate_formula(maxima_reference, category, weight_reference) if count else "0"
            summary.cell(8, score_col, maximum, "maximum", maximum_formula)
            summary.cell(7, score_col + 1, "ผลการประเมิน", "heading")
            summary.merge(7, score_col + 1, 8, score_col + 1)
        for row_index, student in enumerate(module["rows"], 9):
            if student.get("resigned"):
                summary.row(row_index, summary.text_height(student["name"], 33))
                summary.cell(row_index, 1, student["roll"], "grey_roll")
                summary.cell(row_index, 2, student["name"], "grey_name")
                for col in range(3, len(summary.widths) + 1):
                    summary.cell(row_index, col, style="grey_number")
                continue
            heights = [summary.text_height(student["name"], 33)] + [summary.text_height(student["categories"][str(category["id"])]["evaluation"], 10, 14) for category in categories]
            summary.row(row_index, max(heights))
            summary.cell(row_index, 1, student["roll"], "roll")
            summary.cell(row_index, 2, student["name"], "name")
            for index, category in enumerate(categories):
                count = len(category["criteria"])
                result = student["categories"][str(category["id"])]
                col = 3 + index * 2
                reference = f"{quoted_sheet(details[index].name)}!C{row_index}:{column(count + 2)}{row_index}"
                weight_row = 12 + len(module["rows"]) + 2 + len(category["rubric"]) + 2
                weights = f"{quoted_sheet(details[index].name)}!C${weight_row}:{column(count + 2)}${weight_row}"
                calculation = aggregate_formula(reference, category, weights) if count else "0"
                formula = f'IF(COUNT({reference})=0,"",ROUND({calculation},2))' if count else '""'
                value = Decimal(result["subtotal"]) if result["subtotal"] is not None else None
                summary.cell(row_index, col, value, "number", formula)
                summary.cell(row_index, col + 1, result["evaluation"], "evaluation", f"{quoted_sheet(details[index].name)}!{column(count + 3)}{row_index}")
        sheets.extend([summary] + details)
    if not sheets:
        raise ValueError("Choose at least one module")
    workbook = ET.Element("{" + S + "}workbook")
    book_views = node(workbook, "bookViews")
    node(book_views, "workbookView", {"activeTab": 0})
    listing = node(workbook, "sheets")
    names = node(workbook, "definedNames")
    relationships = ET.fromstring(parts["xl/_rels/workbook.xml.rels"])
    for item in list(relationships):
        if item.get("Type", "").endswith(("/worksheet", "/sharedStrings")):
            relationships.remove(item)
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    for item in list(content_types):
        if item.get("PartName", "").startswith("/xl/worksheets/") or item.get("PartName") == "/xl/sharedStrings.xml":
            content_types.remove(item)
    output_sheets = {}
    for index, sheet in enumerate(sheets, 1):
        identifier = "scoreSheet" + str(index)
        node(listing, "sheet", {"name": sheet.name, "sheetId": index, "{" + R + "}id": identifier})
        ET.SubElement(relationships, "{" + P + "}Relationship", {"Id": identifier, "Type": R + "/worksheet", "Target": f"worksheets/sheet{index}.xml"})
        ET.SubElement(content_types, "{" + C + "}Override", {"PartName": f"/xl/worksheets/sheet{index}.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"})
        final_row = 8 + len(context["modules"][0]["rows"])
        output_sheets[f"xl/worksheets/sheet{index}.xml"] = sheet.finish(final_row)
        node(names, "definedName", {"name": "_xlnm.Print_Area", "localSheetId": index - 1}, f"{quoted_sheet(sheet.name)}!$A$1:${column(len(sheet.widths))}${final_row}")
        node(names, "definedName", {"name": "_xlnm.Print_Titles", "localSheetId": index - 1}, f"{quoted_sheet(sheet.name)}!$1:$8")
    node(workbook, "calcPr", {"calcId": 191029, "calcMode": "auto", "fullCalcOnLoad": 1, "forceFullCalc": 1})
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            if name in {"xl/workbook.xml", "xl/styles.xml", "xl/_rels/workbook.xml.rels", "[Content_Types].xml", "xl/sharedStrings.xml"} or name.startswith("xl/worksheets/"):
                continue
            archive.writestr(name, content)
        archive.writestr("xl/workbook.xml", xml(workbook))
        archive.writestr("xl/styles.xml", xml(style_root))
        archive.writestr("xl/_rels/workbook.xml.rels", xml(relationships))
        archive.writestr("[Content_Types].xml", xml(content_types))
        for name, content in output_sheets.items():
            archive.writestr(name, content)
    return output.getvalue()
