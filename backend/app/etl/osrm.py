"""Road geometry for live lanes, fetched once at seed time and cached.

Uses the public OSRM demo server; any failure falls back to a great-circle
arc so seeding never blocks on the network.
"""
from __future__ import annotations

import httpx
import polyline as polyline_codec

from ..geo import great_circle_points, Polyline

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"


def fetch_road_polyline(
    lat1: float, lon1: float, lat2: float, lon2: float, via: tuple[float, float] | None = None
) -> tuple[list[tuple[float, float]], float, float, str]:
    """Returns (points, distance_miles, duration_hours, source)."""
    coords = f"{lon1},{lat1};"
    if via:
        coords += f"{via[1]},{via[0]};"
    coords += f"{lon2},{lat2}"
    url = f"https://router.project-osrm.org/route/v1/driving/{coords}"
    try:
        resp = httpx.get(url, params={"overview": "full", "geometries": "polyline"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]
        pts = polyline_codec.decode(route["geometry"])
        # thin out ultra-dense geometry; detectors only need ~0.3 mi resolution
        if len(pts) > 800:
            step = len(pts) // 800 + 1
            pts = pts[::step] + [pts[-1]]
        return pts, route["distance"] / 1609.344, route["duration"] / 3600.0, "osrm"
    except Exception:
        pts = great_circle_points(lat1, lon1, lat2, lon2, n=96)
        line = Polyline.from_points(pts)
        road_miles = line.total_miles * 1.18  # typical road/great-circle ratio
        return pts, road_miles, road_miles / 55.0, "greatcircle"
