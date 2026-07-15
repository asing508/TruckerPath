# Fleet Copilot - Trucker Path PM Take-Home

An **AI-native fleet operations assistant** for small fleets (5–50 trucks). It
watches every load, investigates its own alarms with real LLM tool-calling,
and hands the dispatcher **decisions instead of dashboards** - covering all
five problem areas from the brief: Smart Dispatch, Proactive Alerts, Cost
Intelligence, Safety & Compliance, and Billing & Document Automation.

> The standalone product deck is
> [`docs/Fleet-Copilot-Deck.pptx`](docs/Fleet-Copilot-Deck.pptx).

## The idea in one paragraph

Fleet software has historically been a *system of record*: it shows a dot on a
map, fires an alert, and waits for a human to do everything else. Fleet
Copilot is built as a *system of agency*: deterministic watchdogs detect
exceptions in live telemetry (dark loads, route deviation, ETA slip, dock
detention, HOS risk, maintenance lapses), a Gemini agent investigates each one
through read-only fleet tools, and the result is always a **pending action** -
a drafted SMS/email/invoice with quantified impact that the dispatcher can
edit inline and approve. The model reasons, the code computes (HOS ledger,
detention math, invoice totals are never delegated to the LLM), and the human
decides.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 · React 19 · Tailwind v4 · shadcn/ui · MapLibre GL (keyless CARTO basemap) · TanStack Query · Recharts |
| Backend | FastAPI · SQLModel · SQLite (WAL) · SSE (`sse-starlette`) |
| AI | `google-genai` SDK · Gemini 3.5 Flash (per-model quota circuit breaker, ≤1 fallback per call) · manual tool-loop with per-step tracing · Gemini Vision for document extraction (persisted per document) · per-request daily budget, event-gated invocation |
| Data | 3-year Class 8 carrier operations dataset (14 CSVs, ~550k rows) + simulated live plane (OSRM road geometry, FMCSA HOS ledger) |

## Run it locally

Prereqs: Python 3.12+, `uv`, Node 20+.

```bash
# 1 — backend (first boot auto-seeds SQLite from ./archive, ~1 min)
cd backend
cp .env.example .env         # put your GEMINI_API_KEY in .env
uv sync
uv run uvicorn app.main:app --port 8000

# 2 — frontend (second terminal)
cd frontend
npm install
npm run dev                  # http://localhost:3000
```

Optional: re-seed a fresh world at any time with
`uv run python -m app.etl.seed`, or click **reset demo** in the app's blue
simulation strip.

### Tests

```bash
cd backend && uv run python -m pytest tests/ -q
```

Covers the FMCSA HOS ledger, the legal-schedule generator, geodesic math for
the deviation detector, the billing reconciler, the guarded-SQL layer
(SELECT-only authorizer, denylisted tables), and a sim smoke test that proves
the scripted faults are *detected*, not hardcoded.

## A 10-minute demo script

1. **Operations** — live map with the fleet moving along real road geometry.
   Within a few sim-minutes the watchdog flags the scripted incidents: a load
   goes **dark** mid-route, a truck **drifts off corridor**, a slowdown pushes
   an ETA into **at-risk**, a dwell at the dock starts **accruing detention**,
   and two drivers approach **mandatory HOS stops**. Detection is fully
   deterministic - no LLM is spent watching the fleet. Click **Send agent to
   investigate** on any exception and open **Agent trace** (top right) to
   watch the model's actual tool calls; or flip **auto-AI on** in the blue
   strip to let the watchdog summon the agent itself for CRITICAL incidents
   (at most one an hour, inside the daily budget).
2. **Approve something** — edit the drafted SMS inline, hit *Approve &
   execute*, then open **Driver phone** to see what the driver received.
3. **Dispatch** — pick an unassigned load, compare scored candidates
   (deadhead, HOS slack, lane familiarity, on-time, safety), then *Ask agent
   to recommend*. Approving the recommendation creates a live trip you can
   watch leave on the map.
4. **Cost** — KPIs and margin-per-mile over 36 months of real data; ask the
   fleet a question in English ("Which customers cause the most detention?")
   and watch the guarded SQL run in the trace.
5. **Safety** — HOS clocks per driver, risk watchlist (one driver is seeded at
   66 h of the 70 h cycle), equipment PM/inspection flags, agent-written
   coaching briefs.
6. **Billing** — open a delivered packet, *Run agent audit*: Gemini Vision
   reads the rate con/BOL/POD/receipts, the reconciler diffs them against the
   system of record, and discrepancies surface with dollar impact (one packet
   hides an unclaimed **$142.50 detention** documented by POD dock times and
   corroborated by GPS dwell). Approve to generate and "send" the invoice PDF.
   These packet PDFs are deterministic demo fixtures generated at seed/reset;
   the prototype has no upload connector. A production version would ingest
   driver scans, email attachments, or TMS/ELD document feeds.

