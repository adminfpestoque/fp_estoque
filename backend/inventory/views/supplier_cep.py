import re
import unicodedata
from urllib.parse import quote

import requests
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .catalog import SupplierViewSet


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_ATTRIBUTION = "Dados de ruas: © OpenStreetMap contributors"


def normalize(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold().split())


def unique(items):
    result = []
    seen = set()
    for item in items:
        cleaned = " ".join(str(item or "").strip().split())
        key = normalize(cleaned)
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        result.append(cleaned[:100])
    return result


def street_candidates(address, district):
    address = " ".join(str(address or "").strip().split())
    district = " ".join(str(district or "").strip().split())
    first_part = address.split(",", 1)[0].strip()
    without_details = re.split(
        r"\s*(?:,|\bKM\b|\bQUILOMETRO\b|\bSETOR\b|\bLOTE\b|\bN[º°O]?\b)\s*",
        address,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    highway_codes = re.findall(r"\bBR\s*[- ]?\s*(\d{2,3})\b", address, flags=re.IGNORECASE)
    highway_variants = []
    for number in highway_codes:
        highway_variants.extend(
            [
                f"BR-{number}",
                f"BR {number}",
                f"Rodovia BR-{number}",
                f"Rodovia BR {number}",
            ]
        )

    cleaned_address = re.sub(r"[/\\]", " ", first_part)
    cleaned_address = re.sub(r"\s+", " ", cleaned_address).strip()

    return unique(
        [
            address,
            first_part,
            without_details,
            cleaned_address,
            *highway_variants,
            district,
        ]
    )


def result_score(item, address, district, city, state):
    target_address = normalize(address)
    target_district = normalize(district)
    target_city = normalize(city)
    target_state = normalize(state)

    street = normalize(item.get("logradouro"))
    neighborhood = normalize(item.get("bairro"))
    result_city = normalize(item.get("localidade"))
    result_state = normalize(item.get("uf"))
    complement = normalize(item.get("complemento"))

    score = 0
    if result_city == target_city:
        score += 20
    if result_state == target_state:
        score += 15
    if target_district and neighborhood == target_district:
        score += 12
    elif target_district and (target_district in neighborhood or neighborhood in target_district):
        score += 6

    if street and street == target_address:
        score += 20
    elif street and (street in target_address or target_address in street):
        score += 12

    address_tokens = set(target_address.split())
    result_tokens = set((street + " " + complement).split())
    significant = {token for token in address_tokens if len(token) >= 3 or token.isdigit()}
    score += min(len(significant & result_tokens) * 3, 18)

    address_highways = set(re.findall(r"\b\d{2,3}\b", target_address))
    result_highways = set(re.findall(r"\b\d{2,3}\b", street + " " + complement))
    score += len(address_highways & result_highways) * 10
    return score


def query_viacep(state, city, street):
    url = (
        "https://viacep.com.br/ws/"
        f"{quote(state)}/{quote(city)}/{quote(street)}/json/"
    )
    response = requests.get(
        url,
        timeout=8,
        headers={
            "Accept": "application/json",
            "User-Agent": "FP-Estoque/1.0",
        },
    )
    if response.status_code == 400:
        return []
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def query_city_map(city_id):
    city_code = re.sub(r"\D", "", str(city_id or ""))
    if not city_code:
        return {"streets": [], "districts": []}

    cache_key = f"supplier-city-map-v2:{city_code}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    query = f"""
[out:json][timeout:25];
(
  rel[\"boundary\"=\"administrative\"][\"admin_level\"=\"8\"][\"IBGE:GEOCODIGO\"=\"{city_code}\"];
  rel[\"boundary\"=\"administrative\"][\"admin_level\"=\"8\"][\"ref:IBGE\"=\"{city_code}\"];
)->.city_relation;
.city_relation map_to_area -> .city_area;
(
  way(area.city_area)[\"highway\"][\"name\"];
  nwr(area.city_area)[\"place\"~\"^(suburb|neighbourhood|quarter)$\"][\"name\"];
);
out tags;
""".strip()

    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=30,
        headers={
            "Accept": "application/json",
            "User-Agent": "FP-Estoque/1.0 (city street suggestions)",
        },
    )
    response.raise_for_status()
    payload = response.json()

    streets = []
    districts = []
    excluded_highways = {"footway", "path", "cycleway", "steps", "bridleway"}

    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        name = " ".join(str(tags.get("name") or "").strip().split())
        if not name:
            continue

        highway = str(tags.get("highway") or "").strip()
        place = str(tags.get("place") or "").strip()
        if highway and highway not in excluded_highways:
            streets.append(name)
        if place in {"suburb", "neighbourhood", "quarter"}:
            districts.append(name)

    catalog = {
        "streets": unique(streets),
        "districts": unique(districts),
    }
    cache.set(cache_key, catalog, 7 * 24 * 60 * 60 if catalog["streets"] else 60 * 60)
    return catalog


def compact_suggestions(items):
    suggestions = []
    seen = set()
    for item in items:
        address = " ".join(str(item.get("logradouro") or "").strip().split())
        district = " ".join(str(item.get("bairro") or "").strip().split())
        cep = str(item.get("cep") or "").strip()
        if not address and not district:
            continue
        key = (normalize(address), normalize(district), cep)
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            {
                "address": address,
                "district": district,
                "cep": cep,
                "complement": str(item.get("complemento") or "").strip(),
                "source": str(item.get("source") or "viacep"),
            }
        )
        if len(suggestions) >= 30:
            break
    return suggestions


def saved_supplier_suggestions(viewset, state, city, query):
    target = normalize(query)
    try:
        rows = viewset.get_queryset().filter(
            state__iexact=state,
            city__iexact=city,
        ).values("address", "district", "cep")[:100]
    except Exception:
        return []

    results = []
    for row in rows:
        address = str(row.get("address") or "").strip()
        district = str(row.get("district") or "").strip()
        if target not in normalize(address) and target not in normalize(district):
            continue
        results.append(
            {
                "logradouro": address,
                "bairro": district,
                "cep": row.get("cep") or "",
                "source": "saved",
            }
        )
    return results


@action(detail=False, methods=["get"], url_path="address-suggestions")
def address_suggestions(self, request):
    state = str(request.query_params.get("state") or "").strip().upper()
    city = str(request.query_params.get("city") or "").strip()
    city_id = str(request.query_params.get("city_id") or "").strip()
    query = " ".join(str(request.query_params.get("q") or "").strip().split())

    if len(state) != 2 or len(city) < 3:
        return Response(
            {
                "detail": "Selecione a cidade antes de pesquisar endereço ou bairro.",
                "results": [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(query) < 3:
        return Response({"results": []})

    raw_results = []
    errors = []

    try:
        raw_results.extend(query_viacep(state, city, query))
    except (requests.RequestException, ValueError) as error:
        errors.append(str(error))

    raw_results.extend(saved_supplier_suggestions(self, state, city, query))

    uses_openstreetmap = False
    if city_id:
        try:
            catalog = query_city_map(city_id)
            target = normalize(query)
            matching_streets = [name for name in catalog["streets"] if target in normalize(name)]
            matching_districts = [name for name in catalog["districts"] if target in normalize(name)]

            if matching_streets or matching_districts:
                uses_openstreetmap = True

            raw_results.extend(
                {
                    "logradouro": name,
                    "bairro": "",
                    "cep": "",
                    "source": "openstreetmap",
                }
                for name in matching_streets
            )
            raw_results.extend(
                {
                    "logradouro": "",
                    "bairro": name,
                    "cep": "",
                    "source": "openstreetmap",
                }
                for name in matching_districts
            )
        except (requests.RequestException, ValueError) as error:
            errors.append(str(error))

    results = compact_suggestions(raw_results)
    return Response(
        {
            "results": results,
            "attribution": OSM_ATTRIBUTION if uses_openstreetmap else "",
            "detail": (
                "Nenhuma rua ou bairro foi encontrado nas bases consultadas."
                if not results
                else ""
            ),
            "service_unavailable": bool(errors) and not results,
        }
    )


@action(detail=False, methods=["get"], url_path="lookup-cep")
def lookup_cep(self, request):
    state = str(request.query_params.get("state") or "").strip().upper()
    city = str(request.query_params.get("city") or "").strip()
    address = str(request.query_params.get("address") or "").strip()
    district = str(request.query_params.get("district") or "").strip()

    if len(state) != 2 or len(city) < 3 or len(address) < 3:
        return Response(
            {
                "detail": "Informe cidade, UF e endereço para buscar o CEP.",
                "found": False,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    results_by_cep = {}
    errors = []
    for candidate in street_candidates(address, district):
        try:
            for item in query_viacep(state, city, candidate):
                cep = str(item.get("cep") or "").strip()
                if cep:
                    results_by_cep[cep] = item
        except (requests.RequestException, ValueError) as error:
            errors.append(str(error))

        if results_by_cep:
            best = max(
                results_by_cep.values(),
                key=lambda item: result_score(item, address, district, city, state),
            )
            if result_score(best, address, district, city, state) >= 40:
                break

    if not results_by_cep:
        return Response(
            {
                "found": False,
                "detail": (
                    "CEP não localizado para esse endereço. Revise o logradouro, "
                    "bairro e cidade."
                ),
                "service_unavailable": bool(errors),
            },
            status=status.HTTP_200_OK,
        )

    best = max(
        results_by_cep.values(),
        key=lambda item: result_score(item, address, district, city, state),
    )
    return Response(
        {
            "found": True,
            "cep": best.get("cep") or "",
            "address": best.get("logradouro") or address,
            "district": best.get("bairro") or district,
            "city": best.get("localidade") or city,
            "state": best.get("uf") or state,
            "complement": best.get("complemento") or "",
        }
    )


SupplierViewSet.address_suggestions = address_suggestions
SupplierViewSet.lookup_cep = lookup_cep
