"""Geodesic math for route replay and deviation detection.

Positions travel along a polyline addressed by cumulative distance, so the
mover is O(log n) per tick (bisect over the prefix-sum table) and the deviation
detector is an exact point-to-segment projection in a local equirectangular
frame (accurate to well under 0.5% at truck-route segment lengths).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass

EARTH_RADIUS_MI = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def great_circle_points(
    lat1: float, lon1: float, lat2: float, lon2: float, n: int = 64
) -> list[tuple[float, float]]:
    """Intermediate points via spherical linear interpolation."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = 2 * math.asin(
        math.sqrt(
            math.sin((p2 - p1) / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
        )
    )
    if d < 1e-9:
        return [(lat1, lon1), (lat2, lon2)]
    pts = []
    for i in range(n + 1):
        f = i / n
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
        y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
        z = a * math.sin(p1) + b * math.sin(p2)
        pts.append(
            (
                math.degrees(math.atan2(z, math.hypot(x, y))),
                math.degrees(math.atan2(y, x)),
            )
        )
    return pts


@dataclass
class Polyline:
    """Polyline with prefix-sum mileage for O(log n) point-at-distance."""

    points: list[tuple[float, float]]
    cum_miles: list[float]

    @classmethod
    def from_points(cls, points: list[tuple[float, float]]) -> "Polyline":
        cum = [0.0]
        for (a, b), (c, d) in zip(points, points[1:]):
            cum.append(cum[-1] + haversine_miles(a, b, c, d))
        return cls(points=points, cum_miles=cum)

    @property
    def total_miles(self) -> float:
        return self.cum_miles[-1]

    def point_at(self, miles: float) -> tuple[float, float, float]:
        """(lat, lon, heading_deg) at the given distance along the line."""
        m = max(0.0, min(miles, self.total_miles))
        i = bisect_right(self.cum_miles, m) - 1
        if i >= len(self.points) - 1:
            i = len(self.points) - 2
        seg = self.cum_miles[i + 1] - self.cum_miles[i]
        f = 0.0 if seg <= 1e-12 else (m - self.cum_miles[i]) / seg
        (lat1, lon1), (lat2, lon2) = self.points[i], self.points[i + 1]
        lat = lat1 + (lat2 - lat1) * f
        lon = lon1 + (lon2 - lon1) * f
        return lat, lon, initial_bearing_deg(lat1, lon1, lat2, lon2)

    def distance_from(self, lat: float, lon: float) -> float:
        """Minimum miles from a point to the polyline (segment projection)."""
        best = float("inf")
        coslat = math.cos(math.radians(lat))
        px, py = lon * coslat, lat
        for (alat, alon), (blat, blon) in zip(self.points, self.points[1:]):
            ax, ay = alon * coslat, alat
            bx, by = blon * coslat, blat
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 <= 1e-18 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
            qx, qy = ax + t * dx, ay + t * dy
            d = math.hypot(px - qx, py - qy) * 69.0460  # degrees → miles
            if d < best:
                best = d
        return best
