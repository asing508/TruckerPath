/* Fleet Copilot product deck — Trucker Path visual language.
   Build: node make_deck.js  ->  Fleet-Copilot-Deck.pptx */
const pptxgen = require("pptxgenjs");

const NAVY = "10151D";
const NAVY2 = "1E2836";
const BLUE = "2489E9";
const BLUE_TINT = "EAF3FD";
const INK = "16202B";
const MUTED = "5B6B7B";
const LINE = "E2E8EE";
const OK = "15803D";
const WHITE = "FFFFFF";
const BG = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Fleet Copilot";
pres.title = "Fleet Copilot - Trucker Path PM Take-Home";

const H = { fontFace: "Arial", bold: true, color: INK };
const B = { fontFace: "Calibri", color: INK };

function kicker(slide, text, color = BLUE, x = 0.7, y = 0.55) {
  slide.addText(text.toUpperCase(), {
    x, y, w: 11.9, h: 0.35, fontFace: "Arial", bold: true,
    fontSize: 12, color, charSpacing: 3, margin: 0,
  });
}

function title(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.7, y: 0.95, w: 11.9, h: 1.15, fontSize: 32, ...H,
    ...opts, margin: 0,
  });
}

function card(slide, x, y, w, h, head, body, opts = {}) {
  slide.addShape("roundRect", {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: opts.fill || BG },
    line: { color: opts.lineColor || LINE, width: 1 },
  });
  slide.addText(head, {
    x: x + 0.22, y: y + 0.16, w: w - 0.44, h: 0.4, fontSize: 14,
    ...H, color: opts.headColor || INK, margin: 0,
  });
  slide.addText(body, {
    x: x + 0.22, y: y + 0.58, w: w - 0.44, h: h - 0.75, fontSize: 11.5,
    ...B, color: opts.bodyColor || MUTED, margin: 0, valign: "top",
    lineSpacingMultiple: 1.12,
  });
}

/* 1 — title */
let s = pres.addSlide();
s.background = { color: NAVY };
s.addText("TRUCKER PATH PM TAKE-HOME · WORKING PROTOTYPE", {
  x: 0.9, y: 1.5, w: 11, h: 0.4, fontFace: "Arial", bold: true,
  fontSize: 13, color: BLUE, charSpacing: 3, margin: 0,
});
s.addText("Fleet Copilot", {
  x: 0.9, y: 2.0, w: 11, h: 1.3, fontSize: 60, ...H, color: WHITE, margin: 0,
});
s.addText(
  "An AI-native operations assistant for 5–50 truck fleets — it watches every load, " +
  "investigates its own alarms, and hands the dispatcher decisions instead of dashboards.",
  { x: 0.9, y: 3.4, w: 9.6, h: 1.0, fontSize: 17, ...B, color: "C7D2DE", margin: 0, lineSpacingMultiple: 1.15 },
);
s.addText("All five problem areas  ·  real LLM tool-calling on live telemetry  ·  July 2026", {
  x: 0.9, y: 6.5, w: 11, h: 0.4, fontSize: 11, ...B, color: "7A8794", margin: 0,
});

/* 2 — problem */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "The problem");
title(s, "A 14-truck dispatcher runs on phone calls, spreadsheets, and adrenaline.");
const probs = [
  ["8:05 AM", "Three loads to cover. Who's closest? Who has hours left? Six phone calls to find out — and the answer changes while you dial."],
  ["11:40 AM", "A load goes dark in Arkansas. You find out at 4 PM — when the customer calls you."],
  ["3:15 PM", "Owner asks 'why is cost per mile up 9%?' The answer lives in fuel receipts, ELD logs, and a QuickBooks export that don't talk."],
  ["6:30 PM", "Chasing drivers for PODs and receipts. Invoices go out 4–5 days late, detention goes unbilled, nobody notices until quarter end."],
];
probs.forEach(([h, b], i) => {
  const x = 0.7 + (i % 2) * 6.15, y = 2.35 + Math.floor(i / 2) * 2.2;
  card(s, x, y, 5.85, 2.0, h, b, { headColor: BLUE });
});

