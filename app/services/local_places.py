from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

logger = logging.getLogger(__name__)

_LOCAL_ENTITY_HINTS: tuple[str, ...] = (
    "bbq",
    "barbecue",
    "barbeque",
    "restaurant",
    "restaurants",
    "bar ",
    " bars",
    "cafe",
    "coffee shop",
    "hotel",
    "hotels",
    "pizza",
    "sushi",
    "taco",
    "brewery",
    "winery",
    "museum",
    "attraction",
    "things to do",
)

_NEAR_ME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnear me\b", re.IGNORECASE),
    re.compile(r"\bnearby\b", re.IGNORECASE),
    re.compile(r"\baround me\b", re.IGNORECASE),
    re.compile(r"\bclose to me\b", re.IGNORECASE),
    re.compile(r"\bclosest\b", re.IGNORECASE),
    re.compile(r"\bin my area\b", re.IGNORECASE),
    re.compile(r"\bwhere i am\b", re.IGNORECASE),
    re.compile(r"\bcurrent location\b", re.IGNORECASE),
    re.compile(r"\bmy location\b", re.IGNORECASE),
)

_LOCATION_PROMPT_MARKERS: tuple[str, ...] = (
    "what city or neighborhood",
    "what city or area",
    "city or neighborhood should i search",
    "share your city",
    "which city",
    "which neighborhood",
    "which area",
    "which stadium",
    "which landmark",
)

_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("coffee", ("coffee", "cafe", "espresso")),
    ("bar", ("bar", "bars", "pub", "brewery", "winery", "nightlife")),
    ("things_to_do", ("things to do", "attraction", "attractions", "museum", "museums", "activities", "activity")),
    ("hotel", ("hotel", "hotels", "lodging", "stay")),
    ("food", ("food", "restaurant", "restaurants", "eat", "dining", "lunch", "dinner", "breakfast", "bbq", "barbecue", "pizza", "sushi", "taco")),
)

_OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "food": [("amenity", "restaurant"), ("amenity", "fast_food")],
    "coffee": [("amenity", "cafe"), ("shop", "coffee")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "things_to_do": [("tourism", "attraction"), ("tourism", "museum"), ("leisure", "park")],
    "hotel": [("tourism", "hotel")],
    "general": [("amenity", "restaurant"), ("amenity", "cafe"), ("tourism", "attraction")],
}

_OVERPASS_ENDPOINTS: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
)

_HTTP_HEADERS = {
    "User-Agent": "CurAI/1.0 (https://github.com/sreeram843/personal-ai)",
}

_NOMINATIM_CATEGORY_QUERIES = {
    "food": "restaurant",
    "coffee": "cafe coffee",
    "bar": "bar pub",
    "things_to_do": "attraction museum",
    "hotel": "hotel",
    "general": "restaurant cafe",
}

_CATEGORY_LABELS = {
    "food": "places to eat",
    "coffee": "coffee shops",
    "bar": "bars and pubs",
    "things_to_do": "things to do",
    "hotel": "hotels",
    "general": "nearby places",
}


def uses_relative_location(query: str) -> bool:
    return any(pattern.search(query) for pattern in _NEAR_ME_PATTERNS)


def _has_explicit_place(query: str) -> bool:
    return bool(
        re.search(
            r"\b(?:in|near|around|close to)\s+[A-Za-z][\w\s'.,-]{1,60}",
            query,
        )
    )


def is_nearby_places_query(query: str) -> bool:
    """True when the user is asking for local recommendations near a place or themselves."""
    text = query.strip()
    if not text:
        return False
    lowered = text.lower()
    if any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in ("weather", "temperature", "forecast", "humidity")):
        return False
    has_entity = any(hint in lowered for hint in _LOCAL_ENTITY_HINTS)
    has_entity = has_entity or any(term in lowered for _, terms in _CATEGORY_RULES for term in terms)
    if not has_entity:
        return False
    return uses_relative_location(text) or _has_explicit_place(text)


