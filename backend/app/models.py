"""Live-ops plane tables (SQLModel).

Warehouse tables (drivers, trucks, loads, trips, ...) are created by the ETL
with plain SQL and intentionally have no ORM classes — they are read with SQL.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlmodel import Field, SQLModel


class TripStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    EN_ROUTE_PICKUP = "EN_ROUTE_PICKUP"
    AT_PICKUP = "AT_PICKUP"
    IN_TRANSIT = "IN_TRANSIT"
    AT_DELIVERY = "AT_DELIVERY"
    COMPLETED = "COMPLETED"


class LoadStatus(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    INVOICED = "INVOICED"


class EtaState(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"


class DriverDuty(StrEnum):
    OFF = "OFF"
    SLEEPER = "SLEEPER"
    DRIVING = "DRIVING"
    ON_DUTY = "ON_DUTY"  # on duty, not driving


class ExceptionType(StrEnum):
    DARK_LOAD = "DARK_LOAD"
    ROUTE_DEVIATION = "ROUTE_DEVIATION"
    ETA_RISK = "ETA_RISK"
    DETENTION = "DETENTION"
    HOS_RISK = "HOS_RISK"
    MAINTENANCE_DUE = "MAINTENANCE_DUE"


class ExceptionState(StrEnum):
    OPEN = "OPEN"
    TRIAGING = "TRIAGING"
    TRIAGED = "TRIAGED"
    ACTIONED = "ACTIONED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ActionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"


class PacketStatus(StrEnum):
    READY = "READY"
    AUDITING = "AUDITING"
    AUDITED = "AUDITED"
    INVOICED = "INVOICED"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class FleetDriver(SQLModel, table=True):
    __tablename__ = "fleet_drivers"

    driver_id: str = Field(primary_key=True)
    name: str
    phone: str
    home_terminal: str
    years_experience: int
    duty: DriverDuty = DriverDuty.OFF
    truck_id: Optional[str] = None
    trip_id: Optional[str] = None
    lat: float
    lon: float
    # 24-month history features from the warehouse (dispatch scorer inputs)
    on_time_rate: float
    avg_mpg: float
    incident_count: int
    revenue_per_mile: float
    # HOS snapshot recomputed each tick from hos_events
    drive_min_used: int = 0
    window_min_used: int = 0
    cycle_min_used: int = 0
    min_since_break: int = 0
    hos_violation_flags: str = ""  # comma-joined codes, empty = clean

    def drive_min_remaining_calc(self) -> int:
        return max(0, 11 * 60 - self.drive_min_used)

    def window_min_remaining_calc(self) -> int:
        return max(0, 14 * 60 - self.window_min_used)

    def cycle_min_remaining_calc(self) -> int:
        return max(0, 70 * 60 - self.cycle_min_used)


class FleetTruck(SQLModel, table=True):
    __tablename__ = "fleet_trucks"

    truck_id: str = Field(primary_key=True)
    unit_number: str
    make: str
    model_year: int
    home_terminal: str
    status: str  # Active | Maintenance
    driver_id: Optional[str] = None
    trip_id: Optional[str] = None
    lat: float
    lon: float
    heading_deg: float = 0.0
    speed_mph: float = 0.0
    odometer_miles: float
    fuel_pct: float = 90.0
    last_pm_date: datetime
    next_pm_due: datetime
    annual_inspection_expiry: datetime


class LiveLoad(SQLModel, table=True):
    __tablename__ = "live_loads"

    load_id: str = Field(primary_key=True)
    source_load_id: str  # lineage to the warehouse row it was re-anchored from
    customer_id: str
    customer_name: str
    route_id: str
    origin_city: str
    origin_state: str
    dest_city: str
    dest_state: str
    pickup_facility_id: str
    dest_facility_id: str
    load_type: str
    weight_lbs: int
    pieces: int
    revenue: float
    fuel_surcharge: float
    accessorial_charges: float
    booking_type: str
    distance_miles: float
    pickup_window_start: datetime
    pickup_window_end: datetime
    delivery_deadline: datetime
    status: LoadStatus = LoadStatus.UNASSIGNED


class LiveTrip(SQLModel, table=True):
    __tablename__ = "live_trips"

    trip_id: str = Field(primary_key=True)
    load_id: str = Field(index=True)
    driver_id: str
    truck_id: str
    status: TripStatus
    geometry_id: int  # route_geometries row
    planned_eta: datetime
    started_at: datetime
    pickup_arrival_at: Optional[datetime] = None  # deadhead leg ETA (EN_ROUTE_PICKUP)
    progress_miles: float = 0.0
    total_miles: float
    speed_ewma_mph: float = 0.0
    eta_state: EtaState = EtaState.NORMAL
    projected_eta: Optional[datetime] = None
    last_ping_at: Optional[datetime] = None
    dwell_facility_id: Optional[str] = None
    dwell_started_at: Optional[datetime] = None
    rest_until: Optional[datetime] = None  # parked for HOS break/reset
    rest_kind: str = ""                    # "break" | "reset"
    detention_min: int = 0
    off_route: bool = False
    off_route_pings: int = 0
    completed_at: Optional[datetime] = None
    fault_script: str = "{}"  # JSON: scripted telemetry faults for the demo world


class PingLog(SQLModel, table=True):
    __tablename__ = "ping_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: str = Field(index=True)
    ts: datetime
    lat: float
    lon: float
    speed_mph: float
    heading_deg: float


class HosEvent(SQLModel, table=True):
    __tablename__ = "hos_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    driver_id: str = Field(index=True)
    duty: DriverDuty
    start: datetime
    end: Optional[datetime] = None  # open interval = current status


class RouteGeometry(SQLModel, table=True):
    __tablename__ = "route_geometries"

    id: Optional[int] = Field(default=None, primary_key=True)
    lane_key: str = Field(index=True)  # "DallasTX->ChicagoIL" (+ ":detour" variants)
    encoded_polyline: str
    distance_miles: float
    duration_hours: float
    source: str  # osrm | greatcircle


class FleetException(SQLModel, table=True):
    __tablename__ = "exceptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: ExceptionType
    severity: str  # WATCH | HIGH | CRITICAL
    state: ExceptionState = ExceptionState.OPEN
    trip_id: Optional[str] = Field(default=None, index=True)
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    load_id: Optional[str] = None
    title: str
    detail: str = "{}"  # JSON payload with detector evidence
    detected_at: datetime
    updated_at: datetime
    agent_run_id: Optional[int] = None


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str  # dispatch | triage | analyst | safety | billing
    subject_id: str
    status: RunStatus = RunStatus.RUNNING
    model: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    summary: str = ""
    error: str = ""


class AgentStep(SQLModel, table=True):
    __tablename__ = "agent_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    seq: int
    kind: str  # thought | tool_call | tool_result | output
    name: str = ""
    payload: str = "{}"
    ts: datetime


class PendingAction(SQLModel, table=True):
    __tablename__ = "pending_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int
    kind: str  # ASSIGN_DRIVER | SMS_DRIVER | EMAIL_CUSTOMER | REROUTE | SCHEDULE_MAINTENANCE | SEND_INVOICE
    title: str
    subject_id: str  # load/trip/packet the action applies to
    impact: str = "{}"    # JSON: quantified impact estimates
    draft: str = "{}"     # JSON: editable fields (sms body, email subject/body, assignment)
    rationale: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime
    decided_at: Optional[datetime] = None
    executed_note: str = ""


class MessageLog(SQLModel, table=True):
    __tablename__ = "message_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    channel: str  # SMS | EMAIL
    to_name: str
    to_addr: str
    subject: str = ""
    body: str
    related_trip_id: Optional[str] = None
    related_load_id: Optional[str] = None
    sent_at: datetime


class DocPacket(SQLModel, table=True):
    __tablename__ = "doc_packets"

    id: Optional[int] = Field(default=None, primary_key=True)
    load_id: str = Field(index=True)
    delivered_at: datetime
    docs: str = "[]"          # JSON list [{doc_type, filename, title}]
    truth: str = "{}"         # JSON system-of-record values (never shown to the LLM)
    status: PacketStatus = PacketStatus.READY
    extraction: str = "{}"    # JSON: Gemini Vision output per document
    reconciliation: str = "{}"  # JSON: deterministic diff results
    audit_memo: str = ""
    agent_run_id: Optional[int] = None


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: Optional[int] = Field(default=None, primary_key=True)
    packet_id: int
    load_id: str
    lines: str = "[]"  # JSON [{description, amount}]
    total: float
    status: str = "DRAFT"  # DRAFT | SENT
    pdf_path: str = ""
    email_subject: str = ""
    email_body: str = ""
    created_at: datetime
    sent_at: Optional[datetime] = None
    days_to_invoice: float = 0.0


class SimState(SQLModel, table=True):
    __tablename__ = "sim_state"

    id: int = Field(default=1, primary_key=True)
    t0: datetime
    sim_now: datetime
    speed: int
    running: bool = True


class AiSpend(SQLModel, table=True):
    """Gemini requests actually sent, per quota day (America/Los_Angeles,
    matching Google's daily reset). Deliberately NOT wiped by demo reset or
    server restart - Google's counter doesn't reset either."""
    __tablename__ = "ai_spend"

    day: str = Field(primary_key=True)
    requests: int = 0