/* 3 — insight */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "The insight");
title(s, "Fleet software has been a system of record.\nThe unlock is a system of agency.", { h: 1.6 });
const recordItems = [
  "Shows a dot moving on a map",
  "Fires an alert, then waits",
  "Human does the investigation, the math, the phone calls, the email",
  "Value ceiling: visibility",
];
const agencyItems = [
  "Detects the exception with deterministic watchdogs",
  "Agent investigates via tool calls: HOS, lane history, nearby trucks, customer SLA",
  "Proposes one concrete action with a drafted SMS / email and dollar impact",
  "Human edits inline and approves — every action stays human-gated",
];
s.addShape("roundRect", { x: 0.7, y: 2.85, w: 5.85, h: 3.6, rectRadius: 0.06, fill: { color: "F4F6F8" }, line: { color: LINE, width: 1 } });
s.addText("SYSTEM OF RECORD — STATUS QUO", { x: 0.95, y: 3.05, w: 5.3, h: 0.35, fontSize: 12.5, ...H, color: MUTED, margin: 0 });
s.addText(recordItems.map((t, i) => ({ text: t, options: { bullet: { code: "2022", indent: 12 }, breakLine: i < recordItems.length - 1, paraSpaceAfter: 8 } })), {
  x: 1.0, y: 3.5, w: 5.2, h: 2.8, fontSize: 12.5, ...B, color: MUTED, margin: 0, valign: "top" });
s.addShape("roundRect", { x: 6.8, y: 2.85, w: 5.85, h: 3.6, rectRadius: 0.06, fill: { color: BLUE_TINT }, line: { color: BLUE, width: 1.5 } });
s.addText("SYSTEM OF AGENCY — FLEET COPILOT", { x: 7.05, y: 3.05, w: 5.3, h: 0.35, fontSize: 12.5, ...H, color: BLUE, margin: 0 });
s.addText(agencyItems.map((t, i) => ({ text: t, options: { bullet: { code: "2022", indent: 12 }, breakLine: i < agencyItems.length - 1, paraSpaceAfter: 8 } })), {
  x: 7.1, y: 3.5, w: 5.3, h: 2.8, fontSize: 12.5, ...B, color: INK, margin: 0, valign: "top" });
s.addText("No chat sidebar. The dispatcher's unit of work is a decision, not a conversation.", {
  x: 0.7, y: 6.7, w: 11.9, h: 0.4, fontSize: 13, italic: true, ...B, color: MUTED, margin: 0 });

/* 4 — product map */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "The prototype");
title(s, "Five surfaces. Five pain points. Nothing else.");
const mods = [
  ["Operations — Proactive Alerts", "Live map + watchdog: dark loads, route deviation, ETA slip, dock detention, HOS risk. HIGH/CRITICAL exceptions auto-dispatch the triage agent; its proposal lands in the Action Queue."],
  ["Dispatch — Smart Dispatch", "Deterministic candidate scoring (deadhead, HOS slack, lane familiarity, on-time, safety) + agent recommendation memo + editable driver SMS."],
  ["Cost — Cost Intelligence", "CPM decomposition over 85k historical trips, margin-per-mile trend, and 'Ask your fleet': English → guarded SQL → answer + chart."],
  ["Safety — Compliance", "FMCSA HOS ledger (11h/14h/70h-8d, 30-min break), fatigue features, PM/inspection tracking, agent-written coaching briefs."],
  ["Billing — Document Automation", "Gemini Vision reads rate cons, BOLs, PODs, receipts → deterministic reconciler diffs them against the system of record and GPS dwell → invoice drafted, human approves."],
  ["Everywhere — Trust primitives", "Agent Trace console shows every tool call live. Every draft is inline-editable. Every execution requires a click. Nothing is scripted."],
];
mods.forEach(([h, b], i) => {
  const x = 0.7 + (i % 3) * 4.1, y = 2.3 + Math.floor(i / 3) * 2.35;
  card(s, x, y, 3.9, 2.15, h, b, i === 5 ? { fill: BLUE_TINT, lineColor: BLUE, headColor: BLUE } : { headColor: INK });
});