## Architecture

```
archive/*.csv ──ETL──▶ SQLite warehouse (loads, trips, fuel, events, + derived stats)
                            │
                            ├─ analytics API  ──▶ Cost page (real 3-year numbers)
                            ├─ guarded run_sql ─▶ "Ask your fleet" agent
                            │
                       fleet carve (Dallas/Houston/OKC, 14 trucks)
                            │
                       live plane: SimEngine (asyncio)
                        clock ▸ mover (OSRM polylines, HOS rest stops)
                              ▸ HOS ledger snapshots (FMCSA 11h/14h/70h·8d)
                              ▸ watchdog detectors (state machines + hysteresis)
                            │            │
                            ▼            ▼ AI gate (human click, or CRITICAL
                        SSE stream    triage agent   + auto-AI on + budget)
                                      (Gemini tool-loop)
                            │            │
                            ▼            ▼
                      Next.js UI ◀── PendingAction (draft + impact + rationale)
                                        │ human approves (edits inline)
                                        ▼
                                    executor: create trip / send SMS·email / invoice PDF
```

Two planes, one honesty rule: the **warehouse is real data**, the **live plane
is simulated forward** from it (the dataset ships no GPS pings or HOS — the
deck covers this). Demo faults are injected into *telemetry*; every alert you
see was detected by the watchdog, and every piece of AI output is a live
Gemini call — the trace console proves both.

## The AI gate: continuous intelligence, metered generation

Fleet Copilot separates *operational* intelligence from *generative*
intelligence. Deterministic code does everything with known rules — positions,
ETAs, HOS math, exception detection, dedupe, prioritization, money math — and
costs nothing to run continuously. The LLM is invoked only at decision
boundaries, where explanation, ambiguity resolution, or communication adds
value:

- **On demand** — every AI feature is a button: investigate an exception,
  recommend a driver, ask the fleet a question, write a coaching brief, audit
  a packet.
- **Event-gated autonomy (opt-in)** — with **auto-AI** switched on in the sim
  strip, the watchdog may summon the triage agent itself, but only for a
  CRITICAL incident, at most once an hour.
- **Budgeted per request** — every actual Gemini API call (tool-loop step,
  finalization, vision extraction) debits one unit from a daily budget
  (`AI_DAILY_REQUEST_BUDGET`, default 100), counted at the HTTP call site so
  the number means what Google's quota dashboard means. Spend persists in
  SQLite keyed by the Pacific-time quota day — Google's reset boundary — so
  neither a server restart nor a demo reset mints fresh budget. A workflow
  is admitted only if a reserve (`AI_RUN_RESERVE_REQUESTS`, default 12)
  remains, so runs are refused at the door rather than dying mid-flight.
- **Circuit-broken** — a model that returns 429 is benched for a cooldown
  instead of being retried, and one logical request may touch at most two
  models' quota buckets, so an exhausted bucket is probed once, not hammered
  by every fallback.
- **Cached incrementally** — each document extraction is persisted the
  moment it succeeds; a failed audit resumes at the document it died on, and
  re-audits spend zero vision calls.

This is what makes the design production-credible: the same architecture that
survives a free-tier Gemini key is the one that keeps LLM spend sublinear in
fleet size when the assistant runs a 500-truck operation.

## Deploy (optional, ~15 min)

**Backend on Railway**
1. Push this repo to GitHub, create a Railway project from it.
2. Railway reads `backend/railway.json` (Dockerfile build from repo root).
3. Set env vars: `GEMINI_API_KEY`, `FRONTEND_ORIGIN=https://<your-vercel-app>.vercel.app`.
4. First boot seeds the database (~1 min); `/api/health` goes green.

**Frontend on Vercel**
1. Import the repo in Vercel, set the project root to `frontend/`.
2. Set `NEXT_PUBLIC_API_URL=https://<your-railway-app>.up.railway.app`.
3. Deploy.

Notes: SQLite lives on the container filesystem — fine for a demo (a redeploy
just re-seeds a fresh world). On Railway's free tier, keep one instance.

## Repository map

```
backend/app/etl/        CSV→SQLite loader, derived stats, world builder, OSRM cache, doc PDFs
backend/app/hos/        FMCSA ledger + legal-schedule generator (unit-tested)
backend/app/sim/        clock, mover (rest stops, fault scripts), watchdog detectors
backend/app/agents/     Gemini harness (tool loop, tracing, circuit breaker, run budget) + 5 agents + executor
backend/app/routers/    REST + SSE surface
backend/tests/          34 tests
frontend/src/app/       operations · dispatch · cost · safety · billing
frontend/src/components shell, map, action cards, trace drawer, driver phone, charts
docs/                   deck source + Fleet-Copilot-Deck.pptx + GTM.md
archive/                source dataset (14 CSVs)
```
