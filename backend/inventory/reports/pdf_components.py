from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .brand_assets import fp_logo_flowable
from .constants import BLACK, GOLD, LIGHT, MUTED


def _header(story, data, styles, available_width):
    logo = fp_logo_flowable(18 * mm)

    brand = [
        Paragraph("<b>FP DEPÓSITO DE BEBIDAS</b>", styles["Brand"]),
        Paragraph("Sistema interno de controle de estoque", styles["Small"]),
    ]
    title = [
        Paragraph(data["title"], styles["ReportTitle"]),
        Paragraph(f"Período: {data['period']}", styles["SmallRight"]),
    ]

    brand_width = 80 * mm if available_width > 210 * mm else 65 * mm
    logo_width = 22 * mm
    header = Table(
        [[logo, brand, title]],
        colWidths=[logo_width, brand_width, available_width - logo_width - brand_width],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, GOLD),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ]
        )
    )
    story.extend([header, Spacer(1, 5 * mm)])


def _footer(canvas, doc, data):
    canvas.saveState()
    width, _ = doc.pagesize
    canvas.setStrokeColor(GOLD)
    canvas.line(doc.leftMargin, 13 * mm, width - doc.rightMargin, 13 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 8 * mm, f"FP Estoque • Emitido em {data['generated_at']} • {data['generated_by']}")
    canvas.drawRightString(width - doc.rightMargin, 8 * mm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def _summary_table(summary, styles, available_width):
    cells = []
    for key, value in summary.items():
        label = key.replace("_", " ").title()
        cells.append([Paragraph(label, styles["SummaryLabel"]), Paragraph(str(value), styles["SummaryValue"])])
    if not cells:
        return Spacer(1, 1)
    columns_count = 4 if available_width > 210 * mm else 3
    cell_width = available_width / columns_count - 2 * mm
    chunks = [cells[i : i + columns_count] for i in range(0, len(cells), columns_count)]
    rows = []
    for chunk in chunks:
        row = []
        for cell in chunk:
            row.append(Table([[cell[0]], [cell[1]]], colWidths=[cell_width], rowHeights=[5 * mm, 8 * mm]))
        while len(row) < columns_count:
            row.append("")
        rows.append(row)
    table = Table(rows, colWidths=[available_width / columns_count] * columns_count, hAlign="LEFT")
    table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")), ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")), ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return table


def _data_table(columns, rows, styles, daily=False, available_width=267 * mm):
    data = [[Paragraph(str(c), styles["TableHead"]) for c in columns]]
    if daily:
        keys = ["time", "type", "product", "code", "category", "lot", "previous", "quantity", "final", "unit_cost", "total", "reason", "document", "user", "notes"]
        data += [[Paragraph(str(row[k]), styles["TableCell"]) for k in keys] for row in rows]
    else:
        data += [[Paragraph(str(value), styles["TableCell"]) for value in row] for row in rows]
    if len(data) == 1:
        data.append([Paragraph("Nenhum registro encontrado.", styles["TableCell"])] + [""] * (len(columns) - 1))

    widths = [available_width / len(columns)] * len(columns)
    if daily:
        weights = [1.3, 1.2, 2.2, 1.1, 1.5, 1.1, 1.1, 1.1, 1.1, 1.1, 1.2, 2.0, 1.4, 1.5, 2.2]
        total = sum(weights)
        widths = [available_width * w / total for w in weights]
    table = Table(data, repeatRows=1, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), GOLD), ("TEXTCOLOR", (0, 0), (-1, 0), BLACK), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#BBBBBB")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("SPAN", (0, 1), (-1, 1)) if not rows else ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return table
