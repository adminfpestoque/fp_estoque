from io import BytesIO
from numbers import Number
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from django.utils import timezone


DAILY_KEYS = [
    "time",
    "type",
    "product",
    "code",
    "category",
    "lot",
    "previous",
    "quantity",
    "final",
    "unit_cost",
    "total",
    "reason",
    "document",
    "user",
    "notes",
]


def _clean(value):
    if value is None:
        return ""
    return str(value).replace("\x00", "")


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(reference, value, style=0):
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, Number):
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'
    text = escape(_clean(value))
    preserve = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t{preserve}>{text}</t></is></c>'


def _row(row_number, values, styles=None, height=None):
    cells = []
    for index, value in enumerate(values, start=1):
        style = styles[index - 1] if styles and index - 1 < len(styles) else 0
        cells.append(_cell(f"{_column_name(index)}{row_number}", value, style))
    height_attr = f' ht="{height}" customHeight="1"' if height else ""
    return f'<row r="{row_number}"{height_attr}>{"".join(cells)}</row>'


def _rows_for_report(data):
    if data["report_type"] == "daily_movements":
        return [[row.get(key, "") for key in DAILY_KEYS] for row in data["rows"]]
    return [list(row) for row in data["rows"]]


def _column_widths(columns, rows):
    widths = []
    for index, column in enumerate(columns):
        values = [_clean(column)]
        values.extend(_clean(row[index]) for row in rows[:250] if index < len(row))
        longest = max((len(value) for value in values), default=10)
        widths.append(min(max(longest + 2, 11), 38))
    return widths


def _styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="5">
    <font><sz val="11"/><name val="Aptos"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="17"/><name val="Aptos Display"/></font>
    <font><b/><color rgb="FF111111"/><sz val="12"/><name val="Aptos"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Aptos"/></font>
    <font><b/><color rgb="FF111111"/><sz val="11"/><name val="Aptos"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF111111"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF5B400"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF3F4F6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF7D6"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="3">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFE5E7EB"/></left><right style="thin"><color rgb="FFE5E7EB"/></right><top style="thin"><color rgb="FFE5E7EB"/></top><bottom style="thin"><color rgb="FFE5E7EB"/></bottom><diagonal/></border>
    <border><left/><right/><top/><bottom style="thin"><color rgb="FFCCCCCC"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="9">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="4" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="4" fillId="5" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="2" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="4" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _worksheet_xml(data):
    columns = list(data["columns"])
    rows = _rows_for_report(data)
    total_columns = max(len(columns), 8)
    last_column = _column_name(total_columns)
    sheet_rows = []
    merges = []

    current = 1
    sheet_rows.append(_row(current, ["FP Depósito de Bebidas"], [1], height=30))
    merges.append(f"A{current}:{last_column}{current}")
    current += 1
    sheet_rows.append(_row(current, [data["title"]], [2], height=24))
    merges.append(f"A{current}:{last_column}{current}")
    current += 1

    metadata = [
        ("Período", data["period"]),
        ("Data e horário de emissão", data["generated_at"]),
        ("Gerado por", data["generated_by"]),
        ("Filtros utilizados", " | ".join(data.get("filters", [])) or "Nenhum filtro adicional"),
    ]
    for label, value in metadata:
        sheet_rows.append(_row(current, [label, value], [3, 4], height=22))
        merges.append(f"B{current}:{last_column}{current}")
        current += 1

    if data.get("summary"):
        current += 1
        sheet_rows.append(_row(current, ["Resumo do relatório"], [2], height=22))
        merges.append(f"A{current}:{last_column}{current}")
        current += 1
        summary_items = list(data["summary"].items())
        for start in range(0, len(summary_items), 4):
            values = []
            styles = []
            for key, value in summary_items[start:start + 4]:
                values.extend([key.replace("_", " ").capitalize(), value])
                styles.extend([3, 6])
            sheet_rows.append(_row(current, values, styles, height=24))
            current += 1

    current += 1
    table_header_row = current
    sheet_rows.append(_row(current, columns, [5] * len(columns), height=28))
    current += 1

    if rows:
        for row in rows:
            sheet_rows.append(_row(current, row, [7] * len(row), height=24))
            current += 1
    else:
        sheet_rows.append(_row(current, [data.get("empty_message") or "Nenhum dado encontrado."], [6], height=28))
        merges.append(f"A{current}:{last_column}{current}")
        current += 1

    widths = _column_widths(columns, rows)
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    if len(widths) < total_columns:
        cols += f'<col min="{len(widths) + 1}" max="{total_columns}" width="14" customWidth="1"/>'

    merge_xml = ""
    if merges:
        merge_xml = f'<mergeCells count="{len(merges)}">' + "".join(
            f'<mergeCell ref="{reference}"/>' for reference in merges
        ) + "</mergeCells>"

    data_end_row = max(current - 1, table_header_row)
    filter_ref = f"A{table_header_row}:{_column_name(max(len(columns), 1))}{data_end_row}"

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="{table_header_row}" topLeftCell="A{table_header_row + 1}" activePane="bottomLeft" state="frozen"/>
      <selection pane="bottomLeft" activeCell="A{table_header_row + 1}" sqref="A{table_header_row + 1}"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>{cols}</cols>
  <sheetData>{"".join(sheet_rows)}</sheetData>
  <autoFilter ref="{filter_ref}"/>
  {merge_xml}
  <pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
  <pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0" paperSize="9"/>
</worksheet>"""


def _xlsx_bytes(data):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="20000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="Relatório" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(data))
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(_clean(data['title']))}</dc:title>
  <dc:creator>FP Estoque</dc:creator>
  <cp:lastModifiedBy>{escape(_clean(data['generated_by']))}</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{timezone.now().isoformat()}</dcterms:created>
</cp:coreProperties>""",
        )
        archive.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>FP Estoque</Application>
</Properties>""",
        )
    return output.getvalue()


def xlsx_response(data):
    response = HttpResponse(
        _xlsx_bytes(data),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{data["report_type"]}-{timezone.localdate()}.xlsx"'
    )
    return response
