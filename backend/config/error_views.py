from django.http import JsonResponse
from django.views.defaults import page_not_found, server_error


def health(request):
    """Endpoint público e leve para confirmar que o backend correto está no ar."""
    return JsonResponse(
        {
            "status": "ok",
            "service": "fp-estoque-api",
            "api_version": "2.1.0",
            "packaging_types_endpoint": "/api/packaging-types/",
        }
    )


def handler404(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "detail": "Endpoint da API não encontrado.",
                "status_code": 404,
                "path": request.path,
            },
            status=404,
        )
    return page_not_found(request, exception)


def handler500(request):
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "detail": "O servidor encontrou um erro inesperado. Tente novamente em alguns instantes.",
                "status_code": 500,
            },
            status=500,
        )
    return server_error(request)
