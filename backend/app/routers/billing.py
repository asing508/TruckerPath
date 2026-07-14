"""Billing & document automation: packets, audits, invoices, files."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..agents import billing as billing_agent
from ..config import DOCS_DIR, INVOICE_DIR
from ..db import engine
from ..models import DocPacket, Invoice, LiveLoad, SimState

router = APIRouter(prefix="/api/billing", tags=["billing"])

_background: set[asyncio.Task] = set()


def _packet_dict(p: DocPacket, load: LiveLoad | None, sim_now) -> dict:
    recon = json.loads(p.reconciliation) if p.reconciliation != "{}" else None
    return {
        "id": p.id,
        "load_id": p.load_id,
        "customer": load.customer_name if load else "",
        "lane": (f"{load.origin_city}, {load.origin_state} -> "
                 f"{load.dest_city}, {load.dest_state}") if load else "",
        "revenue": load.revenue if load else 0,
        "booking_type": load.booking_type if load else "",
        "delivered_at": p.delivered_at,
        "age_days": round((sim_now - p.delivered_at).total_seconds() / 86400, 1),
        "status": p.status,
        "docs": json.loads(p.docs),
        "findings": [d["code"] for d in recon["diffs"]] if recon else None,
        "invoice_total": recon["invoice_total"] if recon else None,
        "agent_run_id": p.agent_run_id,
    }


@router.get("/packets")
def packets() -> dict:
    with Session(engine) as s:
        sim_now = s.get(SimState, 1).sim_now
        rows = s.exec(select(DocPacket).order_by(DocPacket.delivered_at.desc())).all()  # type: ignore[attr-defined]
        loads = {l.load_id: l for l in s.exec(select(LiveLoad)).all()}
        invoices = s.exec(select(Invoice)).all()
        avg_days = (round(sum(i.days_to_invoice for i in invoices) / len(invoices), 1)
                    if invoices else None)
        return {
            "packets": [_packet_dict(p, loads.get(p.load_id), sim_now) for p in rows],
            "kpis": {
                "ready": sum(1 for p in rows if p.status == "READY"),
                "audited": sum(1 for p in rows if p.status == "AUDITED"),
                "invoiced": sum(1 for p in rows if p.status == "INVOICED"),
                "avg_days_to_invoice": avg_days,
                "recovered_usd": round(sum(
                    sum(d.get("amount_usd", 0) for d in json.loads(p.reconciliation)["diffs"])
                    for p in rows if p.reconciliation != "{}"), 2),
            },
        }


@router.get("/packets/{packet_id}")
def packet_detail(packet_id: int) -> dict:
    with Session(engine) as s:
        p = s.get(DocPacket, packet_id)
        if p is None:
            raise HTTPException(404)
        sim_now = s.get(SimState, 1).sim_now
        load = s.get(LiveLoad, p.load_id)
        out = _packet_dict(p, load, sim_now)
        out["extraction"] = json.loads(p.extraction) if p.extraction != "{}" else None
        out["reconciliation"] = (json.loads(p.reconciliation)
                                 if p.reconciliation != "{}" else None)
        out["audit_memo"] = p.audit_memo
        invoice = s.exec(select(Invoice).where(Invoice.packet_id == packet_id)).first()
        if invoice:
            out["invoice"] = {
                "lines": json.loads(invoice.lines), "total": invoice.total,
                "status": invoice.status, "sent_at": invoice.sent_at,
                "days_to_invoice": invoice.days_to_invoice,
                "pdf": f"/api/billing/invoice-pdf/{invoice.id}",
                "email_subject": invoice.email_subject,
                "email_body": invoice.email_body,
            }
        return out


@router.post("/packets/{packet_id}/audit")
async def audit(packet_id: int) -> dict:
    task = asyncio.create_task(billing_agent.audit_packet(packet_id))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"started": True}


@router.get("/doc/{load_id}/{filename}")
def doc_pdf(load_id: str, filename: str):
    path = (DOCS_DIR / load_id / filename).resolve()
    if not path.is_file() or DOCS_DIR.resolve() not in path.parents:
        raise HTTPException(404)
    return FileResponse(path, media_type="application/pdf")


@router.get("/invoice-pdf/{invoice_id}")
def invoice_pdf(invoice_id: int):
    with Session(engine) as s:
        inv = s.get(Invoice, invoice_id)
        if inv is None or not inv.pdf_path:
            raise HTTPException(404)
    path = (INVOICE_DIR / inv.pdf_path.split("\\")[-1].split("/")[-1]).resolve()
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/pdf")
