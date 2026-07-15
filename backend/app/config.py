"""Central configuration: paths, environment, domain constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
ARCHIVE_DIR = REPO_DIR / "archive"
DATA_DIR = BACKEND_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
INVOICE_DIR = DATA_DIR / "invoices"
DB_PATH = DATA_DIR / "fleet.db"

load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

# ---- AI event gate ----------------------------------------------------------
# Generative AI is budgeted: detection is deterministic and free, every actual
# Gemini request is metered (persisted per Pacific-time quota day, matching
# Google's reset). Auto-investigation defaults OFF so the demo spends quota
# only when a human clicks (Option B: event-gated hybrid).
AI_DAILY_REQUEST_BUDGET = int(os.getenv("AI_DAILY_REQUEST_BUDGET", "100"))
# A tool-loop run makes up to ~11 requests; don't admit a run without this
# much headroom, so it can't die halfway through an investigation.
AI_RUN_RESERVE_REQUESTS = int(os.getenv("AI_RUN_RESERVE_REQUESTS", "12"))
AI_AUTO_INVESTIGATE_DEFAULT = os.getenv("AI_AUTO_INVESTIGATE", "0") == "1"
AI_AUTO_MIN_GAP_S = int(os.getenv("AI_AUTO_MIN_GAP_S", "3600"))

# Resolved at startup against ListModels; first available wins.
MODEL_PREFERENCE = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
]

SEED = 42

# ---- Live fleet carve -------------------------------------------------------
FLEET_TERMINALS = ("Dallas", "Houston", "Oklahoma City")
FLEET_NAME = "Sunbelt Carriers — TX/OK Regional Fleet"

# Route cities that have no facility row in the dataset.
EXTRA_CITY_COORDS = {
    ("Columbus", "OH"): (39.9612, -82.9988),
    ("Memphis", "TN"): (35.1495, -90.0490),
    ("Minneapolis", "MN"): (44.9778, -93.2650),
    ("Seattle", "WA"): (47.6062, -122.3321),
}

# ---- Simulation -------------------------------------------------------------
SIM_TICK_WALL_SECONDS = 2.0     # wall-clock cadence of the background loop
SIM_SPEED_DEFAULT = 30          # sim-seconds advanced per wall-second
PING_INTERVAL_SIM_MIN = 4       # GPS ping cadence in sim time
LINEHAUL_BASE_MPH = 58.0
PING_LOG_CAP_PER_TRIP = 600

# ---- Watchdog thresholds ----------------------------------------------------
DARK_GAP_MIN = 35               # minutes without a ping while moving
DEVIATION_CORRIDOR_MI = 2.5     # distance from planned polyline
DEVIATION_CONFIRM_PINGS = 3     # consecutive off-corridor pings (hysteresis)
ETA_WATCH_SLIP_MIN = 20
ETA_RISK_SLIP_MIN = 45
ETA_CRITICAL_SLIP_MIN = 90
DETENTION_FREE_MIN = 120        # industry-standard free time at dock
DETENTION_RATE_PER_HR = 75.0
SPEED_EWMA_ALPHA = 0.25

# ---- FMCSA Hours of Service (property-carrying) -----------------------------
HOS_DRIVE_LIMIT_MIN = 11 * 60
HOS_WINDOW_LIMIT_MIN = 14 * 60
HOS_BREAK_AFTER_DRIVE_MIN = 8 * 60
HOS_BREAK_MIN = 30
HOS_CYCLE_LIMIT_MIN = 70 * 60   # 70h / 8 days
HOS_CYCLE_DAYS = 8
HOS_RESTART_OFF_MIN = 34 * 60
HOS_WARN_DRIVE_REMAINING_MIN = 60

# ---- Maintenance / compliance -----------------------------------------------
PM_INTERVAL_DAYS = 90           # preventive maintenance cadence
ANNUAL_INSPECTION_DAYS = 365    # 49 CFR 396.17 periodic inspection

# ---- Billing ----------------------------------------------------------------
PACKET_COUNT = 12
PACKET_DISCREPANCY_COUNT = 5
