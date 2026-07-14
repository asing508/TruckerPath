"""Structured output contracts for every agent (Gemini response_schema)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Alternate(BaseModel):
    driver_id: str
    name: str
    reason_not_first: str


class DispatchRecommendation(BaseModel):
    recommended_driver_id: str
    recommended_driver_name: str
    deadhead_miles: float
    rationale: str = Field(description="Dispatcher-facing markdown, cite tool evidence")
    sms_draft: str = Field(description="Text message to the recommended driver")
    alternates: list[Alternate]
    risks: list[str]


class EmailDraft(BaseModel):
    subject: str
    body: str


class TriageAssessment(BaseModel):
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    root_cause_hypothesis: str
    recommended_action: Literal[
        "MONITOR", "CALL_DRIVER", "REROUTE", "RELAY_SWAP",
        "NOTIFY_CUSTOMER", "SCHEDULE_MAINTENANCE", "PLAN_REST_STOP",
    ]
    action_summary: str
    impact_estimate: str
    customer_email: Optional[EmailDraft] = None
    driver_sms: Optional[str] = None


class ChartSeries(BaseModel):
    name: str
    values: list[float]


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "area"]
    title: str
    x: list[str]
    series: list[ChartSeries]


class AnalystAnswer(BaseModel):
    answer_markdown: str
    sql_used: Optional[str] = None
    chart: Optional[ChartSpec] = None


class SafetyBrief(BaseModel):
    risk_level: Literal["LOW", "GUARDED", "ELEVATED", "SEVERE"]
    brief_markdown: str
    talking_points: list[str]


class BillingAudit(BaseModel):
    memo_markdown: str = Field(description="Audit memo: what was checked, what was found")
    confirmed_discrepancies: list[str]
    email_subject: str
    email_body: str


# ---- Vision extraction contracts (one per document type) ---------------------

class RateConExtract(BaseModel):
    load_number: str
    linehaul_amount: float
    fuel_surcharge: float
    accessorial_amount: float
    detention_amount: float
    total_amount: float
    weight_lbs: Optional[int] = None
    pickup_location: str
    delivery_location: str


class BolExtract(BaseModel):
    bol_number: str
    pieces: int
    weight_lbs: int
    shipper: str
    consignee: str


class PodExtract(BaseModel):
    load_number: str
    delivery_date: str
    time_in: str
    time_out: str
    pieces_received: int
    exceptions_noted: str


class FuelReceiptExtract(BaseModel):
    station: str
    gallons: float
    price_per_gallon: float
    total: float
    reference_load: Optional[str] = None
