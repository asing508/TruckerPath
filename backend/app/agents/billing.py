"""Billing Auditor.

Three phases per packet:
  1. VISION (real LLM): Gemini reads each PDF and extracts typed fields.
  2. RECONCILE (deterministic): code diffs the extraction against the system
     of record - rate, accessorials, weight, receipt count, and detention
     recomputed from documented dock times cross-checked against GPS dwell.
     Money math is never delegated to the model.
  3. MEMO (real LLM): Gemini writes the audit memo + invoice email around the
     confirmed numbers. The dispatcher approves before anything is "sent".

The packet's `truth.discrepancy` label is the grading key for the demo and is
never given to the model or the reconciler.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from google.genai import types
from sqlmodel import Session

from ..config import DETENTION_FREE_MIN, DETENTION_RATE_PER_HR, DOCS_DIR, GEMINI_VISION_MODEL
from ..db import engine
from ..models import DocPacket, LiveLoad, PacketStatus, PendingAction
from ..streams import broadcaster
from .gemini import Tracer, finish_run, start_run, structured_call
from .schemas import (
    BillingAudit,
    BolExtract,
    FuelReceiptExtract,
    PodExtract,
    RateConExtract,
)

EXTRACT_SCHEMAS = {
    "RATE_CONFIRMATION": (RateConExtract, "rate confirmation"),
    "BOL": (BolExtract, "bill of lading"),
    "POD": (PodExtract, "proof of delivery"),
    "FUEL_RECEIPT": (FuelReceiptExtract, "fuel receipt"),
}

VISION_SYSTEM = (
    "You extract structured fields from freight paperwork images/PDFs. "
    "Read carefully, keep numbers exactly as printed (no rounding), use 0 for "
    "charges that do not appear. Times must be HH:MM 24h as printed."
)


def _parse_hhmm(v: str) -> int | None:
    try:
        h, m = v.strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def reconcile(extraction: dict, load: LiveLoad, system: dict) -> dict:
    """Deterministic diff of documents vs system of record."""
    diffs: list[dict] = []
    ratecon = extraction.get("RATE_CONFIRMATION") or {}
    bol = extraction.get("BOL") or {}
    pod = extraction.get("POD") or {}
    receipts = extraction.get("FUEL_RECEIPTS") or []

    linehaul = float(ratecon.get("linehaul_amount") or 0)
    if linehaul and abs(linehaul - load.revenue) > 1.0:
        direction = "below" if linehaul < load.revenue else "above"
        diffs.append({
            "code": "RATE_MISMATCH",
            "description": (f"Rate confirmation linehaul ${linehaul:,.2f} is {direction} "
                            f"system quote ${load.revenue:,.2f}"),
            "amount_usd": round(load.revenue - linehaul, 2),
            "bill_using": "system_quote",
        })

    acc_doc = float(ratecon.get("accessorial_amount") or 0)
    if load.accessorial_charges > 0 and acc_doc == 0:
        diffs.append({
            "code": "ACCESSORIAL_MISSING",
            "description": (f"System shows ${load.accessorial_charges:,.2f} accessorial "
                            f"(lumper/unload) not present on the rate confirmation"),
            "amount_usd": load.accessorial_charges,
            "bill_using": "system_accessorial",
        })

    detention_due = 0.0
    t_in, t_out = _parse_hhmm(pod.get("time_in", "")), _parse_hhmm(pod.get("time_out", ""))
    if t_in is not None and t_out is not None:
        dwell = t_out - t_in if t_out >= t_in else t_out + 1440 - t_in
        gps_dwell = system.get("gps_dwell_minutes")
        corroborated = gps_dwell is not None and abs(gps_dwell - dwell) <= 25
        billable = max(0, dwell - DETENTION_FREE_MIN)
        if billable > 0:
            detention_due = round(billable / 60 * DETENTION_RATE_PER_HR, 2)
            if float(ratecon.get("detention_amount") or 0) == 0:
                diffs.append({
                    "code": "DETENTION_UNCLAIMED",
                    "description": (f"POD shows {dwell} min at the dock ({billable} min past "
                                    f"free time). GPS dwell {'corroborates' if corroborated else 'differs: ' + str(gps_dwell) + ' min'}."
                                    f" ${detention_due:,.2f} billable at ${DETENTION_RATE_PER_HR:.0f}/hr not on rate con"),
                    "amount_usd": detention_due,
                    "bill_using": "pod_times",
                })

    weight_doc = int(bol.get("weight_lbs") or 0)
    if weight_doc and abs(weight_doc - load.weight_lbs) > 500:
        diffs.append({
            "code": "WEIGHT_MISMATCH",
            "description": (f"BOL weight {weight_doc:,} lbs vs booked {load.weight_lbs:,} lbs "
                            f"({weight_doc - load.weight_lbs:+,} lbs) - verify scale ticket / re-rate risk"),
            "amount_usd": 0.0,
            "bill_using": "flag_only",
        })

    n_sys = int(system.get("fuel_purchases_in_system") or 0)
    if n_sys and len(receipts) < n_sys:
        diffs.append({
            "code": "FUEL_RECEIPT_MISSING",
            "description": (f"Fuel card feed shows {n_sys} purchases on this trip; driver "
                            f"submitted {len(receipts)} receipt(s) - chase the missing one for IFTA"),
            "amount_usd": 0.0,
            "bill_using": "flag_only",
        })

    lines = [
        {"description": f"Linehaul - {load.origin_city} to {load.dest_city}", "amount": load.revenue},
        {"description": "Fuel surcharge", "amount": load.fuel_surcharge},
    ]
    if load.accessorial_charges > 0:
        lines.append({"description": "Accessorial (lumper/unload per contract)",
                      "amount": load.accessorial_charges})
    if detention_due > 0:
        lines.append({"description": f"Detention ({DETENTION_FREE_MIN / 60:.0f}h free, "
                                     f"${DETENTION_RATE_PER_HR:.0f}/hr, per POD in/out times)",
                      "amount": detention_due})
    total = round(sum(l["amount"] for l in lines), 2)
    return {"diffs": diffs, "invoice_lines": lines, "invoice_total": total,
            "clean": len(diffs) == 0}


async def audit_packet(packet_id: int) -> dict:
    with Session(engine) as s:
        packet = s.get(DocPacket, packet_id)
        if packet is None:
            return {"error": "packet not found"}
        if packet.status == PacketStatus.AUDITING:
            return {"error": "already auditing"}
        load = s.get(LiveLoad, packet.load_id)
        docs = json.loads(packet.docs)
        system_feed = {k: v for k, v in json.loads(packet.truth).items()
                       if k in ("gps_dwell_minutes", "fuel_purchases_in_system")}
        packet.status = PacketStatus.AUDITING
        s.add(packet)
        s.commit()
    broadcaster.publish("packet", {"id": packet_id, "status": "AUDITING"})

    run_id, tracer = start_run("billing", packet.load_id)
    try:
        extraction: dict = {"FUEL_RECEIPTS": []}
        for doc in docs:
            schema, label = EXTRACT_SCHEMAS[doc["doc_type"]]
            pdf_path = DOCS_DIR / packet.load_id / doc["filename"]
            tracer.emit("tool_call", name="vision_extract",
                        payload={"document": doc["title"], "file": doc["filename"]})
            parsed = await structured_call(
                system=VISION_SYSTEM,
                parts=[
                    types.Part.from_bytes(data=pdf_path.read_bytes(),
                                          mime_type="application/pdf"),
                    types.Part.from_text(text=f"Extract the fields from this {label}."),
                ],
                output_schema=schema,
                model=GEMINI_VISION_MODEL or None,
            )
            data = json.loads(parsed.model_dump_json())
            tracer.emit("tool_result", name="vision_extract", payload=data)
            if doc["doc_type"] == "FUEL_RECEIPT":
                extraction["FUEL_RECEIPTS"].append(data)
            else:
                extraction[doc["doc_type"]] = data

        with Session(engine) as s:
            load = s.get(LiveLoad, packet.load_id)
        recon = reconcile(extraction, load, system_feed)
        tracer.emit("tool_result", name="reconcile", payload={
            "diffs": recon["diffs"], "invoice_total": recon["invoice_total"],
            "clean": recon["clean"]})

        memo: BillingAudit = await structured_call(
            system=("You are the billing auditor for Sunbelt Carriers. Write the audit "
                    "memo and the invoice email for this delivered load. The reconciler's "
                    "numbers are authoritative - explain them, do not change them. Memo: "
                    "markdown, what was verified, each discrepancy and its dollar impact, "
                    "what the dispatcher should confirm before sending. Email: to the "
                    "customer's AP desk, professional, references load and PO, itemizes "
                    "charges, notes POD-documented detention where applicable. No emojis."),
            parts=[types.Part.from_text(text=json.dumps({
                "load": {"load_id": load.load_id, "customer": load.customer_name,
                         "lane": f"{load.origin_city}->{load.dest_city}",
                         "booking_type": load.booking_type,
                         "credit_terms_days": 30},
                "extraction": extraction,
                "reconciliation": recon,
            }, default=str))],
            output_schema=BillingAudit,
            temperature=0.3,
        )
        tracer.emit("output", payload=json.loads(memo.model_dump_json()))

        with Session(engine) as s:
            packet = s.get(DocPacket, packet_id)
            packet.extraction = json.dumps(extraction)
            packet.reconciliation = json.dumps(recon)
            packet.audit_memo = memo.memo_markdown
            packet.status = PacketStatus.AUDITED
            packet.agent_run_id = run_id
            s.add(packet)

            action = PendingAction(
                run_id=run_id,
                kind="SEND_INVOICE",
                title=(f"Invoice {load.load_id} - ${recon['invoice_total']:,.2f}"
                       + (f" ({len(recon['diffs'])} finding(s))" if recon["diffs"] else " (clean)")),
                subject_id=str(packet_id),
                impact=json.dumps({
                    "invoice_total": recon["invoice_total"],
                    "recovered_usd": round(sum(d["amount_usd"] for d in recon["diffs"]), 2),
                    "findings": [d["code"] for d in recon["diffs"]],
                }),
                draft=json.dumps({
                    "invoice_lines": recon["invoice_lines"],
                    "invoice_total": recon["invoice_total"],
                    "email_subject": memo.email_subject,
                    "email_body": memo.email_body,
                }),
                rationale=memo.memo_markdown,
                created_at=datetime.now(),
            )
            s.add(action)
            s.commit()
            s.refresh(action)

        finish_run(run_id, summary=f"{len(recon['diffs'])} finding(s); "
                                   f"invoice ${recon['invoice_total']:,.2f}")
        broadcaster.publish("packet", {"id": packet_id, "status": "AUDITED"})
        broadcaster.publish("action", {"id": action.id, "kind": action.kind,
                                       "title": action.title, "status": "PENDING"})
        return {"run_id": run_id, "action_id": action.id,
                "reconciliation": recon, "memo": memo.model_dump()}
    except Exception as e:
        with Session(engine) as s:
            packet = s.get(DocPacket, packet_id)
            packet.status = PacketStatus.READY
            s.add(packet)
            s.commit()
        finish_run(run_id, summary="", error=str(e))
        broadcaster.publish("packet", {"id": packet_id, "status": "READY"})
        return {"run_id": run_id, "error": str(e)}