def extract_nearby_category(query: str) -> str:
    lowered = query.lower()
    for category, terms in _CATEGORY_RULES:
        if any(term in lowered for term in terms):
            return category
    return "general"


def extract_nearby_location(query: str) -> Optional[str]:
    """Extract a named place from queries like 'restaurants in Austin'."""
    if uses_relative_location(query):
        return None

    for pattern in (
        r"\b(?:in|near|around|close to)\s+([A-Za-z][\w\s'.,-]{1,80}?)(?:\?|$)",
        r"\b(?:in|near|around|close to)\s+([A-Za-z][\w\s'.,-]{1,80})",
    ):
        match = re.search(pattern, query.strip(), flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" .?,-")
            if candidate and len(candidate.split()) <= 8:
                return candidate
    return None


def location_prompt_text(*, category: str) -> str:
    label = _CATEGORY_LABELS.get(category, "nearby places")
    return (
        f"I can find **{label}** once I know your area.\n\n"
        "What **city or neighborhood** should I search around? "
        "(For example: Austin, TX or downtown Seattle.)"
    )


def assistant_asked_for_location(assistant_message: str) -> bool:
    lowered = re.sub(r"\*+", "", assistant_message).lower()
    return any(marker in lowered for marker in _LOCATION_PROMPT_MARKERS)


def looks_like_location_reply(query: str) -> bool:
    text = query.strip()
    if not text or len(text.split()) > 8:
        return False
    if uses_relative_location(text):
        return False
    if re.search(r"\b(what|why|how|when|who|stock|weather|price)\b", text, flags=re.IGNORECASE):
        return False
    return bool(re.match(r"^[A-Za-z][\w\s'.,-]{1,80}$", text))


def detect_nearby_places_follow_up(
    query: str,
    chat_history: Sequence[dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """If the assistant asked for a location, treat a short place reply as nearby intent."""
    if not looks_like_location_reply(query):
        return None

    category = "general"
    for message in reversed(chat_history):
        role = str(message.get("role") or "").lower()
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if role == "user" and is_nearby_places_query(content):
            category = extract_nearby_category(content)
            break

    for message in reversed(chat_history):
        role = str(message.get("role") or "").lower()
        content = str(message.get("content") or "").strip()
        if role == "assistant" and assistant_asked_for_location(content):
            return {
                "location": query.strip(),
                "category": category,
            }
        if role == "user":
            break
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _place_type(tags: dict[str, Any]) -> str:
    for key in ("amenity", "tourism", "leisure", "shop"):
        value = tags.get(key)
        if value:
            return str(value).replace("_", " ")
    return "place"


async def _geocode(location: str, *, timeout: float = 10.0) -> Optional[dict[str, Any]]:
    place = location.strip()
    if not place:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=_HTTP_HEADERS) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": place, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            return results[0] if results else None
    except Exception:
        logger.exception("Geocoding failed for %s", place)
        return None


def _build_overpass_query(lat: float, lon: float, category: str, *, radius_m: int, limit: int) -> str:
    tags = _OSM_TAGS.get(category, _OSM_TAGS["general"])
    filters: list[str] = []
    for key, value in tags:
        filters.append(f'node["{key}"="{value}"](around:{radius_m},{lat},{lon});')
        filters.append(f'way["{key}"="{value}"](around:{radius_m},{lat},{lon});')
    body = "\n  ".join(filters)
    return f"[out:json][timeout:25];(\n  {body}\n);out center {limit};"


async def _fetch_overpass_elements(
    query: str,
    *,
    timeout: float,
) -> Optional[list[dict[str, Any]]]:
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, headers=_HTTP_HEADERS) as client:
        for url in _OVERPASS_ENDPOINTS:
            try:
                resp = await client.post(url, data={"data": query})
                if resp.status_code == 406:
                    # Some Overpass frontends reject Accept: application/json; retry bare.
                    resp = await client.post(
                        url,
                        data={"data": query},
                        headers={**_HTTP_HEADERS, "Accept": "*/*"},
                    )
                resp.raise_for_status()
                return list(resp.json().get("elements") or [])
            except Exception as exc:
                last_error = exc
                logger.warning("Overpass endpoint failed (%s): %s", url, exc)
                continue
    if last_error is not None:
        logger.exception("All Overpass endpoints failed: %s", last_error)
    return None


