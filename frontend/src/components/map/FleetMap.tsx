"use client";

import maplibregl, { Map as MLMap, Marker } from "maplibre-gl";
import { useEffect, useRef } from "react";

import { API_URL } from "@/lib/api";
import { useLive } from "@/lib/hooks";
import type { TripRow, TruckPos } from "@/lib/types";

const STYLE_URL =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const ETA_COLOR: Record<string, string> = {
  NORMAL: "#2489e9",
  WATCH: "#a16207",
  AT_RISK: "#d97706",
  CRITICAL: "#dc2626",
};

function markerEl(t: TruckPos, hasAlert: boolean): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "tp-marker";
  const color = t.trip_id ? (ETA_COLOR[t.eta_state ?? "NORMAL"] ?? "#2489e9") : "#64748b";
  el.innerHTML = `
    <div class="${hasAlert ? "pulse" : ""}" style="
      display:flex;align-items:center;gap:4px;background:#10151d;border:1.5px solid ${color};
      border-radius:6px;padding:2px 6px 2px 4px;box-shadow:0 1px 6px rgba(0,0,0,.4);
      transform:translate(-50%,-50%);cursor:pointer;">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
        style="transform:rotate(${(t.heading ?? 0) - 90}deg)">
        <path d="M3 7h11v10H3z" fill="${color}"/>
        <path d="M14 10h4l3 3v4h-7z" fill="${color}" opacity=".75"/>
      </svg>
      <span style="color:#fff;font:600 10px var(--font-jetbrains);letter-spacing:.04em">
        ${t.unit}
      </span>
    </div>`;
  return el;
}

export function FleetMap({
  trips,
  alertTrips,
  selectedTrip,
  onSelectTrip,
}: {
  trips: TripRow[];
  alertTrips: Set<string>;
  selectedTrip: string | null;
  onSelectTrip: (tripId: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<Map<string, Marker>>(new Map());
  const loadedGeoms = useRef<Set<number>>(new Set());
  const trucks = useLive((s) => s.trucks);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [-96.5, 35.5],
      zoom: 4.1,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
      loadedGeoms.current.clear();
    };
  }, []);

  // planned route lines, one source/layer pair per geometry
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const addRoutes = () => {
      for (const trip of trips) {
        if (loadedGeoms.current.has(trip.geometry_id)) continue;
        loadedGeoms.current.add(trip.geometry_id);
        fetch(`${API_URL}/api/geometry/${trip.geometry_id}`)
          .then((r) => r.json())
          .then((geom: { points: [number, number][] }) => {
            if (!mapRef.current || mapRef.current.getSource(`route-${trip.geometry_id}`)) return;
            mapRef.current.addSource(`route-${trip.geometry_id}`, {
              type: "geojson",
              data: {
                type: "Feature",
                properties: {},
                geometry: {
                  type: "LineString",
                  coordinates: geom.points.map(([lat, lon]) => [lon, lat]),
                },
              },
            });
            mapRef.current.addLayer({
              id: `route-${trip.geometry_id}`,
              type: "line",
              source: `route-${trip.geometry_id}`,
              paint: {
                "line-color": "#2489e9",
                "line-width": 1.6,
                "line-opacity": 0.4,
              },
            });
          })
          .catch(() => loadedGeoms.current.delete(trip.geometry_id));
      }
    };
    if (map.isStyleLoaded()) addRoutes();
    else map.once("load", addRoutes);
  }, [trips]);

  // highlight selected trip's line
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    for (const trip of trips) {
      const layer = `route-${trip.geometry_id}`;
      if (!map.getLayer(layer)) continue;
      const isSel = trip.trip_id === selectedTrip;
      map.setPaintProperty(layer, "line-width", isSel ? 3.2 : 1.6);
      map.setPaintProperty(layer, "line-opacity", isSel ? 0.9 : 0.35);
      map.setPaintProperty(
        layer,
        "line-color",
        isSel ? (ETA_COLOR[trip.eta_state] ?? "#2489e9") : "#2489e9",
      );
    }
  }, [selectedTrip, trips]);

  // truck markers follow live positions
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const t of trucks) {
      seen.add(t.truck_id);
      const existing = markersRef.current.get(t.truck_id);
      const hasAlert = t.trip_id !== null && alertTrips.has(t.trip_id);
      if (existing) {
        existing.setLngLat([t.lon, t.lat]);
        const el = existing.getElement();
        const fresh = markerEl(t, hasAlert);
        el.replaceChildren(...fresh.children);
      } else {
        const el = markerEl(t, hasAlert);
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          onSelectTrip(t.trip_id);
        });
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([t.lon, t.lat])
          .addTo(map);
        markersRef.current.set(t.truck_id, marker);
      }
    }
    for (const [id, marker] of markersRef.current) {
      if (!seen.has(id)) {
        marker.remove();
        markersRef.current.delete(id);
      }
    }
  }, [trucks, alertTrips, onSelectTrip]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg border border-tp-line">
      <div ref={containerRef} className="h-full w-full" />
      <div className="absolute bottom-2 left-2 flex gap-2 rounded bg-tp-navy/85 px-2 py-1 text-[10px] text-white/80">
        {Object.entries({ "on plan": "#2489e9", watch: "#a16207", "at risk": "#d97706", critical: "#dc2626", idle: "#64748b" }).map(
          ([label, color]) => (
            <span key={label} className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
              {label}
            </span>
          ),
        )}
      </div>
    </div>
  );
}