/* 5 — AI design */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "How the AI is built");
title(s, "The model reasons. The code computes. The human decides.");
const ai = [
  ["Real tool-calling loops", "Gemini 3.5 Flash with 10 read-only fleet tools (get_trip_state, get_candidate_drivers, find_nearby_drivers…). Every step is persisted and streamed to the trace console over SSE."],
  ["Guardrails by construction", "NL→SQL runs on a read-only SQLite connection with an authorizer: SELECT-only, denylisted tables, row caps, VM-step budget. Money math is never delegated to the model — the reconciler and HOS ledger are code."],
  ["Human in the loop", "Agents end at a PendingAction: title, rationale, dollar impact, editable drafts. Approve executes; dismiss archives. The model never sends anything itself."],
];
ai.forEach(([h, b], i) => card(s, 0.7 + i * 4.1, 2.3, 3.9, 2.5, h, b));
s.addShape("roundRect", { x: 0.7, y: 5.1, w: 11.9, h: 1.6, rectRadius: 0.06, fill: { color: NAVY }, line: { color: NAVY, width: 1 } });
s.addText(
  "exception #14 DETENTION → agent: get_exception → get_trip_state → get_detention_math → get_customer_profile\n" +
  "→ proposal: notify customer AP — $142.50 detention documented via POD 19:05→22:59, GPS dwell corroborates   [Edit] [Approve & execute]",
  { x: 1.0, y: 5.3, w: 11.3, h: 1.2, fontFace: "Courier New", fontSize: 11, color: "9FD1FF", margin: 0, valign: "middle", lineSpacingMultiple: 1.3 },
);

/* 6 — data foundation */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "Data foundation");
title(s, "Real operations data. Honestly simulated telemetry.");
const data = [
  ["Historical warehouse — real", "Public 3-year Class 8 carrier dataset: 85,410 loads/trips, 196k fuel purchases, 170k delivery events with detention minutes, maintenance + incident history. Powers every analytic and every scorer feature."],
  ["Live plane — simulated forward", "The dataset has no GPS pings or HOS, so the sim supplies them: positions replayed along real OSRM road geometry, duty ledgers ticked by a deterministic engine (seeded, resettable)."],
  ["Faults injected, detection earned", "Demo incidents (GPS blackout, slowdown, off-route drift, dock dwell) are scripted into telemetry. The watchdog must detect them from the data — alerts are never hardcoded."],
  ["The LLM is never mocked", "Every recommendation, triage, brief, extraction, and answer is a live Gemini call — visible, step by step, in the trace console."],
];
data.forEach(([h, b], i) => {
  const x = 0.7 + (i % 2) * 6.15, y = 2.35 + Math.floor(i / 2) * 2.25;
  card(s, x, y, 5.85, 2.05, h, b);
});

/* 7 — tradeoffs */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "What I traded off");
title(s, "Cut scope, kept honesty.");
const cuts = [
  ["No auth, no multi-tenant", "One fleet, one dispatcher persona. The interesting risk was the agentic loop, not login forms."],
  ["Simulated world, not integrations", "Samsara/Motive/TP ELD integration is a connector problem with known shape. The time went into what the system does after the data arrives."],
  ["Reroute/relay stop at the proposal", "Approving a reroute logs and notifies but doesn't re-optimize the whole board — honest about where the prototype ends."],
  ["Free-tier LLM quotas", "Engineered around, not hidden: model cascade across quota buckets, paced calls, serialized auto-triage. A paid key simply makes it faster."],
];
cuts.forEach(([h, b], i) => {
  const x = 0.7 + (i % 2) * 6.15, y = 2.35 + Math.floor(i / 2) * 2.1;
  card(s, x, y, 5.85, 1.9, h, b);
});

/* 8 — metrics */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "How I'd measure success");
title(s, "One activation metric, three P&L metrics, two trust metrics.");
s.addShape("roundRect", { x: 0.7, y: 2.3, w: 11.9, h: 1.25, rectRadius: 0.06, fill: { color: BLUE_TINT }, line: { color: BLUE, width: 1.5 } });
s.addText("Activation: time-to-first-approved-action", { x: 0.95, y: 2.45, w: 11.4, h: 0.4, fontSize: 15, ...H, color: BLUE, margin: 0 });
s.addText("The product is working the first time a dispatcher approves an agent proposal. Target: under 15 minutes from install.",
  { x: 0.95, y: 2.9, w: 11.4, h: 0.5, fontSize: 12, ...B, color: INK, margin: 0 });
