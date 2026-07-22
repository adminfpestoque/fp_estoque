from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..permissions import IsInventoryUser
from ..reports import build_report_data, xlsx_response
from ..services import audit


@api_view(["GET"])
@permission_classes([IsInventoryUser])
def report_xlsx_export(request):
    report_type = request.GET.get("type", "daily_movements")
    try:
        data = build_report_data(report_type, request.GET, request.user)
    except (ValueError, DjangoValidationError) as exc:
        return Response({"detail": str(exc)}, status=400)

    audit(
        request.user,
        "EXPORT_REPORT",
        description=f"Relatório {report_type} exportado em XLSX.",
        metadata=dict(request.GET),
    )
    return xlsx_response(data)
