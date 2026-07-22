from io import BytesIO

from django.http import FileResponse
from django.utils import timezone
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .constants import BLACK, GOLD, MUTED
from .pdf_components import _data_table, _footer, _header, _summary_table

def pdf_response(data):
    buffer = BytesIO()
    is_landscape = data["report_type"] == "daily_movements" or len(data.get("columns", [])) > 7
    page_size = landscape(A4) if is_landscape else A4
    available_width = 267 * mm if is_landscape else 186 * mm
    doc = SimpleDocTemplate(buffer, pagesize=page_size, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=10 * mm, bottomMargin=18 * mm, title=data["title"], author="FP Estoque")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Logo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16, alignment=TA_CENTER, textColor=BLACK))
    styles.add(ParagraphStyle(name="Brand", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=BLACK))
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=TA_RIGHT, textColor=BLACK))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, textColor=MUTED))
    styles.add(ParagraphStyle(name="SmallRight", parent=styles["Small"], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=5 * mm, spaceAfter=2 * mm, textColor=BLACK, borderColor=GOLD, borderWidth=0, borderPadding=2))
    styles.add(ParagraphStyle(name="TableHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.3, leading=7.5, textColor=BLACK))
    styles.add(ParagraphStyle(name="TableCell", parent=styles["Normal"], fontSize=6.1, leading=7.3, textColor=BLACK))
    styles.add(ParagraphStyle(name="SummaryLabel", parent=styles["Normal"], fontSize=6.5, textColor=MUTED))
    styles.add(ParagraphStyle(name="SummaryValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=11, textColor=BLACK))
    styles.add(ParagraphStyle(name="Empty", parent=styles["Normal"], fontSize=10, textColor=MUTED, alignment=TA_CENTER, spaceBefore=10 * mm, spaceAfter=10 * mm))

    story = []
    _header(story, data, styles, available_width)
    info = f"Gerado em {data['generated_at']} por {data['generated_by']}"
    filters = " • ".join(data.get("filters") or ["Nenhum filtro adicional"])
    story.extend([Paragraph(info, styles["Small"]), Paragraph(f"Filtros: {filters}", styles["Small"]), Spacer(1, 3 * mm), _summary_table(data.get("summary", {}), styles, available_width), Spacer(1, 4 * mm)])

    if data.get("empty_message"):
        story.append(Paragraph(data["empty_message"], styles["Empty"]))
    elif data["report_type"] == "daily_movements":
        sections = data["sections"]
        story.append(Paragraph("1. Resumo geral do período", styles["Section"]))
        story.append(Paragraph("Os totais acima consolidam as movimentações registradas no banco de dados para o período e os filtros selecionados.", styles["Small"]))
        section_defs = [
            ("2. Entradas de estoque", "entries"),
            ("3. Saídas de estoque", "outputs"),
            ("4. Ajustes realizados", "adjustments"),
            ("5. Inventários e divergências", "divergences"),
            ("7. Cancelamentos e estornos", "reversals"),
        ]
        compact_columns = ["Data/hora", "Tipo", "Produto", "Código", "Lote", "Anterior", "Movimentada", "Final", "Valor", "Usuário", "Motivo"]
        compact_keys = ["time", "type", "product", "code", "lot", "previous", "quantity", "final", "total", "user", "reason"]
        for title, key in section_defs:
            story.append(Paragraph(title, styles["Section"]))
            items = sections[key]
            if key == "divergences":
                rows = [[i["inventory"], i["product"], i["system"], i["counted"], i["difference"], i["justification"]] for i in items]
                story.append(_data_table(["Inventário", "Produto", "Registrado", "Contado", "Divergência", "Justificativa"], rows, styles, available_width=available_width))
            else:
                rows = [[item[k] for k in compact_keys] for item in items]
                story.append(_data_table(compact_columns, rows, styles, available_width=available_width))
        story.append(Paragraph("6. Alertas gerados", styles["Section"]))
        alerts = sections["alerts"]
        alert_rows = []
        for item in alerts["low_stock"]:
            alert_rows.append(["Estoque baixo", item["product"], "-", item["stock"], f"Mínimo: {item['minimum']}"])
        for item in alerts["out_of_stock"]:
            alert_rows.append(["Sem estoque", item["product"], "-", item["stock"], "Crítico"])
        for item in alerts["expiring"]:
            alert_rows.append(["Próximo do vencimento", item["product"], item["lot"], item["quantity"], item["expiration"]])
        for item in alerts["expired"]:
            alert_rows.append(["Vencido", item["product"], item["lot"], item["quantity"], item["expiration"]])
        story.append(_data_table(["Alerta", "Produto", "Lote", "Quantidade", "Detalhe"], alert_rows, styles, available_width=available_width))
        story.extend([PageBreak(), Paragraph("8. Histórico detalhado das movimentações", styles["Section"]), _data_table(data["columns"], data["rows"], styles, daily=True, available_width=available_width)])
    else:
        story.append(_data_table(data["columns"], data["rows"], styles, available_width=available_width))

    doc.build(story, onFirstPage=lambda c, d: _footer(c, d, data), onLaterPages=lambda c, d: _footer(c, d, data))
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{data['report_type']}-{timezone.localdate()}.pdf")