async def _fetch_nominatim_places(
    location: str,
    *,
    category: str,
    limit: int,
    timeout: float,
) -> Optional[dict[str, Any]]:
    """Fallback POI search when Overpass is unavailable."""
    keyword = _NOMINATIM_CATEGORY_QUERIES.get(category, category.replace("_", " "))
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=_HTTP_HEADERS) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": f"{keyword} {location}",
                    "format": "json",
                    "limit": limit,
                    "addressdetails": 0,
                },
            )
            resp.raise_for_status()
            rows = resp.json() or []
    except Exception:
        logger.exception("Nominatim nearby fallback failed for %s", location)
        return None

    places: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        display = str(row.get("display_name") or "").strip()
        if not name:
            name = display.split(",")[0].strip() if display else ""
        if not name:
            continue
        places.append(
            {
                "name": name,
                "type": str(row.get("type") or category).replace("_", " "),
                "distanceKm": None,
            }
        )
    if not places:
        return None
    return {
        "location": location,
        "category": category,
        "categoryLabel": _CATEGORY_LABELS.get(category, _CATEGORY_LABELS["general"]),
        "radiusKm": None,
        "places": places[:limit],
        "source": "OpenStreetMap",
    }


async def fetch_nearby_places(
    location: str,
    *,
    category: str = "general",
    radius_m: int = 5000,
    limit: int = 12,
    timeout: float = 20.0,
) -> Optional[dict[str, Any]]:
    geo = await _geocode(location, timeout=timeout)
    if not geo:
        return await _fetch_nominatim_places(location, category=category, limit=limit, timeout=timeout)

    lat = geo.get("latitude")
    lon = geo.get("longitude")
    if lat is None or lon is None:
        return await _fetch_nominatim_places(location, category=category, limit=limit, timeout=timeout)

    label_parts = [geo.get("name", location)]
    if geo.get("admin1"):
        label_parts.append(str(geo["admin1"]))
    if geo.get("country"):
        label_parts.append(str(geo["country"]))
    location_label = ", ".join(part for part in label_parts if part)

    query = _build_overpass_query(float(lat), float(lon), category, radius_m=radius_m, limit=limit)
    elements = await _fetch_overpass_elements(query, timeout=timeout)

    places: list[dict[str, Any]] = []
    for element in elements or []:
        tags = element.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        if not name:
            continue
        if "center" in element:
            place_lat = element["center"].get("lat")
            place_lon = element["center"].get("lon")
        else:
            place_lat = element.get("lat")
            place_lon = element.get("lon")
        distance_km = None
        if place_lat is not None and place_lon is not None:
            distance_km = round(_haversine_km(float(lat), float(lon), float(place_lat), float(place_lon)), 1)
        places.append(
            {
                "name": name,
                "type": _place_type(tags),
                "distanceKm": distance_km,
            }
        )

    places.sort(key=lambda item: item.get("distanceKm") if item.get("distanceKm") is not None else 999)
    places = places[:limit]

    if places:
        return {
            "location": location_label,
            "category": category,
            "categoryLabel": _CATEGORY_LABELS.get(category, _CATEGORY_LABELS["general"]),
            "radiusKm": round(radius_m / 1000, 1),
            "places": places,
            "source": "OpenStreetMap",
        }

    # Overpass empty/down — Nominatim search still often finds cafes in major cities.
    fallback = await _fetch_nominatim_places(
        location_label or location,
        category=category,
        limit=limit,
        timeout=timeout,
    )
    return fallback


__all__ = [
    "assistant_asked_for_location",
    "detect_nearby_places_follow_up",
    "extract_nearby_category",
    "extract_nearby_location",
    "fetch_nearby_places",
    "is_nearby_places_query",
    "location_prompt_text",
    "looks_like_location_reply",
    "uses_relative_location",
]
