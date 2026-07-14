"""Executes human-approved agent actions. Nothing here runs without a click."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from fpdf import FPDF
from sqlmodel import Session, select

from ..config import INVOICE_DIR
from ..db import engine
from ..etl.osrm import fetch_road_polyline
from ..geo import haversine_miles
from ..hos.schedule import legal_elapsed_minutes
from ..models import (
    ActionStatus,
    DocPacket,
    DriverDuty,
    ExceptionState,
    FleetDriver,
    FleetException,
    FleetTruck,
    Invoice,
    LiveLoad,
    LiveTrip,
    LoadStatus,
    MessageLog,
    PacketStatus,
    PendingAction,
    RouteGeometry,
    SimState,
    TripStatus,
)
from ..sim.mover import set_duty
from ..streams import broadcaster

ROAD_FACTOR = 1.18
DEADHEAD_MPH = 45.0
PLANNING_MPH = 52.0


def _sim_now(s: Session) -> datetime:
    return s.get(SimState, 1).sim_now


def approve_action(action_id: int, draft_override: dict | None = None) -> dict:
    with Session(engine) as s:
        action = s.get(PendingAction, action_id)
        if action is None:
            return {"error": "action not found"}
        if action.status != ActionStatus.PENDING:
            return {"error": f"action already {action.status}"}
        draft = json.loads(action.draft)
        if draft_override:
            draft.update({k: v for k, v in draft_override.items() if v is not None})
            action.draft = json.dumps(draft)

        now = _sim_now(s)
        note = _execute(s, action, draft, now)

        action.status = ActionStatus.APPROVED
        action.decided_at = datetime.now()
        action.executed_note = note
        s.add(action)
        s.commit()
    broadcaster.publish("action", {"id": action_id, "status": "APPROVED", "note": note})
    return {"ok": True, "note": note}


def dismiss_action(action_id: int) -> dict:
    with Session(engine) as s:
        action = s.get(PendingAction, action_id)
        if action is None or action.status != ActionStatus.PENDING:
            return {"error": "not pending"}
        action.status = ActionStatus.DISMISSED
        action.decided_at = datetime.now()
        s.add(action)
        s.commit()
    broadcaster.publish("action", {"id": action_id, "status": "DISMISSED"})
    return {"ok": True}


def _execute(s: Session, action: PendingAction, draft: dict, now: datetime) -> str:
    if action.kind == "ASSIGN_DRIVER":
        return _assign_driver(s, action, draft, now)
    if action.kind in ("SMS_DRIVER", "EMAIL_CUSTOMER", "MONITOR"):
        return _comms(s, action, draft, now)
    if action.kind == "SEND_INVOICE":
        return _send_invoice(s, action, draft, now)
    return "no-op"


# ---- dispatch execution -------------------------------------------------------

def _geometry_for(s: Session, o: tuple[str, str], d: tuple[str, str],
                  coords: dict) -> RouteGeometry:
    key = f"{o[0]},{o[1]}->{d[0]},{d[1]}"
    geom = s.exec(select(RouteGeometry).where(RouteGeometry.lane_key == key)).first()
    if geom:
        return geom
    (olat, olon), (dlat, dlon) = coords[o], coords[d]
    pts, miles, hours, source = fetch_road_polyline(olat, olon, dlat, dlon)
    geom = RouteGeometry(lane_key=key, encoded_polyline=json.dumps(pts),
                         distance_miles=round(miles, 1), duration_hours=round(hours, 2),
                         source=source)
    s.add(geom)
    s.flush()
    return geom


def _assign_driver(s: Session, action: PendingAction, draft: dict, now: datetime) -> str:
    from ..db import raw_connection

    load = s.get(LiveLoad, action.subject_id)
    driver = s.get(FleetDriver, draft["driver_id"])
    if load is None or driver is None:
        return "load or driver missing"
    if load.status != LoadStatus.UNASSIGNED:
        return f"load already {load.status}"
    if driver.trip_id:
        return f"{driver.name} took another trip in the meantime"

    truck = s.exec(select(FleetTruck).where(
        FleetTruck.driver_id == None, FleetTruck.status == "Active",  # noqa: E711
        FleetTruck.home_terminal == driver.home_terminal)).first()
    if truck is None:
        truck = s.exec(select(FleetTruck).where(
            FleetTruck.driver_id == None, FleetTruck.status == "Active")).first()  # noqa: E711
    if truck is None:
        return "no active truck available"

    conn = raw_connection()
    coords = {(c, st): (lat, lon) for c, st, lat, lon in
              conn.execute("SELECT city, state, lat, lon FROM city_coords")}
    conn.close()

    o = (load.origin_city, load.origin_state)
    d = (load.dest_city, load.dest_state)
    geom = _geometry_for(s, o, d, coords)

    pickup_lat, pickup_lon = coords[o]
    deadhead_mi = haversine_miles(driver.lat, driver.lon, pickup_lat, pickup_lon) * ROAD_FACTOR
    arrive = now + timedelta(hours=deadhead_mi / DEADHEAD_MPH + 0.2)
    # quote the ETA with the driver's current clocks: breaks/resets included
    linehaul_min = legal_elapsed_minutes(
        int(geom.distance_miles / PLANNING_MPH * 60),
        drive_used_min=driver.drive_min_used,
        window_used_min=driver.window_min_used,
        since_break_min=driver.min_since_break,
    )
    planned_eta = arrive + timedelta(minutes=45 + linehaul_min)

    trip = LiveTrip(
        trip_id=f"T-{now:%y%m}-{900 + action.id:03d}",
        load_id=load.load_id,
        driver_id=driver.driver_id,
        truck_id=truck.truck_id,
        status=TripStatus.EN_ROUTE_PICKUP,
        geometry_id=geom.id,
        planned_eta=planned_eta,
        started_at=now,
        pickup_arrival_at=arrive,
        total_miles=geom.distance_miles,
        speed_ewma_mph=DEADHEAD_MPH,
        last_ping_at=now,
        fault_script=json.dumps({"assign": {
            "from": [driver.lat, driver.lon],
            "to": [pickup_lat, pickup_lon],
            "depart": now.isoformat(),
        }}),
    )
    load.status = LoadStatus.ASSIGNED
    driver.trip_id = trip.trip_id
    driver.truck_id = truck.truck_id
    truck.trip_id = trip.trip_id
    truck.driver_id = driver.driver_id
    set_duty(s, driver, DriverDuty.DRIVING, now)
    s.add_all([trip, load, driver, truck])

    sms = draft.get("sms_body") or f"New load {load.load_id} for you."
    s.add(MessageLog(channel="SMS", to_name=driver.name, to_addr=driver.phone,
                     body=sms, related_trip_id=trip.trip_id,
                     related_load_id=load.load_id, sent_at=now))
    broadcaster.publish("message", {"channel": "SMS", "to_name": driver.name,
                                    "body": sms, "ts": now})
    broadcaster.publish("feed", {
        "kind": "dispatch", "ts": now,
        "text": f"{driver.name} dispatched on {load.load_id} "
                f"({load.origin_city} -> {load.dest_city}), unit {truck.unit_number}",
        "trip_id": trip.trip_id, "load_id": load.load_id,
    })
    return f"trip {trip.trip_id} created; SMS sent to {driver.name}"


# ---- comms execution ----------------------------------------------------------

def _comms(s: Session, action: PendingAction, draft: dict, now: datetime) -> str:
    impact = json.loads(action.impact)
    exc_id = impact.get("exception_id")
    notes = []
    if draft.get("sms_body"):
        trip = s.get(LiveTrip, action.subject_id)
        driver = s.get(FleetDriver, trip.driver_id) if trip else None
        if driver:
            s.add(MessageLog(channel="SMS", to_name=driver.name, to_addr=driver.phone,
                             body=draft["sms_body"], related_trip_id=action.subject_id,
                             sent_at=now))
            broadcaster.publish("message", {"channel": "SMS", "to_name": driver.name,
                                            "body": draft["sms_body"], "ts": now})
            notes.append(f"SMS to {driver.name}")
    if draft.get("email_body"):
        trip = s.get(LiveTrip, action.subject_id)
        load = s.get(LiveLoad, trip.load_id) if trip else None
        to_name = load.customer_name if load else "Customer"
        s.add(MessageLog(channel="EMAIL", to_name=to_name,
                         to_addr=f"ap@{to_name.lower().replace(' ', '')}.example",
                         subject=draft.get("email_subject", ""),
                         body=draft["email_body"],
                         related_trip_id=action.subject_id, sent_at=now))
        broadcaster.publish("message", {"channel": "EMAIL", "to_name": to_name,
                                        "subject": draft.get("email_subject", ""), "ts": now})
        notes.append(f"email to {to_name}")
    if exc_id:
        exc = s.get(FleetException, exc_id)
        if exc:
            exc.state = ExceptionState.ACTIONED
            exc.updated_at = now
            s.add(exc)
            broadcaster.publish("exception", {"id": exc_id, "state": "ACTIONED"})
    return "; ".join(notes) if notes else "monitoring - no comms sent"


# ---- billing execution ---------------------------------------------------------

def _send_invoice(s: Session, action: PendingAction, draft: dict, now: datetime) -> str:
    packet = s.get(DocPacket, int(action.subject_id))
    load = s.get(LiveLoad, packet.load_id)
    lines = draft["invoice_lines"]
    total = round(sum(l["amount"] for l in lines), 2)
    inv_no = f"INV-{now:%y%m}-{packet.id:03d}"
    pdf_path = INVOICE_DIR / f"{inv_no}.pdf"
    _make_invoice_pdf(pdf_path, inv_no, load, lines, total, now)

    days = round((now - packet.delivered_at).total_seconds() / 86400, 1)
    invoice = Invoice(
        packet_id=packet.id, load_id=load.load_id, lines=json.dumps(lines),
        total=total, status="SENT", pdf_path=str(pdf_path),
        email_subject=draft.get("email_subject", f"Invoice {inv_no}"),
        email_body=draft.get("email_body", ""),
        created_at=now, sent_at=now, days_to_invoice=days,
    )
    packet.status = PacketStatus.INVOICED
    load.status = LoadStatus.INVOICED
    s.add_all([invoice, packet, load])
    s.flush()
    s.add(MessageLog(channel="EMAIL", to_name=load.customer_name,
                     to_addr=f"ap@{load.customer_name.lower().replace(' ', '')}.example",
                     subject=invoice.email_subject, body=invoice.email_body,
                     related_load_id=load.load_id, sent_at=now))
    broadcaster.publish("packet", {"id": packet.id, "status": "INVOICED"})
    broadcaster.publish("message", {"channel": "EMAIL", "to_name": load.customer_name,
                                    "subject": invoice.email_subject, "ts": now})
    broadcaster.publish("feed", {
        "kind": "invoice", "ts": now,
        "text": f"{inv_no} sent to {load.customer_name} - ${total:,.2f} "
                f"({days:.1f} days after delivery)",
        "load_id": load.load_id,
    })
    return f"{inv_no} generated and emailed - ${total:,.2f}"


def _make_invoice_pdf(path, inv_no: str, load: LiveLoad, lines: list[dict],
                      total: float, now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(15, 23, 34)
    pdf.cell(120, 9, "SUNBELT CARRIERS LLC")
    pdf.set_text_color(46, 108, 190)
    pdf.cell(0, 9, "INVOICE", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(120, 5, "4200 Irving Blvd, Dallas, TX 75247 - MC-884217 - remit@sunbeltcarriers.example")
    pdf.set_font("courier", "B", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 5, inv_no, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(160, 160, 160)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(0, 5, f"Bill to: {load.customer_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Load {load.load_id} - {load.origin_city}, {load.origin_state} "
                   f"to {load.dest_city}, {load.dest_state}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Invoice date: {now:%m/%d/%Y}   Terms: Net 30",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    for line in lines:
        pdf.set_font("helvetica", "", 10)
        pdf.cell(140, 7, line["description"])
        pdf.set_font("courier", "", 10)
        pdf.cell(0, 7, f"$ {line['amount']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(140, 8, "TOTAL DUE")
    pdf.set_font("courier", "B", 11)
    pdf.cell(0, 8, f"$ {total:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))
