"""Deterministic billing-packet PDFs for recently delivered loads.

The documents are the simulated *environment* (rate confirmations, BOLs, PODs,
fuel receipts a driver would hand in). Five packets carry injected
discrepancies; each packet's `truth` JSON records the system-of-record values
so the deterministic reconciler can grade the LLM's extraction — the LLM never
sees `truth`.
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fpdf import FPDF
from sqlmodel import Session

from ..config import (
    DETENTION_FREE_MIN,
    DETENTION_RATE_PER_HR,
    DOCS_DIR,
    FLEET_TERMINALS,
    PACKET_COUNT,
    SEED,
)
from ..db import engine
from ..models import DocPacket, LiveLoad, LoadStatus
from .world import WorldBuilder

FUEL_STOPS = ["Pilot Travel Center", "Love's Travel Stop", "TA Express", "Flying J"]

DISCREPANCIES = {
    1: "rate_mismatch",
    3: "detention_unclaimed",
    5: "missing_fuel_receipt",
    7: "missing_accessorial",
    9: "weight_mismatch",
}


class Doc(FPDF):
    """Shared letterhead-free page chrome for generated freight paperwork."""

    def hline(self, y: float | None = None) -> None:
        if y is None:
            y = self.get_y()
        self.set_draw_color(160, 160, 160)
        self.line(12, y, 198, y)

    def kv(self, label: str, value: str, w_label: float = 42) -> None:
        self.set_font("helvetica", "", 8)
        self.set_text_color(110, 110, 110)
        self.cell(w_label, 5, label.upper())
        self.set_font("courier", "B", 9)
        self.set_text_color(20, 20, 20)
        self.cell(0, 5, value, new_x="LMARGIN", new_y="NEXT")

    def signature(self, rng: random.Random, x: float, y: float, w: float = 40) -> None:
        self.set_draw_color(30, 30, 90)
        self.set_line_width(0.4)
        px, py = x, y
        for _ in range(14):
            nx = px + rng.uniform(1.5, w / 10)
            ny = y + rng.uniform(-3.5, 3.5)
            self.line(px, py, nx, ny)
            px, py = nx, ny
        self.set_line_width(0.2)


def _header(pdf: Doc, title: str, ref: str, issuer: str, issuer_sub: str) -> None:
    pdf.set_font("helvetica", "B", 15)
    pdf.set_text_color(15, 23, 34)
    pdf.cell(120, 8, issuer)
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(46, 108, 190)
    pdf.cell(0, 8, title, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(120, 5, issuer_sub)
    pdf.set_font("courier", "B", 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 5, ref, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.hline()
    pdf.ln(3)


def make_ratecon(path: Path, d: dict) -> None:
    pdf = Doc()
    pdf.add_page()
    _header(pdf, "RATE CONFIRMATION", f"RC# {d['ratecon_no']}",
            d["customer_name"], "Freight Payables Desk")
    pdf.kv("Load number", d["load_id"])
    pdf.kv("Carrier", "Sunbelt Carriers LLC  MC-884217  DOT-2318876")
    pdf.kv("Equipment", f"{d['load_type']} 53'")
    pdf.kv("Pickup", f"{d['pickup_name']} - {d['origin']}  {d['pickup_date']}")
    pdf.kv("Delivery", f"{d['dest_name']} - {d['dest']}  {d['delivery_date']}")
    pdf.kv("Weight / pieces", f"{d['ratecon_weight']:,} lbs / {d['pieces']} plts")
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(15, 23, 34)
    pdf.cell(0, 6, "AGREED CHARGES", new_x="LMARGIN", new_y="NEXT")
    rows = [("Linehaul", d["ratecon_linehaul"]), ("Fuel surcharge", d["fuel_surcharge"])]
    if d["ratecon_accessorial"] > 0:
        rows.append(("Accessorial - lumper/unload", d["ratecon_accessorial"]))
    if d.get("ratecon_detention", 0) > 0:
        rows.append(("Detention", d["ratecon_detention"]))
    total = sum(v for _, v in rows)
    for label, val in rows:
        pdf.set_font("helvetica", "", 9)
        pdf.cell(120, 6, label)
        pdf.set_font("courier", "", 9)
        pdf.cell(0, 6, f"$ {val:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.hline()
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(120, 7, "TOTAL")
    pdf.set_font("courier", "B", 10)
    pdf.cell(0, 7, f"$ {total:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 4, "Detention billable after 2 hours free time at $75.00/hr with in/out "
                         "times noted on signed POD. Rates inclusive unless amended in writing. "
                         "Invoice with signed BOL/POD and all receipts within 48 hours of delivery.")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def make_bol(path: Path, d: dict, rng: random.Random) -> None:
    pdf = Doc()
    pdf.add_page()
    _header(pdf, "BILL OF LADING", f"BOL# {d['bol_no']}", d["pickup_name"], d["origin"])
    pdf.kv("Ship date", d["pickup_date"])
    pdf.kv("Shipper", f"{d['pickup_name']}, {d['origin']}")
    pdf.kv("Consignee", f"{d['dest_name']}, {d['dest']}")
    pdf.kv("Carrier", "Sunbelt Carriers LLC")
    pdf.kv("PRO number", d["pro_no"])
    pdf.kv("Ref / PO", d["load_id"])
    pdf.ln(3)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(0, 6, "COMMODITIES", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(25, 5, "PIECES")
    pdf.cell(95, 5, "DESCRIPTION")
    pdf.cell(35, 5, "WEIGHT (LBS)")
    pdf.cell(0, 5, "HM", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("courier", "", 9)
    pdf.cell(25, 6, str(d["pieces"]))
    pdf.cell(95, 6, f"{d['load_type']} freight, palletized")
    pdf.cell(35, 6, f"{d['bol_weight']:,}")
    pdf.cell(0, 6, "N", new_x="LMARGIN", new_y="NEXT")
    pdf.hline()
    pdf.ln(6)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 4, "Received, subject to individually determined rates or contracts agreed "
                         "upon in writing between the carrier and shipper, the property described "
                         "above in apparent good order, except as noted.")
    pdf.ln(6)
    y = pdf.get_y()
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(90, 5, "SHIPPER SIGNATURE")
    pdf.cell(0, 5, "DRIVER SIGNATURE", new_x="LMARGIN", new_y="NEXT")
    pdf.signature(rng, 16, y + 12)
    pdf.signature(rng, 110, y + 12)
    pdf.line(14, y + 16, 92, y + 16)
    pdf.line(108, y + 16, 186, y + 16)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def make_pod(path: Path, d: dict, rng: random.Random) -> None:
    pdf = Doc()
    pdf.add_page()
    _header(pdf, "PROOF OF DELIVERY", f"POD ref {d['pro_no']}", d["dest_name"], d["dest"])
    pdf.kv("Load number", d["load_id"])
    pdf.kv("Carrier", "Sunbelt Carriers LLC")
    pdf.kv("Delivery date", d["delivery_date"])
    pdf.kv("Arrival (check-in)", d["pod_in"])
    pdf.kv("Departure (check-out)", d["pod_out"])
    pdf.kv("Pieces received", f"{d['pieces']} pallets")
    pdf.kv("Condition", "Received in good order - no exceptions noted")
    pdf.ln(8)
    y = pdf.get_y()
    pdf.set_font("helvetica", "", 8)
    pdf.cell(90, 5, "RECEIVED BY (CONSIGNEE)")
    pdf.cell(0, 5, "DATE / TIME", new_x="LMARGIN", new_y="NEXT")
    pdf.signature(rng, 16, y + 12)
    pdf.line(14, y + 16, 92, y + 16)
    pdf.set_font("courier", "B", 9)
    pdf.text(110, y + 15, f"{d['delivery_date']} {d['pod_out']}")
    pdf.ln(18)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(110, 110, 110)
    pdf.multi_cell(0, 4, "Detention: free time 2 hours from documented arrival. Check-in and "
                         "check-out times above are the controlling record for dwell.")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def make_fuel_receipt(path: Path, d: dict, idx: int, rng: random.Random) -> dict:
    stop = rng.choice(FUEL_STOPS)
    gallons = round(rng.uniform(78, 142), 1)
    price = round(rng.uniform(3.35, 3.92), 3)
    total = round(gallons * price, 2)
    city, state = rng.choice(d["fuel_cities"])
    pdf = Doc(format=(90, 140))
    pdf.set_margins(8, 8)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 6, stop, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 4, f"{city}, {state}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, f"{d['fuel_date']}  PUMP {rng.randint(3, 14)}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(20, 20, 20)
    pdf.set_font("courier", "", 9)
    for label, val in [
        ("DIESEL GAL", f"{gallons:.1f}"),
        ("PRICE/GAL", f"${price:.3f}"),
        ("FUEL TOTAL", f"${total:,.2f}"),
        ("CARD", f"FC**{rng.randint(1000, 9999)}"),
        ("UNIT", d["unit_number"]),
        ("REF LOAD", d["load_id"]),
    ]:
        pdf.cell(38, 5, label)
        pdf.cell(0, 5, val, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("helvetica", "", 7)
    pdf.cell(0, 4, "THANK YOU - DRIVE SAFE", align="C")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return {"station": stop, "gallons": gallons, "price_per_gallon": price, "total": total}


def build_packets(conn: sqlite3.Connection, t0: datetime) -> dict:
    rng = random.Random(SEED + 7)
    with Session(engine) as session:
        wb = WorldBuilder(conn, session, t0)
        wb._load_seq = 100  # packet loads get their own L-YYMM-1xx series
        routes = wb._fleet_routes()
        outbound = [r for r in routes if r[1] in FLEET_TERMINALS]

        made = 0
        for i in range(PACKET_COUNT):
            route = outbound[i % len(outbound)]
            delivered_at = t0 - timedelta(days=1 + (i % 5), hours=rng.uniform(2, 9))
            pickup_at = delivered_at - timedelta(hours=route[5] / 52.0 + 2)
            load = wb.make_load(route, pickup_at, LoadStatus.DELIVERED)
            load.status = LoadStatus.DELIVERED
            session.add(load)
            session.flush()

            kind = DISCREPANCIES.get(i)
            unit = f"{rng.randint(3100, 6900)}"
            pickup_fac = wb.facility.get((load.origin_city, load.origin_state))
            dest_fac = wb.facility.get((load.dest_city, load.dest_state))
            pickup_name = f"{load.origin_city} Shipper Dock"
            dest_name = f"{load.dest_city} Receiving"
            if pickup_fac:
                row = conn.execute("SELECT facility_name FROM facilities WHERE facility_id=?",
                                   (pickup_fac[0],)).fetchone()
                pickup_name = row[0] if row else pickup_name
            if dest_fac:
                row = conn.execute("SELECT facility_name FROM facilities WHERE facility_id=?",
                                   (dest_fac[0],)).fetchone()
                dest_name = row[0] if row else dest_name

            dwell_min = rng.randint(35, 100)
            detention_due = 0.0
            if kind == "detention_unclaimed":
                dwell_min = 234
                billable = dwell_min - DETENTION_FREE_MIN
                detention_due = round(billable / 60.0 * DETENTION_RATE_PER_HR, 2)
            pod_in = delivered_at.replace(minute=rng.randint(0, 45))
            pod_out = pod_in + timedelta(minutes=dwell_min)

            bol_weight = load.weight_lbs
            if kind == "weight_mismatch":
                bol_weight = load.weight_lbs + 2400
            ratecon_linehaul = load.revenue
            if kind == "rate_mismatch":
                ratecon_linehaul = round(load.revenue - 200.0, 2)
            ratecon_accessorial = load.accessorial_charges
            if kind == "missing_accessorial":
                ratecon_accessorial = 0.0

            n_fuel_system = 2
            n_fuel_docs = 1 if kind == "missing_fuel_receipt" else 2

            d = {
                "load_id": load.load_id,
                "customer_name": load.customer_name,
                "load_type": load.load_type,
                "pieces": load.pieces,
                "origin": f"{load.origin_city}, {load.origin_state}",
                "dest": f"{load.dest_city}, {load.dest_state}",
                "pickup_name": pickup_name,
                "dest_name": dest_name,
                "pickup_date": f"{pickup_at:%m/%d/%Y}",
                "delivery_date": f"{delivered_at:%m/%d/%Y}",
                "fuel_date": f"{(pickup_at + timedelta(hours=4)):%m/%d/%Y %H:%M}",
                "ratecon_no": f"RC{rng.randint(100000, 999999)}",
                "bol_no": f"BOL{rng.randint(1000000, 9999999)}",
                "pro_no": f"PRO{rng.randint(100000, 999999)}",
                "unit_number": unit,
                "ratecon_weight": load.weight_lbs,
                "bol_weight": bol_weight,
                "ratecon_linehaul": ratecon_linehaul,
                "fuel_surcharge": load.fuel_surcharge,
                "ratecon_accessorial": ratecon_accessorial,
                "pod_in": f"{pod_in:%H:%M}",
                "pod_out": f"{pod_out:%H:%M}",
                "fuel_cities": [(load.origin_city, load.origin_state),
                                (load.dest_city, load.dest_state)],
            }

            pdir = DOCS_DIR / load.load_id
            docs = []
            make_ratecon(pdir / "ratecon.pdf", d)
            docs.append({"doc_type": "RATE_CONFIRMATION", "filename": "ratecon.pdf",
                         "title": f"Rate Confirmation {d['ratecon_no']}"})
            make_bol(pdir / "bol.pdf", d, rng)
            docs.append({"doc_type": "BOL", "filename": "bol.pdf",
                         "title": f"Bill of Lading {d['bol_no']}"})
            make_pod(pdir / "pod.pdf", d, rng)
            docs.append({"doc_type": "POD", "filename": "pod.pdf",
                         "title": f"Proof of Delivery {d['pro_no']}"})
            fuel_totals = []
            for f_i in range(n_fuel_docs):
                info = make_fuel_receipt(pdir / f"fuel{f_i + 1}.pdf", d, f_i, rng)
                fuel_totals.append(info)
                docs.append({"doc_type": "FUEL_RECEIPT", "filename": f"fuel{f_i + 1}.pdf",
                             "title": f"Fuel receipt - {info['station']}"})

            truth = {
                "discrepancy": kind,
                "system_revenue": load.revenue,
                "system_fuel_surcharge": load.fuel_surcharge,
                "system_accessorials": load.accessorial_charges,
                "system_weight_lbs": load.weight_lbs,
                "gps_dwell_minutes": dwell_min,
                "detention_free_min": DETENTION_FREE_MIN,
                "detention_rate_per_hr": DETENTION_RATE_PER_HR,
                "detention_due": detention_due,
                "fuel_purchases_in_system": n_fuel_system,
                "fuel_receipts_submitted": n_fuel_docs,
                "expected_invoice_total": round(
                    load.revenue + load.fuel_surcharge + load.accessorial_charges + detention_due, 2),
            }
            session.add(DocPacket(
                load_id=load.load_id,
                delivered_at=delivered_at,
                docs=json.dumps(docs),
                truth=json.dumps(truth),
            ))
            made += 1
        session.commit()
    return {"packets": made, "with_discrepancies": len(DISCREPANCIES)}
