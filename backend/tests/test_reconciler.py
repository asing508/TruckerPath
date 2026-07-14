from datetime import datetime

from app.agents.billing import reconcile
from app.models import LiveLoad, LoadStatus


def make_load(**kw) -> LiveLoad:
    base = dict(
        load_id="L-1", source_load_id="LOAD1", customer_id="C1",
        customer_name="Acme", route_id="R1",
        origin_city="Dallas", origin_state="TX", dest_city="Denver", dest_state="CO",
        pickup_facility_id="F1", dest_facility_id="F2",
        load_type="Dry Van", weight_lbs=30000, pieces=20,
        revenue=2500.0, fuel_surcharge=300.0, accessorial_charges=0.0,
        booking_type="Contract", distance_miles=795.0,
        pickup_window_start=datetime(2026, 7, 10, 8),
        pickup_window_end=datetime(2026, 7, 10, 10),
        delivery_deadline=datetime(2026, 7, 11, 8),
        status=LoadStatus.DELIVERED,
    )
    base.update(kw)
    return LiveLoad(**base)


def extraction(ratecon=None, bol=None, pod=None, receipts=None) -> dict:
    return {
        "RATE_CONFIRMATION": ratecon or {
            "linehaul_amount": 2500.0, "fuel_surcharge": 300.0,
            "accessorial_amount": 0.0, "detention_amount": 0.0,
            "total_amount": 2800.0},
        "BOL": bol or {"bol_number": "B1", "pieces": 20, "weight_lbs": 30000,
                       "shipper": "X", "consignee": "Y"},
        "POD": pod or {"load_number": "L-1", "delivery_date": "07/11/2026",
                       "time_in": "08:00", "time_out": "09:30",
                       "pieces_received": 20, "exceptions_noted": "none"},
        "FUEL_RECEIPTS": receipts if receipts is not None else [{"total": 400.0}],
    }


def test_clean_packet_reconciles_clean():
    r = reconcile(extraction(), make_load(), {"gps_dwell_minutes": 90,
                                              "fuel_purchases_in_system": 1})
    assert r["clean"] is True
    assert r["invoice_total"] == 2800.0


def test_rate_mismatch_detected():
    ext = extraction(ratecon={"linehaul_amount": 2300.0, "fuel_surcharge": 300.0,
                              "accessorial_amount": 0.0, "detention_amount": 0.0,
                              "total_amount": 2600.0})
    r = reconcile(ext, make_load(), {"fuel_purchases_in_system": 1})
    codes = [d["code"] for d in r["diffs"]]
    assert "RATE_MISMATCH" in codes
    # invoice still bills the system quote
    assert r["invoice_total"] == 2800.0


def test_detention_unclaimed_computed_from_pod_times():
    ext = extraction(pod={"load_number": "L-1", "delivery_date": "07/11/2026",
                          "time_in": "08:00", "time_out": "11:54",
                          "pieces_received": 20, "exceptions_noted": "none"})
    r = reconcile(ext, make_load(), {"gps_dwell_minutes": 234,
                                     "fuel_purchases_in_system": 1})
    det = [d for d in r["diffs"] if d["code"] == "DETENTION_UNCLAIMED"]
    assert det, r["diffs"]
    # 234 min dwell - 120 free = 114 min -> $142.50 at $75/hr
    assert abs(det[0]["amount_usd"] - 142.50) < 0.01
    assert any("Detention" in l["description"] for l in r["invoice_lines"])


def test_missing_accessorial_and_receipt_and_weight():
    load = make_load(accessorial_charges=150.0, weight_lbs=28900)
    ext = extraction(bol={"bol_number": "B1", "pieces": 20, "weight_lbs": 31300,
                          "shipper": "X", "consignee": "Y"}, receipts=[])
    r = reconcile(ext, load, {"fuel_purchases_in_system": 2})
    codes = {d["code"] for d in r["diffs"]}
    assert {"ACCESSORIAL_MISSING", "FUEL_RECEIPT_MISSING", "WEIGHT_MISMATCH"} <= codes
    assert r["invoice_total"] == 2500.0 + 300.0 + 150.0
