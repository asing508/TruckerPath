# Fleet Copilot — Trucker Path PM Take-Home

Fleet Copilot is an **AI-native fleet operations assistant** for small and
midsize carriers operating 5–50 trucks. It connects live operations, smart
dispatch, cost intelligence, safety and compliance, and billing automation in
one working product.

Deterministic services continuously monitor the fleet and perform legal or
financial calculations. Gemini is invoked only at valuable decision points to
investigate, explain, recommend, or draft. Every external action remains
editable and human-approved.

> Product presentation: [`docs/Fleet-Copilot-Deck.pptx`](docs/Fleet-Copilot-Deck.pptx)

## Reviewer quick start

The local setup is the canonical way to review the complete product and does
not require access to the author's Railway or Vercel accounts.

### Prerequisites

| Requirement | Version | Install |
|---|---:|---|
| Git | Any recent version | [git-scm.com/downloads](https://git-scm.com/downloads) |
| Python | 3.12 or newer | [python.org/downloads](https://www.python.org/downloads/) |
| `uv` | Any recent version | [Official installation guide](https://docs.astral.sh/uv/getting-started/installation/) |
| Node.js | 20 or newer LTS | [nodejs.org/download](https://nodejs.org/en/download) |

A Gemini API key is **optional for launching and exploring the deterministic
product**. It is required only when clicking an AI action such as **Send agent
to investigate**, **Ask agent to recommend**, **Ask**, **Generate brief**, or
**Run agent audit**. A key can be created in
[Google AI Studio](https://aistudio.google.com/apikey); keep it only in
`backend/.env` and never commit it.

### 1. Clone the repository

```bash
git clone https://github.com/asing508/TruckerPath.git
cd TruckerPath
```

### 2. Start the backend

Open a terminal in the repository root.

**Windows PowerShell**

```powershell
Set-Location backend
Copy-Item .env.example .env
notepad .env
uv sync --frozen
uv run uvicorn app.main:app --port 8000
```

**macOS or Linux**

```bash
cd backend
cp .env.example .env
${EDITOR:-nano} .env
uv sync --frozen
uv run uvicorn app.main:app --port 8000
```

For the full AI experience, replace the placeholder in `backend/.env`:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key
FRONTEND_ORIGIN=http://localhost:3000
```

If no key is available, either leave `GEMINI_API_KEY` empty or skip creating
`backend/.env`; the simulator, watchdogs, maps, dashboards, scoring, HOS,
billing reconciliation, and generated documents still work. AI buttons will
report that the provider is unavailable.

On the first boot, the backend creates `backend/data/fleet.db`, loads all 14
source CSVs, builds the 14-truck live world, and generates freight-document
fixtures. This can take approximately one minute. Wait for the terminal to
show:

```text
INFO main: simulation loop started
```

Leave this terminal running.

### 3. Start the frontend

Open a **second terminal** in the repository root.

**Windows PowerShell**

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

**macOS or Linux**

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Leave this terminal running, then open:

- **Application:** [http://localhost:3000](http://localhost:3000)
- **Backend health:** [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Interactive API docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

The app is ready when the blue simulation strip says **telemetry stream
connected**.

### 4. First five minutes in the product

1. On **Operations**, click two trip rows and watch the corresponding road
   route highlight on the map.
2. Use **play/pause** and select `×120` or `×300` to surface simulated
   exceptions quickly. Dark-load, HOS, route-deviation, detention, ETA, and
   maintenance alerts are detected without an LLM call.
3. Keep **auto-AI off** for intentional, quota-safe use. Open **Agent trace**
   before clicking **Send agent to investigate** to watch the real read-only
   tool calls and results.
4. Review the resulting Action Queue proposal, edit its draft, click
   **Approve & execute**, and open **Driver phone** to see an approved SMS.
5. Visit **Dispatch**, **Cost**, **Safety**, and **Billing** using the walkthrough
   below. Keep returning to **Agent trace** whenever an AI action runs.

## Feature walkthrough

### Operations — proactive exception management

- Live map and trip table share the same selected-trip state.
- The simulated world advances GPS, ETA, dwell, HOS, and equipment state over
  road-following route geometry.
- Deterministic watchdogs detect dark loads, route deviation, ETA slip,
  detention, HOS pressure, and maintenance/compliance deadlines.
- **Send agent to investigate** gathers trip, driver, telemetry, customer, and
  similar-incident evidence through read-only tools.
- The result is an editable SMS, customer email, or monitoring proposal in the
  Action Queue—not an automatic external action.
- **Driver phone** and the Operations Feed show approved execution.

### Dispatch — deterministic ranking plus agent judgment

1. Select an unassigned load.
2. Compare candidates using deadhead, pickup arrival, HOS slack, lane trips,
   on-time history, safety, score, and hard feasibility flags.
3. Click **Ask agent to recommend** with **Agent trace** open.
4. Inspect the rationale and editable assignment SMS.
5. Approve the proposal; the load becomes a live trip in Operations.

The candidate score is deterministic and inspectable. Gemini reasons on top
of the score and constraints; it does not replace them.

### Cost — natural-language analysis over three years

- Review cost/mile, revenue/mile, on-time performance, detention, deadhead,
  fuel, maintenance, and 36-month margin trends.
- Segment fuel cost per mile by lane, driver, or customer.
- In **Ask your fleet**, try:

```text
Which customers cause the most detention over 2 hours?
```

The analyst inspects an approved schema, writes read-only SQL, and explains
only the returned rows. The SQLite authorizer blocks writes and sensitive
tables, limits result size, and interrupts long-running queries. The generated
SQL remains visible below the result.

### Safety — risk evidence into a coaching brief

1. Select a driver from the risk watchlist.
2. Review HOS pressure, 14-hour window, cycle use, night driving, violations,
   and incident history.
3. Open **Agent trace** and click **Generate brief**.
4. Review the evidence-grounded assessment and five-minute coaching points.
5. Inspect the equipment-compliance list for preventive-maintenance and DOT
   inspection deadlines.

Risk scores and compliance clocks are deterministic. Gemini summarizes the
evidence for a manager; it does not automate discipline or employment action.

### Billing — document audit and revenue recovery

1. Open a delivered packet. For the clearest discrepancy example, choose
   `L-2607-104 · First Industries` after a fresh reset.
2. Open the Rate Confirmation and Proof of Delivery PDFs to inspect the source
   evidence.
3. Open **Agent trace**, then click **Run agent audit**.
4. Gemini Vision extracts document fields. Deterministic reconciliation checks
   them against the system of record and calculates financial discrepancies.
5. Review the audit memo and editable invoice email, then approve the invoice
   to generate its PDF.

The selected fixture contains 234 minutes of dwell, 120 free minutes, and 114
billable minutes at $75/hour, yielding **$142.50 in unclaimed detention**. The
model extracts and explains the evidence; code calculates the amount.

The prototype generates packet PDFs during seeding and does not include an
upload connector. A production version would ingest driver scans, email
attachments, and TMS/ELD document feeds.

## AI usage and free-tier safety

Fleet Copilot separates continuous operational intelligence from metered
generation:

- **Auto-AI is off by default.** Monitoring and deterministic detection still
  run continuously.
- **Manual by default.** Every AI workflow begins with an explicit button.
- **Strict auto gate.** If auto-AI is enabled, only a CRITICAL incident can
  trigger triage, no more than once per hour.
- **Request-level budget.** Every actual Gemini HTTP request is counted in a
  Pacific-day budget (`AI_DAILY_REQUEST_BUDGET`, default `100`).
- **Run reserve.** A workflow starts only when enough budget remains to finish
  (`AI_RUN_RESERVE_REQUESTS`, default `12`).
- **Circuit breaker.** A model returning `429` enters a 15-minute cooldown;
  fallback is bounded so an exhausted quota is not hammered repeatedly.
- **Incremental document cache.** Successful Vision extraction is saved per
  document and reused on retries or re-audits.

One visible agent workflow can make several Gemini requests because the agent
may call tools and then produce a structured final response. The blue strip
shows **actual Gemini requests used / configured daily cap**. For a free-tier
review, leave auto-AI off and invoke only the workflows being evaluated.

Model availability and free-tier limits vary by Google account. The backend
automatically selects the first available configured model, or a reviewer may
pin a model listed for their key:

```dotenv
GEMINI_MODEL=gemini-3.1-flash-lite
```

Changing or creating another API key in the same Google project generally
does not create a new project quota. If quota is exhausted, wait for the
provider reset instead of repeatedly retrying; the deterministic product will
continue to run.

## Resetting the demo

There are two different resets:

- **Reset the live scenario:** click **reset demo** in the blue strip. This
  restores trips, loads, incidents, packets, and actions to their seeded demo
  state.
- **Rebuild all local data:** stop the backend and run:

```bash
cd backend
uv run python -m app.etl.seed
```

The in-app reset intentionally **does not erase the persisted daily Gemini
request counter**. A full database rebuild recreates the local safety counter,
but it does not reset Google's provider-side quota; do not use reseeding as a
quota workaround. Restart the backend after a manual reseed.

## Troubleshooting

### The backend appears to keep running

That is expected. Uvicorn is the long-running API server and also owns the
simulation loop. Leave its terminal open while using the app. Stop it with
`Ctrl+C` after the review.

### First backend boot looks slow

The first boot loads approximately 550,000 historical rows and generates the
demo document packets. Wait for `simulation loop started`. Subsequent boots
reuse `backend/data/fleet.db` and are much faster.

### The UI says telemetry is disconnected

1. Open [http://localhost:8000/api/health](http://localhost:8000/api/health).
2. Confirm the backend terminal is still running on port `8000`.
3. Confirm `frontend/.env.local` contains:

   ```dotenv
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Restart `npm run dev` after changing a frontend environment variable.

### Port 8000 or 3000 is already in use

Stop the older backend/frontend process with `Ctrl+C`. Keeping the documented
ports is easiest because the local CORS and frontend API settings already
match them.

### An AI action fails immediately

- Confirm `GEMINI_API_KEY` contains a valid Google AI Studio key, with no
  quotes or trailing spaces.
- Restart the backend after editing `backend/.env`.
- Check the blue request counter and the backend terminal for `429` or quota
  messages.
- Do not repeatedly click the action; wait for the cooldown or daily reset.
- Open **Agent trace** to inspect the failed run without losing the rest of the
  application state.

### Cost or Safety repeatedly rerenders

Use the latest `main` branch and restart both development servers. The external
store snapshot is cached in the current implementation, preventing React's
`getSnapshot` / maximum-update-depth loop.

### Reset did not reduce AI usage

This is intentional. The request budget persists in SQLite for the provider's
Pacific-time quota day so a browser refresh, server restart, or demo reset
cannot mint additional usage.

## Product architecture

```text
archive/*.csv ──ETL──▶ SQLite warehouse
                          │
                          ├── analytics API ──▶ Cost dashboards
                          ├── guarded SQL ────▶ Ask Your Fleet
                          └── fleet carve ────▶ 14-truck live world
                                                   │
                                  SimEngine ───────┤
                                  GPS + HOS        ├──▶ deterministic watchdogs
                                  injected faults │               │
                                                   ▼               ▼
                                                SSE UI       event-gated agent
                                                                  │
                                                        read-only tool calls
                                                                  │
                                                                  ▼
                                                         PendingAction
                                                                  │
                                                      edit + human approval
                                                                  │
                                                                  ▼
                                             trip / SMS / email / invoice PDF
```

The product uses three explicitly labeled data layers:

1. **Historical warehouse:** 14 supplied CSVs, approximately 550,000 rows,
   85,410 loads/trips, 196,442 fuel purchases, and 170,820 delivery events.
2. **Simulated live plane:** 14 trucks around Dallas, Houston, and Oklahoma
   City with road geometry, HOS clocks, dwell, ETA, and injected telemetry
   faults. The source dataset contains no production GPS stream.
3. **Generated freight packets:** real PDFs created for the demo with
   controlled discrepancies. Gemini reads the documents; hidden fixture truth
   is not passed to the model.

## AI responsibility boundaries

| Area | Deterministic software owns | Gemini owns | Human owns |
|---|---|---|---|
| Operations | Telemetry, HOS, ETA, dwell, detection, dedupe | Evidence synthesis, likely cause, draft action | Edit, approve, dismiss |
| Dispatch | Candidate eligibility, scores, flags, pickup/HOS feasibility | Tradeoff explanation, recommendation, assignment draft | Final assignment |
| Cost | Warehouse, permissions, SQL execution, returned rows | Natural language to SQL, explanation, chart intent | Interpretation and business decision |
| Safety | Risk score, HOS/compliance clocks, incident facts | Coaching summary and talking points | Coaching and personnel judgment |
| Billing | Document storage, reconciliation, detention and invoice math | Vision extraction, memo and email draft | Audit approval and invoice send |

Four trust rules apply everywhere:

1. The model receives read-only tools and cannot directly mutate fleet state.
2. Legal and financial calculations remain in deterministic code.
3. Every tool call and result is persisted in **Agent trace**.
4. External actions are editable and require human approval.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS v4, shadcn/ui, MapLibre GL, TanStack Query, Recharts |
| Backend | FastAPI, SQLModel, SQLite WAL, server-sent events |
| AI | Google GenAI SDK, Gemini function calling, structured outputs, Gemini Vision, persisted trace, request budget, circuit breaker |
| Data | Three-year Class 8 carrier dataset plus simulated live GPS/HOS plane and generated freight documents |

## Tests and verification

Run backend tests:

```bash
cd backend
uv run python -m pytest tests/ -q
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

The backend suite covers the AI request gate, event flow, FMCSA-style HOS
ledger, legal schedule generation, detector geometry, billing reconciliation,
guarded SQL, and simulation smoke behavior.

## Optional cloud deployment

### Backend on Railway

1. Import the GitHub repository into Railway.
2. Keep the Railway service root at the repository root. Railway reads the
   root [`railway.json`](railway.json) and builds `backend/Dockerfile`.
3. Set `GEMINI_API_KEY` and
   `FRONTEND_ORIGIN=https://<your-vercel-domain>`.
4. Deploy and confirm `https://<your-railway-domain>/api/health` returns a
   successful JSON health response.

### Frontend on Vercel

1. Import the same repository into Vercel.
2. Set the project root directory to `frontend`.
3. Set
   `NEXT_PUBLIC_API_URL=https://<your-railway-domain>`.
4. Deploy, then update Railway's `FRONTEND_ORIGIN` to the final Vercel origin.

SQLite lives on the container filesystem, which is acceptable for a temporary
product demo and reseeds after an ephemeral redeploy. A production deployment
should use persistent Postgres, durable background jobs, tenant isolation,
role-based access, backups, and managed outbound-message providers.

## Repository map

```text
archive/                  Source dataset: 14 CSVs
backend/app/etl/          Warehouse loader, world builder, route cache, document generation
backend/app/hos/          HOS ledger and legal schedule generator
backend/app/sim/          Clock, mover, fault injection, deterministic watchdogs
backend/app/agents/       Gemini harness, five agents, trace, budget, executor
backend/app/routers/      REST and SSE API surface
backend/tests/            Backend test suite
frontend/src/app/         Operations, Dispatch, Cost, Safety, Billing pages
frontend/src/components/  Shell, map, action queue, trace, phone, charts
docs/                     Product deck source, PPTX, and GTM notes
```