const mets = [
  ["Deadhead % of miles", "Better assignments → fewer empty miles. Baseline from fleet history; target −15% in 90 days."],
  ["Days-to-invoice", "Audit-to-invoice in minutes, not days. Target: 4.6 → <1.0 average; detention recovery per 100 loads as the kicker."],
  ["Exceptions caught first", "Share of late/dark loads the system flagged before the customer called. The 'never go dark again' promise, quantified."],
];
mets.forEach(([h, b], i) => card(s, 0.7 + i * 4.1, 3.85, 3.9, 1.7, h, b));
const trust = [
  ["Approval rate", "Approved / proposed. Below ~60% the agent is noisy; above ~95% it's too timid to be useful."],
  ["Edit-before-approve rate", "How often dispatchers fix drafts. A falling edit rate is growing trust — the leading indicator for expanding autonomy."],
];
trust.forEach(([h, b], i) => card(s, 0.7 + i * 6.15, 5.75, 5.85, 1.45, h, b));

/* 9 — GTM */
s = pres.addSlide();
s.background = { color: BG };
kicker(s, "Go-to-market");
title(s, "Trucker Path already owns the funnel.");
const gtm = [
  ["ICP", "5–50 truck for-hire fleets — ~50k US carriers. One dispatcher wearing four hats; no TMS, or a TMS they hate. Willingness to pay tracks saved hours and recovered detention, both measurable in-product."],
  ["Wedge & pricing", "Land with Billing Audit (fast, provable ROI: found money on real paperwork) at $30–40/truck/mo. Expand to full Copilot at $75–90/truck/mo once trust metrics clear. A 30-truck fleet ≈ $32k ACV."],
  ["Acquisition", "1M+ drivers already run Trucker Path in the cab: driver-side doc scans seed the fleet product. Upsell path from the ELD/Command install base — CAC near zero versus cold outbound."],
];
gtm.forEach(([h, b], i) => card(s, 0.7 + i * 4.1, 2.3, 3.9, 3.0, h, b));
s.addText("Sequencing: billing wedge → dispatch + alerts once telemetry is native → cost & safety complete the retention moat.", {
  x: 0.7, y: 5.7, w: 11.9, h: 0.45, fontSize: 13, italic: true, ...B, color: MUTED, margin: 0 });

/* 10 — roadmap / close */
s = pres.addSlide();
s.background = { color: NAVY };
s.addText("IF THIS SHIPS", { x: 0.9, y: 0.8, w: 11, h: 0.4, fontFace: "Arial", bold: true, fontSize: 12, color: BLUE, charSpacing: 3, margin: 0 });
s.addText("Next 3 moves, in order.", { x: 0.9, y: 1.25, w: 11, h: 0.9, fontSize: 34, ...H, color: WHITE, margin: 0 });
const road = [
  ["1 · Real telemetry", "Swap the sim for TP ELD / Command streams — the watchdog and agents don't change, only the ingest does. That's the point of the two-plane design."],
  ["2 · Autonomy ladder", "Per-action-type trust levels: propose → auto-execute-with-undo → autonomous within budget. Gated by each fleet's own approval and edit history."],
  ["3 · Multi-load optimization", "From one-load recommendations to board-level assignment — deadhead-aware matching across tomorrow's loads. The ripple-effect problem."],
];
road.forEach(([h, b], i) => {
  const y = 2.5 + i * 1.25;
  s.addText(h, { x: 0.9, y, w: 3.4, h: 0.5, fontSize: 17, ...H, color: BLUE, margin: 0 });
  s.addText(b, { x: 4.4, y: y + 0.02, w: 8.0, h: 1.1, fontSize: 12.5, ...B, color: "C7D2DE", margin: 0, valign: "top", lineSpacingMultiple: 1.15 });
});
s.addText("Thanks — the prototype is live; every agent decision you saw was a real model call.", {
  x: 0.9, y: 6.6, w: 11, h: 0.4, fontSize: 11.5, ...B, color: "7A8794", margin: 0 });

pres.writeFile({ fileName: "Fleet-Copilot-Deck.pptx" }).then(() => console.log("written"));
