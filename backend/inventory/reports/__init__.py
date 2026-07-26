from .constants import REPORT_TYPES
from .generic import build_report_data as _build_report_data
from .csv_export import csv_response
from .pdf_export import pdf_response
from .xlsx_export import xlsx_response


def build_report_data(report_type, params, user):
    data = _build_report_data(report_type, params, user)
    columns = list(data.get("columns") or [])
    maximum_indexes = [
        index
        for index, column in enumerate(columns)
        if str(column).strip().casefold() in {"máximo", "estoque máximo"}
    ]
    for index in reversed(maximum_indexes):
        columns.pop(index)
        for row in data.get("rows") or []:
            if index < len(row):
                row.pop(index)
    data["columns"] = columns
    return data


__all__ = [
    "REPORT_TYPES",
    "build_report_data",
    "csv_response",
    "pdf_response",
    "xlsx_response",
]
