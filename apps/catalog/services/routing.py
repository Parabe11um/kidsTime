"""Yandex responses are reduced to route legs and address candidates, never stored."""

import json
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RoutingUnavailable(Exception):
    pass


def valid_coordinate(value, maximum):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
        and -maximum <= value <= maximum
    )


def _request_json(endpoint, params):
    request = Request(
        endpoint + "?" + urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "KidsTime/1.0"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("response too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("invalid response")
        return payload
    except (HTTPError, URLError, OSError, ValueError, RecursionError):
        # Provider errors can contain the complete URL, including the private key.
        raise RoutingUnavailable("Map service unavailable") from None


def _nonnegative_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(value) and value >= 0


def route_legs(points, mode, api_key):
    """Keep the exact waypoint order; one provider request covers the whole walk."""
    payload = _request_json("https://api.routing.yandex.net/v2/route", {
        "apikey": api_key,
        "waypoints": "|".join(f'{point["lat"]:.6f},{point["lng"]:.6f}' for point in points),
        "mode": mode,
        "optimize": "false",
    })
    route = payload.get("route")
    legs = route.get("legs") if isinstance(route, dict) else None
    if not isinstance(legs, list) or len(legs) != len(points) - 1:
        raise RoutingUnavailable("Incomplete route")
    result = []
    for leg in legs:
        steps = leg.get("steps") if isinstance(leg, dict) else None
        valid = (
            isinstance(leg, dict) and leg.get("status") == "OK"
            and isinstance(steps, list) and bool(steps)
            and all(isinstance(step, dict) and _nonnegative_number(step.get("duration")) and _nonnegative_number(step.get("length")) for step in steps)
        )
        seconds = sum(step["duration"] for step in steps) if valid else None
        meters = sum(step["length"] for step in steps) if valid else None
        if valid and (not _nonnegative_number(seconds) or not _nonnegative_number(meters)):
            seconds = meters = None
        result.append({"seconds": seconds, "meters": meters})
    return result


def geocode(query, api_key, *, reverse=False):
    payload = _request_json("https://geocode-maps.yandex.ru/v1/", {
        "apikey": api_key, "geocode": query, "lang": "ru_RU", "format": "json",
        "results": 1 if reverse else 5,
    })
    try:
        members = payload["response"]["GeoObjectCollection"]["featureMember"]
        if not isinstance(members, list):
            raise TypeError
        results = []
        for member in members[:5]:
            obj = member["GeoObject"]
            lng, lat = map(float, obj["Point"]["pos"].split())
            meta = obj["metaDataProperty"]["GeocoderMetaData"]
            address = meta.get("Address", {}).get("formatted") or meta.get("text")
            if valid_coordinate(lat, 90) and valid_coordinate(lng, 180) and isinstance(address, str) and address.strip():
                results.append({"lat": lat, "lng": lng, "label": address.strip()[:500]})
        return results
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RoutingUnavailable("Invalid geocoder response") from None
