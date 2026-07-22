import csv
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone


def csv_response(data):
    output = StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["FP Depósito de Bebidas"])
    writer.writerow([data["title"]])
    writer.writerow(["Período", data["period"]])
    writer.writerow(["Gerado em", data["generated_at"]])
    writer.writerow(["Gerado por", data["generated_by"]])
    writer.writerow(["Filtros", " | ".join(data.get("filters", [])) or "Nenhum filtro adicional"])
    writer.writerow([])
    writer.writerow(data["columns"])
    if data["report_type"] == "daily_movements":
        for row in data["rows"]:
            writer.writerow([row[k] for k in ["time", "type", "product", "code", "category", "lot", "previous", "quantity", "final", "unit_cost", "total", "reason", "document", "user", "notes"]])
    else:
        writer.writerows(data["rows"])
    if not data["rows"]:
        writer.writerow([data["empty_message"]])
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{data["report_type"]}-{timezone.localdate()}.csv"'
    return response
