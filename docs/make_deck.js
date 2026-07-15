/* Fleet Copilot interview deck for the Trucker Path PM take-home.
   Build from this directory: node make_deck.js */
const path = require("path");
const pptxgen = require("pptxgenjs");

const C = {
  navy: "101722", navy2: "1C2938", blue: "3C91F3", blue2: "DCEEFF",
  cyan: "59C8E8", green: "39B980", green2: "E5F7EF", amber: "ECA53A",
  amber2: "FFF4DB", red: "D95B5B", red2: "FCEAEA", purple: "7769D4",
  purple2: "EEEAFE", ink: "172231", muted: "5C6C7D", faint: "8A98A7",
  line: "DDE4EB", bg: "F5F7FA", white: "FFFFFF",
};
const FONT_H = "Aptos Display";
const FONT_B = "Aptos";

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "Aditya";
pptx.company = "Trucker Path";
pptx.subject = "AI-native fleet operations assistant for small fleets";
pptx.title = "Fleet Copilot — Trucker Path PM Take-Home";
pptx.lang = "en-US";
pptx.theme = { headFontFace: FONT_H, bodyFontFace: FONT_B, lang: "en-US" };

let page = 0;

function tx(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h, margin: 0, fontFace: FONT_B, fontSize: 12,
    color: C.ink, breakLine: false, ...opts,
  });
}

function shape(slide, type, x, y, w, h, fill, line = fill, radius = false) {
  slide.addShape(radius ? "roundRect" : type, {
    x, y, w, h, rectRadius: radius ? 0.06 : undefined,
    fill: { color: fill }, line: { color: line, width: 1 },
  });
}

function newSlide(bg = C.bg, section = "") {
  page += 1;
  const slide = pptx.addSlide();
  slide.background = { color: bg };
  if (page > 1) {
    shape(slide, "rect", 0, 0, 13.333, 0.08, C.blue, C.blue);
    tx(slide, "FLEET COPILOT", 0.7, 7.12, 2.2, 0.18, {
      fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint, charSpacing: 1.8,
    });
    tx(slide, section.toUpperCase(), 4.15, 7.12, 5.05, 0.18, {
      fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint,
      align: "center", charSpacing: 1.2,
    });
    tx(slide, String(page).padStart(2, "0"), 11.75, 7.1, 0.85, 0.2, {
      fontFace: FONT_H, bold: true, fontSize: 9, color: C.faint, align: "right",
    });
  }
  return slide;
}

function heading(slide, kicker, headline, sub = "", opts = {}) {
  tx(slide, kicker.toUpperCase(), 0.7, 0.38, 11.9, 0.24, {
    fontFace: FONT_H, bold: true, fontSize: 10.5, color: C.blue, charSpacing: 2.2,
  });
  tx(slide, headline, 0.7, 0.78, 11.9, opts.titleH || 0.75, {
    fontFace: FONT_H, bold: true, fontSize: opts.titleSize || 27,
    color: C.ink, valign: "mid",
  });
  if (sub) tx(slide, sub, 0.7, opts.subY || 1.56, 11.9, opts.subH || 0.36, {
    fontSize: 12.2, color: C.muted,
  });
}

function pill(slide, label, x, y, w, fill, color, line = fill, opts = {}) {
  shape(slide, "rect", x, y, w, opts.h || 0.36, fill, line, true);
  tx(slide, label, x + 0.08, y + 0.06, w - 0.16, (opts.h || 0.36) - 0.1, {
    fontFace: FONT_H, bold: true, fontSize: opts.fontSize || 9.5,
    color, align: "center", valign: "mid", charSpacing: opts.charSpacing || 0.2,
  });
}

function card(slide, x, y, w, h, title, body, opts = {}) {
  shape(slide, "rect", x, y, w, h, opts.fill || C.white, opts.line || C.line, true);
  if (opts.accent) shape(slide, "rect", x, y, 0.07, h, opts.accent, opts.accent);
  tx(slide, title, x + 0.22, y + 0.17, w - 0.44, opts.titleH || 0.36, {
    fontFace: FONT_H, bold: true, fontSize: opts.titleSize || 13,
    color: opts.titleColor || C.ink,
  });
  tx(slide, body, x + 0.22, y + (opts.bodyY || 0.62), w - 0.44,
    h - (opts.bodyY || 0.62) - 0.18, {
      fontSize: opts.bodySize || 11.1, color: opts.bodyColor || C.muted,
      valign: "top", lineSpacingMultiple: 1.05,
    });
}

function dotList(slide, items, x, y, w, opts = {}) {
  const gap = opts.gap || 0.5;
  items.forEach((item, i) => {
    shape(slide, "ellipse", x, y + i * gap + 0.11, 0.09, 0.09,
      opts.dot || C.blue, opts.dot || C.blue);
    tx(slide, item, x + 0.18, y + i * gap, w - 0.18, gap - 0.02, {
      fontSize: opts.fontSize || 11.2, color: opts.color || C.ink, valign: "mid",
    });
  });
}

function numberBadge(slide, number, x, y, color = C.blue) {
  shape(slide, "ellipse", x, y, 0.34, 0.34, color, color);
  tx(slide, String(number), x, y + 0.04, 0.34, 0.22, {
    fontFace: FONT_H, bold: true, fontSize: 10, color: C.white,
    align: "center", valign: "mid",
  });
}

// 1 — Cover
let s = newSlide(C.navy, "Cover");
shape(s, "rect", 0, 0, 13.333, 0.1, C.blue, C.blue);
tx(s, "TRUCKER PATH", 0.78, 0.48, 2.2, 0.28, {
  fontFace: FONT_H, bold: true, fontSize: 13, color: C.white, charSpacing: 2,
});
shape(s, "line", 2.96, 0.44, 0, 0.34, C.navy, C.faint);
tx(s, "FLEET COPILOT", 3.22, 0.48, 2.6, 0.28, {
  fontFace: FONT_H, bold: true, fontSize: 12, color: C.blue, charSpacing: 2.4,
});
tx(s, "AI-NATIVE PRODUCT MANAGEMENT INTERNSHIP", 8.1, 0.49, 4.45, 0.25, {
  fontFace: FONT_H, bold: true, fontSize: 9.5, color: "93A2B4",
  align: "right", charSpacing: 1.4,
});
tx(s, "Fleet Copilot", 0.78, 1.42, 11.7, 0.95, {
  fontFace: FONT_H, bold: true, fontSize: 47, color: C.white,
});
tx(s, "The dispatcher's exception-to-action workspace.", 0.8, 2.5, 10.7, 0.5, {
  fontFace: FONT_H, bold: true, fontSize: 23, color: C.blue,
});
tx(s,
  "It watches every load, investigates what changed, proposes the next best action, and waits for the dispatcher to approve it.",
  0.8, 3.18, 9.9, 0.78, { fontSize: 16, color: "CAD5E1", lineSpacingMultiple: 1.1 });
pill(s, "5–50 TRUCK FLEETS", 0.8, 4.32, 2.05, C.navy2, "BFD0E0", "405064");
pill(s, "WORKING PROTOTYPE", 3.0, 4.32, 2.12, C.navy2, "BFD0E0", "405064");
pill(s, "ALL 5 PROBLEM AREAS", 5.27, 4.32, 2.35, C.blue, C.white, C.blue);
const coverFlow = ["WATCH", "DETECT", "INVESTIGATE", "PROPOSE", "APPROVE", "EXECUTE"];
coverFlow.forEach((label, i) => {
  const x = 0.8 + i * 1.96;
  shape(s, "rect", x, 5.35, 1.62, 0.58, i === 4 ? C.green : C.navy2,
    i === 4 ? C.green : "405064", true);
  tx(s, label, x, 5.54, 1.62, 0.18, {
    fontFace: FONT_H, bold: true, fontSize: 9.3,
    color: i === 4 ? C.navy : "D5DFE9", align: "center", charSpacing: 1,
  });
  if (i < coverFlow.length - 1) tx(s, "›", x + 1.65, 5.42, 0.28, 0.34, {
    fontFace: FONT_H, bold: true, fontSize: 21, color: C.blue, align: "center",
  });
});
tx(s, "Aditya  ·  Trucker Path PM Take-Home  ·  July 2026", 0.8, 6.72, 6.3, 0.23, {
  fontSize: 10.5, color: "7F90A2",
});
tx(s, "Live Gemini calls  ·  human-approved execution", 7.3, 6.72, 5.1, 0.23, {
  fontSize: 10.5, color: "7F90A2", align: "right",
});

// 2 — Brief and product decision
s = newSlide(C.bg, "From brief to product");
heading(s, "The opportunity",
  "The brief asked for at least two problems. I built one connected workflow across all five.",
  "Because the same load, driver, customer, and document facts should not live in five separate tools.",
  { titleSize: 24.5, titleH: 0.9, subY: 1.67 });
shape(s, "rect", 0.7, 2.1, 3.75, 4.55, C.navy, C.navy, true);
tx(s, "PRIMARY USER", 0.98, 2.38, 2.2, 0.22, {
  fontFace: FONT_H, bold: true, fontSize: 10, color: C.blue, charSpacing: 1.8,
});
tx(s, "One dispatcher\nwearing five hats", 0.98, 2.86, 2.9, 0.9, {
  fontFace: FONT_H, bold: true, fontSize: 25, color: C.white,
});
tx(s, "Owner mindset. Dispatcher workload. No procurement team.",
  0.98, 3.96, 2.95, 0.65, { fontSize: 13, color: "BBC9D7" });
shape(s, "line", 0.98, 4.82, 2.85, 0, C.navy, "415165");
tx(s, "5–50", 0.98, 5.13, 1.15, 0.52, {
  fontFace: FONT_H, bold: true, fontSize: 30, color: C.green,
});
tx(s, "trucks in the target fleet", 2.05, 5.23, 1.5, 0.4, {
  fontSize: 11.2, color: "BBC9D7",
});
tx(s, "The product must reduce calls, late surprises, and cash-flow drag—without taking control away.",
  0.98, 5.86, 2.95, 0.55, { fontSize: 11.5, color: "BBC9D7" });

const pains = [
  ["COVER", "Smart Dispatch", "Choose a feasible driver without a phone tree."],
  ["WATCH", "Proactive Alerts", "Catch dark, late, off-route, detention, and HOS risk early."],
  ["UNDERSTAND", "Cost Intelligence", "Explain where margin and cost per mile are moving."],
  ["PROTECT", "Safety & Compliance", "Intervene before a violation, inspection miss, or fatigue event."],
  ["COLLECT", "Billing Automation", "Turn complete paperwork into an accurate invoice faster."],
];
pains.forEach(([tag, name, text], i) => {
  const y = 2.1 + i * 0.89;
  shape(s, "rect", 4.72, y, 7.88, 0.76, i % 2 ? "F9FAFC" : C.white, C.line, true);
  pill(s, tag, 4.94, y + 0.2, 1.25, i === 4 ? C.green2 : C.blue2,
    i === 4 ? C.green : C.blue, i === 4 ? C.green2 : C.blue2,
    { h: 0.3, fontSize: 8.4 });
  tx(s, name, 6.42, y + 0.15, 2.3, 0.25, {
    fontFace: FONT_H, bold: true, fontSize: 12.2,
  });
  tx(s, text, 8.7, y + 0.14, 3.62, 0.43, {
    fontSize: 10.8, color: C.muted, valign: "mid",
  });
});
shape(s, "rect", 4.72, 6.03, 7.88, 0.62, C.blue2, C.blue, true);
tx(s, "PRODUCT DECISION", 4.94, 6.23, 1.6, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.blue, charSpacing: 1.2,
});
tx(s, "Connect the jobs around the load lifecycle—not five isolated AI demos.",
  6.52, 6.18, 5.78, 0.27, { fontFace: FONT_H, bold: true, fontSize: 11.4 });

// 3 — Event-driven workflow
s = newSlide(C.bg, "User workflow");
heading(s, "How it works", "Live events become approved work—not another wall of alerts.",
  "A single event-driven loop connects the simulator, watchdogs, agents, action queue, and execution state.");
const flow = [
  ["INGEST", "GPS, HOS, load, customer, documents"],
  ["DETECT", "Rules identify a meaningful exception"],
  ["INVESTIGATE", "Agent calls read-only fleet tools"],
  ["PROPOSE", "Evidence, impact, and editable draft"],
  ["APPROVE", "Dispatcher edits, approves, or dismisses"],
  ["EXECUTE", "Action is logged and product state updates"],
];
flow.forEach(([name, body], i) => {
  const x = 0.7 + i * 2.0;
  const active = i === 4;
  shape(s, "rect", x, 2.35, 1.72, 2.13, active ? C.green2 : C.white,
    active ? C.green : C.line, true);
  numberBadge(s, i + 1, x + 0.18, 2.56, active ? C.green : C.blue);
  tx(s, name, x + 0.18, 3.08, 1.35, 0.28, {
    fontFace: FONT_H, bold: true, fontSize: 11.5,
    color: active ? C.green : C.ink, charSpacing: 0.8,
  });
  tx(s, body, x + 0.18, 3.5, 1.35, 0.73, {
    fontSize: 10.2, color: C.muted, valign: "top",
  });
  if (i < flow.length - 1) tx(s, "›", x + 1.72, 3.1, 0.28, 0.42, {
    fontFace: FONT_H, bold: true, fontSize: 24, color: C.blue, align: "center",
  });
});
shape(s, "rect", 0.7, 4.88, 11.9, 1.42, C.navy, C.navy, true);
pill(s, "EXAMPLE", 0.98, 5.12, 1.0, C.blue, C.white, C.blue,
  { h: 0.3, fontSize: 8.5 });
tx(s, "Dock dwell passes free time", 2.18, 5.08, 2.0, 0.38, {
  fontFace: FONT_H, bold: true, fontSize: 11.8, color: C.white, valign: "mid",
});
tx(s, "→", 4.18, 5.09, 0.35, 0.34, { fontSize: 19, bold: true, color: C.blue, align: "center" });
tx(s, "POD + GPS are checked", 4.58, 5.08, 1.75, 0.38, {
  fontFace: FONT_H, bold: true, fontSize: 11.8, color: C.white, valign: "mid",
});
tx(s, "→", 6.34, 5.09, 0.35, 0.34, { fontSize: 19, bold: true, color: C.blue, align: "center" });
tx(s, "$142.50 is proposed", 6.74, 5.08, 1.62, 0.38, {
  fontFace: FONT_H, bold: true, fontSize: 11.8, color: C.green, valign: "mid",
});
tx(s, "→", 8.4, 5.09, 0.35, 0.34, { fontSize: 19, bold: true, color: C.blue, align: "center" });
tx(s, "Dispatcher approves invoice", 8.8, 5.08, 2.45, 0.38, {
  fontFace: FONT_H, bold: true, fontSize: 11.8, color: C.white, valign: "mid",
});
tx(s, "Every stage emits the next state change; the dispatcher never has to manually re-enter the same fact.",
  0.98, 5.7, 10.95, 0.3, { fontSize: 10.6, color: "9FB0C2" });
pill(s, "EVENT-DRIVEN BY DESIGN", 9.72, 6.43, 2.88, C.blue2, C.blue, C.blue2,
  { fontSize: 8.8 });

// 4 — Five modules
s = newSlide(C.bg, "What I built");
heading(s, "Prototype scope", "One product surface covers the full load lifecycle.",
  "The brief requires two problem areas; the working prototype covers all five.");
pill(s, "5 OF 5 AREAS BUILT", 10.25, 1.5, 2.35, C.green2, C.green, C.green2,
  { fontSize: 9 });
shape(s, "rect", 0.7, 2.05, 11.9, 0.48, C.navy, C.navy, true);
tx(s, "PROBLEM AREA", 0.92, 2.21, 1.82, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.white, charSpacing: 1,
});
tx(s, "DISPATCHER JOB", 3.18, 2.21, 3.6, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.white, charSpacing: 1,
});
tx(s, "WORKING PROTOTYPE OUTCOME", 7.28, 2.21, 5.0, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.white, charSpacing: 1,
});
const modules = [
  ["Smart Dispatch", "Choose a feasible driver without calling the fleet.",
    "Scored candidates + agent recommendation + editable driver SMS."],
  ["Proactive Alerts", "Catch the exception before the customer calls.",
    "Dark, off-route, ETA, detention, HOS, and maintenance actions in one queue."],
  ["Cost Intelligence", "Explain margin and cost-per-mile movement.",
    "36 months of KPIs + plain-English questions answered through guarded SQL."],
  ["Safety & Compliance", "Intervene before risk becomes an incident or audit finding.",
    "HOS clocks, risk watchlist, PM/inspection flags, and coaching briefs."],
  ["Billing Automation", "Turn complete paperwork into an accurate invoice quickly.",
    "Vision extraction + code reconciliation + audit memo + approved invoice."],
];
modules.forEach((row, i) => {
  const y = 2.6 + i * 0.8;
  shape(s, "rect", 0.7, y, 11.9, 0.72, i % 2 ? "F9FAFC" : C.white, C.line);
  tx(s, row[0], 0.92, y + 0.18, 1.82, 0.36, {
    fontFace: FONT_H, bold: true, fontSize: 11.3, color: i === 4 ? C.green : C.blue,
    valign: "mid",
  });
  tx(s, row[1], 3.18, y + 0.13, 3.55, 0.46, {
    fontSize: 10.7, color: C.ink, valign: "mid",
  });
  tx(s, row[2], 7.28, y + 0.13, 5.0, 0.46, {
    fontSize: 10.7, color: C.muted, valign: "mid",
  });
});
tx(s, "PRE-LOAD", 0.7, 6.75, 2.2, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint,
});
shape(s, "line", 1.65, 6.84, 2.05, 0, C.bg, C.line);
tx(s, "IN TRANSIT", 3.85, 6.75, 2.2, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint,
});
shape(s, "line", 4.95, 6.84, 2.05, 0, C.bg, C.line);
tx(s, "DELIVERED", 7.2, 6.75, 2.2, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint,
});
shape(s, "line", 8.22, 6.84, 1.9, 0, C.bg, C.line);
tx(s, "ALWAYS ON", 10.25, 6.75, 2.2, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.5, color: C.faint,
});

// 5 — LLM duties
s = newSlide(C.bg, "LLM responsibilities");
heading(s, "What the AI actually does", "Each module gives the LLM a narrow, explainable job.",
  "Trusted inputs go in; a recommendation, explanation, or draft comes out.");

function dutyRow(slide, y, label, items, accent) {
  shape(slide, "rect", 0.7, y, 11.9, 0.79, C.white, C.line, true);
  shape(slide, "rect", 0.7, y, 2.22, 0.79, accent === C.green ? C.green2 : C.blue2,
    accent === C.green ? C.green2 : C.blue2, true);
  tx(slide, label, 0.92, y + 0.18, 1.78, 0.42, {
    fontFace: FONT_H, bold: true, fontSize: 11.4, color: accent, valign: "mid",
  });
  items.forEach((item, i) => {
    const x = 3.12 + i * 3.08;
    numberBadge(slide, i + 1, x, y + 0.22, accent);
    tx(slide, item, x + 0.46, y + 0.12, 2.43, 0.54, {
      fontSize: 10.4, color: C.ink, valign: "mid",
    });
  });
}

dutyRow(s, 2.08, "Smart Dispatch — the AI:", [
  "Reviews pre-scored driver options", "Checks HOS feasibility and risk",
  "Recommends one driver, explains, and drafts SMS",
], C.blue);
dutyRow(s, 2.98, "Proactive Alerts — the AI:", [
  "Pulls trip, GPS, HOS, and customer evidence", "Forms a likely cause and impact",
  "Proposes the next action and message",
], C.blue);
dutyRow(s, 3.88, "Cost Intelligence — the AI:", [
  "Turns plain English into guarded SQL", "Reads only the returned rows",
  "Explains the result and chart-ready insight",
], C.blue);
dutyRow(s, 4.78, "Safety — the AI:", [
  "Reads computed driver-risk factors", "Separates urgent from historical risk",
  "Writes a coaching brief and talking points",
], C.blue);
dutyRow(s, 5.68, "Billing — the AI:", [
  "Extracts document fields with Vision", "Explains code-confirmed discrepancies",
  "Drafts the audit memo and invoice email",
], C.green);
shape(s, "rect", 0.7, 6.61, 11.9, 0.34, C.navy, C.navy, true);
tx(s, "The LLM interprets, synthesizes, and communicates. It does not own HOS, detection, risk scores, SQL permissions, or money math.",
  0.9, 6.7, 11.5, 0.17, {
    fontFace: FONT_H, bold: true, fontSize: 9.4, color: C.white, align: "center",
  });

// 6 — Decision boundary
s = newSlide(C.bg, "Trust and control");
heading(s, "AI-native, not AI-everywhere",
  "The code controls facts. The model handles judgment. The dispatcher controls consequences.",
  "That boundary makes the product useful without asking a small fleet to trust a black box.",
  { titleSize: 24, titleH: 0.9, subY: 1.68 });
const boundaries = [
  {
    x: 0.7, label: "01  DETERMINISTIC CODE", color: C.blue, fill: C.blue2,
    title: "Compute and enforce",
    bullets: [
      "HOS ledger and legal schedules",
      "Candidate scores and event detectors",
      "Detention, invoice, and impact math",
      "Read-only SQL authorizer and schema checks",
    ],
  },
  {
    x: 4.82, label: "02  GEMINI AGENT", color: C.purple, fill: C.purple2,
    title: "Interpret and communicate",
    bullets: [
      "Investigates through read-only tools",
      "Synthesizes evidence and tradeoffs",
      "Recommends one next action",
      "Drafts SMS, email, brief, or memo",
    ],
  },
  {
    x: 8.94, label: "03  DISPATCHER", color: C.green, fill: C.green2,
    title: "Decide and execute",
    bullets: [
      "Sees evidence, rationale, and impact",
      "Edits the draft inline",
      "Approves or dismisses the proposal",
      "Owns the final operational decision",
    ],
  },
];
boundaries.forEach((b, i) => {
  shape(s, "rect", b.x, 2.18, 3.66, 3.72, C.white, C.line, true);
  shape(s, "rect", b.x, 2.18, 3.66, 0.52, b.fill, b.fill, true);
  tx(s, b.label, b.x + 0.22, 2.36, 3.2, 0.18, {
    fontFace: FONT_H, bold: true, fontSize: 9.1, color: b.color, charSpacing: 0.8,
  });
  tx(s, b.title, b.x + 0.22, 2.94, 3.18, 0.38, {
    fontFace: FONT_H, bold: true, fontSize: 17, color: C.ink,
  });
  dotList(s, b.bullets, b.x + 0.24, 3.52, 3.14, {
    gap: 0.51, fontSize: 10.7, dot: b.color,
  });
  if (i < 2) tx(s, "›", b.x + 3.7, 3.72, 0.38, 0.55, {
    fontFace: FONT_H, bold: true, fontSize: 30, color: C.blue, align: "center",
  });
});
const trustRules = [
  ["NO DIRECT MODEL WRITES", C.blue2, C.blue],
  ["NO LLM MONEY / HOS MATH", C.blue2, C.blue],
  ["EVERY TOOL CALL TRACED", C.purple2, C.purple],
  ["EVERY ACTION HUMAN-GATED", C.green2, C.green],
];
trustRules.forEach(([label, fill, color], i) =>
  pill(s, label, 0.7 + i * 3.0, 6.18, 2.76, fill, color, fill, { fontSize: 8.6 }));
tx(s, "If the LLM is unavailable, fleet state remains visible; only AI-generated recommendations pause.",
  0.7, 6.67, 11.9, 0.26, { fontSize: 10.4, color: C.muted, italic: true, align: "center" });

// 7 — Data honesty
s = newSlide(C.bg, "Data provenance");
heading(s, "What is real, simulated, and generated",
  "The demo is explicit about provenance—because trust starts with honest labels.",
  "Each data type exists for a different reason; none is presented as something it is not.",
  { titleSize: 25, titleH: 0.88, subY: 1.66 });
const provenance = [
  {
    x: 0.7, tag: "REAL", color: C.blue, fill: C.blue2,
    title: "3-year warehouse",
    big: "14 CSVs  ·  ~550k rows",
    bullets: [
      "85,410 loads and 85,410 trips",
      "196,442 fuel purchases",
      "170,820 delivery events",
      "Powers KPIs, lane history, and scorer features",
    ],
    note: "Answers: What has happened over time?",
  },
  {
    x: 4.82, tag: "SIMULATED", color: C.purple, fill: C.purple2,
    title: "Live operating plane",
    big: "14 trucks  ·  3 terminals",
    bullets: [
      "Dallas / Houston / Oklahoma City carve-out",
      "GPS movement on OSRM road geometry",
      "FMCSA-style HOS clocks and rest stops",
      "Faults alter telemetry; watchdogs earn detection",
    ],
    note: "Answers: What is happening right now?",
  },
  {
    x: 8.94, tag: "GENERATED", color: C.green, fill: C.green2,
    title: "Demo freight documents",
    big: "Rate con  ·  BOL  ·  POD  ·  receipts",
    bullets: [
      "Created deterministically at seed time",
      "Five packets contain known discrepancies",
      "Answer-key truth is hidden from the agent",
      "Gemini Vision must read the actual PDFs",
    ],
    note: "Answers: Can the workflow audit paperwork?",
  },
];
provenance.forEach((p) => {
  shape(s, "rect", p.x, 2.05, 3.66, 4.32, C.white, C.line, true);
  pill(s, p.tag, p.x + 0.22, 2.27, 1.12, p.fill, p.color, p.fill,
    { h: 0.3, fontSize: 8.8 });
  tx(s, p.title, p.x + 0.22, 2.82, 3.15, 0.4, {
    fontFace: FONT_H, bold: true, fontSize: 17, color: C.ink,
  });
  tx(s, p.big, p.x + 0.22, 3.32, 3.16, 0.38, {
    fontFace: FONT_H, bold: true, fontSize: 12.2, color: p.color,
  });
  dotList(s, p.bullets, p.x + 0.24, 3.94, 3.12, {
    gap: 0.45, fontSize: 10.4, dot: p.color,
  });
  shape(s, "line", p.x + 0.22, 5.83, 3.2, 0, C.white, C.line);
  tx(s, p.note, p.x + 0.22, 5.98, 3.15, 0.24, {
    fontFace: FONT_H, bold: true, fontSize: 9.5, color: C.muted,
  });
});
shape(s, "rect", 0.7, 6.56, 11.9, 0.38, C.navy, C.navy, true);
tx(s,
  "Prototype: packets are pre-generated, so no upload is required. Production: ingest driver scans, email attachments, or TMS documents. The LLM itself is never mocked.",
  0.9, 6.67, 11.5, 0.18, {
    fontFace: FONT_H, bold: true, fontSize: 9.1, color: C.white, align: "center",
  });

// 8 — Architecture
s = newSlide(C.bg, "System design");
heading(s, "Architecture", "Two data planes feed one human-approved action layer.",
  "The split keeps historical analytics real while making live behavior repeatable and testable.");

function pipelineNode(slide, x, y, w, title, sub, color = C.blue) {
  shape(slide, "rect", x, y, w, 0.76, C.white, C.line, true);
  shape(slide, "rect", x, y, 0.06, 0.76, color, color);
  tx(slide, title, x + 0.18, y + 0.13, w - 0.32, 0.23, {
    fontFace: FONT_H, bold: true, fontSize: 10.6, color: C.ink,
  });
  tx(slide, sub, x + 0.18, y + 0.42, w - 0.32, 0.2, {
    fontSize: 8.7, color: C.muted,
  });
}

shape(s, "rect", 0.7, 2.05, 5.7, 2.28, C.blue2, C.blue2, true);
pill(s, "HISTORICAL PLANE", 0.94, 2.26, 1.85, C.blue, C.white, C.blue,
  { h: 0.3, fontSize: 8.5 });
tx(s, "What has happened over 3 years?", 2.98, 2.29, 2.95, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.6, color: C.blue, align: "right",
});
pipelineNode(s, 0.94, 2.82, 1.12, "14 CSVs", "source data");
tx(s, "›", 2.08, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.blue, align: "center" });
pipelineNode(s, 2.35, 2.82, 1.12, "ETL", "derive + check");
tx(s, "›", 3.49, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.blue, align: "center" });
pipelineNode(s, 3.76, 2.82, 1.12, "SQLite", "warehouse");
tx(s, "›", 4.9, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.blue, align: "center" });
pipelineNode(s, 5.17, 2.82, 0.99, "KPIs", "Ask Fleet");
tx(s, "Analytics and scorer history", 0.94, 3.82, 5.15, 0.24, {
  fontSize: 9.5, color: C.muted, italic: true, align: "center",
});

shape(s, "rect", 6.75, 2.05, 5.85, 2.28, C.purple2, C.purple2, true);
pill(s, "LIVE PLANE", 6.99, 2.26, 1.45, C.purple, C.white, C.purple,
  { h: 0.3, fontSize: 8.5 });
tx(s, "What is happening right now?", 8.65, 2.29, 3.45, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.6, color: C.purple, align: "right",
});
pipelineNode(s, 6.99, 2.82, 1.16, "World", "fleet carve", C.purple);
tx(s, "›", 8.17, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.purple, align: "center" });
pipelineNode(s, 8.44, 2.82, 1.16, "Sim", "clock + mover", C.purple);
tx(s, "›", 9.62, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.purple, align: "center" });
pipelineNode(s, 9.89, 2.82, 1.16, "Watch", "state machines", C.purple);
tx(s, "›", 11.07, 2.93, 0.25, 0.4, { fontSize: 20, bold: true, color: C.purple, align: "center" });
pipelineNode(s, 11.34, 2.82, 1.02, "SSE", "live UI", C.purple);
tx(s, "Positions, HOS, exceptions, and UI state", 6.99, 3.82, 5.37, 0.24, {
  fontSize: 9.5, color: C.muted, italic: true, align: "center",
});

shape(s, "rect", 0.7, 4.75, 11.9, 1.64, C.navy, C.navy, true);
tx(s, "ACTION LAYER", 0.98, 4.98, 1.45, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.green, charSpacing: 1.2,
});
const actionNodes = [
  ["READ-ONLY TOOLS", "fleet facts + Vision"],
  ["GEMINI AGENT", "investigate + draft"],
  ["PENDING ACTION", "evidence + impact"],
  ["HUMAN + EXECUTOR", "approve + update state"],
];
actionNodes.forEach(([name, sub], i) => {
  const x = 0.98 + i * 2.92;
  shape(s, "rect", x, 5.38, 2.45, 0.68, i === 2 ? C.green : C.navy2,
    i === 2 ? C.green : "415165", true);
  tx(s, name, x + 0.12, 5.52, 2.2, 0.2, {
    fontFace: FONT_H, bold: true, fontSize: 9.4,
    color: i === 2 ? C.navy : C.white, align: "center",
  });
  tx(s, sub, x + 0.12, 5.78, 2.2, 0.16, {
    fontSize: 8.2, color: i === 2 ? "195138" : "A7B6C6", align: "center",
  });
  if (i < actionNodes.length - 1) tx(s, "›", x + 2.49, 5.49, 0.34, 0.34, {
    fontSize: 22, bold: true, color: C.blue, align: "center",
  });
});
tx(s, "One action model powers dispatch recommendations, exception triage, safety coaching, cost Q&A, and billing review.",
  0.7, 6.64, 11.9, 0.27, { fontSize: 10.4, color: C.muted, italic: true, align: "center" });

// 9 — Demo flow
s = newSlide(C.bg, "Interview demo");
heading(s, "Demo flow", "A 7-minute walkthrough tells one connected story.",
  "The goal is not to visit six pages—it is to show detect → decide → act → learn → collect.");
const demoSteps = [
  ["01", "Operations  ·  1:15", "Select a trip and verify its route highlights. Let a watchdog surface an exception; open Agent Trace."],
  ["02", "Action Queue  ·  0:45", "Inspect evidence and impact, edit the drafted SMS, approve it, then confirm it on Driver phone."],
  ["03", "Dispatch  ·  1:15", "Choose an unassigned load, compare drivers, ask the agent, approve, and see the new trip enter live operations."],
  ["04", "Cost  ·  1:00", "Ask “Which customers cause the most detention?” and inspect the guarded SQL plus chart-ready answer."],
  ["05", "Safety  ·  0:45", "Select an at-risk driver and generate a coaching brief grounded in computed HOS and risk facts."],
  ["06", "Billing  ·  1:30", "Audit a packet, surface $142.50 in unclaimed detention, and approve the corrected invoice."],
];
demoSteps.forEach(([num, title1, body], i) => {
  const x = 0.7 + (i % 3) * 4.1;
  const y = 2.08 + Math.floor(i / 3) * 2.05;
  shape(s, "rect", x, y, 3.86, 1.76, C.white, C.line, true);
  tx(s, num, x + 0.2, y + 0.18, 0.55, 0.35, {
    fontFace: FONT_H, bold: true, fontSize: 17, color: i === 5 ? C.green : C.blue,
  });
  tx(s, title1, x + 0.82, y + 0.2, 2.78, 0.3, {
    fontFace: FONT_H, bold: true, fontSize: 12.5, color: C.ink,
  });
  shape(s, "line", x + 0.2, y + 0.63, 3.44, 0, C.white, C.line);
  tx(s, body, x + 0.2, y + 0.82, 3.44, 0.7, {
    fontSize: 10.5, color: C.muted, valign: "top",
  });
});
shape(s, "rect", 0.7, 6.32, 11.9, 0.56, C.navy, C.navy, true);
tx(s, "WHAT TO NOTICE", 0.94, 6.51, 2.55, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.7, color: C.blue, charSpacing: 1,
});
tx(s, "The route, alert, proposal, approval, driver message, new trip, analytics, and invoice all share state—this is one product, not six mockups.",
  3.48, 6.47, 8.82, 0.25, {
    fontFace: FONT_H, bold: true, fontSize: 9.7, color: C.white, align: "right",
  });

// 10 — Tradeoffs
s = newSlide(C.bg, "Tradeoffs");
heading(s, "What I traded off", "I optimized for the product risk—not integration breadth.",
  "The prototype proves the decision loop deeply and labels what a production pilot still needs.");
shape(s, "rect", 0.7, 2.03, 11.9, 0.46, C.navy, C.navy, true);
tx(s, "PROTOTYPE CHOICE", 0.92, 2.18, 2.5, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9, color: C.white, charSpacing: 1,
});
tx(s, "WHY I CHOSE IT", 3.7, 2.18, 3.5, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9, color: C.white, charSpacing: 1,
});
tx(s, "PILOT-READY NEXT STEP", 7.78, 2.18, 4.4, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 9, color: C.white, charSpacing: 1,
});
const tradeoffs = [
  ["Simulated GPS and HOS", "The source dataset has neither; replay makes live exceptions testable.",
    "Connect Trucker Path ELD / Command telemetry."],
  ["Generated packets; no upload", "Proves Vision and reconciliation without building commodity ingest UI.",
    "Add driver scan, email, and TMS document ingestion."],
  ["One fleet + SQLite", "Keeps focus on the action loop and makes reset deterministic.",
    "Add tenancy, RBAC, Postgres, durable jobs, and backups."],
  ["External sends are simulated", "Avoids contacting real drivers or customers during a demo.",
    "Integrate SMS/email providers with idempotency, audit, and undo."],
  ["Free-tier Gemini quotas", "Enough to prove real calls, tracing, and fallback behavior.",
    "Use production quota/SLA, retries, evals, and model routing."],
];
tradeoffs.forEach((row, i) => {
  const y = 2.56 + i * 0.74;
  shape(s, "rect", 0.7, y, 11.9, 0.67, i % 2 ? "F9FAFC" : C.white, C.line);
  tx(s, row[0], 0.92, y + 0.15, 2.52, 0.37, {
    fontFace: FONT_H, bold: true, fontSize: 10.8, color: C.blue, valign: "mid",
  });
  tx(s, row[1], 3.7, y + 0.1, 3.64, 0.47, {
    fontSize: 10.1, color: C.ink, valign: "mid",
  });
  tx(s, row[2], 7.78, y + 0.1, 4.4, 0.47, {
    fontSize: 10.1, color: C.muted, valign: "mid",
  });
});
shape(s, "rect", 0.7, 6.4, 11.9, 0.46, C.green2, C.green2, true);
tx(s, "WHAT I DID NOT TRADE OFF", 0.94, 6.55, 2.35, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.7, color: C.green, charSpacing: 1,
});
tx(s, "Traceability  ·  deterministic HOS and money math  ·  human approval  ·  honest data labels",
  3.3, 6.51, 8.95, 0.24, {
    fontFace: FONT_H, bold: true, fontSize: 10.2, color: C.ink, align: "right",
  });

// 11 — Success metrics
s = newSlide(C.bg, "Measuring success");
heading(s, "Success metrics", "Measure verified outcomes and earned trust—not model activity.",
  "A busy agent is not the goal. A dispatcher making faster, better decisions is.");
shape(s, "rect", 0.7, 2.02, 11.9, 0.92, C.blue2, C.blue, true);
tx(s, "NORTH STAR", 0.98, 2.23, 1.35, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.4, color: C.blue, charSpacing: 1.4,
});
tx(s, "Approved actions with a verified outcome per active truck per week", 2.43, 2.16, 7.5, 0.34, {
  fontFace: FONT_H, bold: true, fontSize: 16.5, color: C.ink,
});
tx(s, "Tie every proposal to dollars recovered, delay avoided, risk reduced, or dispatcher time saved.",
  2.43, 2.53, 8.9, 0.21, { fontSize: 9.8, color: C.muted });

card(s, 0.7, 3.2, 3.66, 2.75, "Activation & adoption", "", {
  accent: C.blue, titleColor: C.blue, bodyY: 0.62,
});
dotList(s, [
  "Time to first approved action",
  "Weekly active dispatcher / fleet",
  "Actions reviewed per active truck",
  "Median time from alert to decision",
], 0.96, 4.0, 3.08, { gap: 0.46, fontSize: 10.6, dot: C.blue });

card(s, 4.84, 3.2, 3.66, 2.75, "Business outcomes", "", {
  accent: C.green, titleColor: C.green, bodyY: 0.62,
});
dotList(s, [
  "Deadhead % of total miles",
  "Exceptions caught before customer call",
  "Delivery-to-invoice cycle time",
  "Detention dollars recovered / 100 loads",
], 5.1, 4.0, 3.08, { gap: 0.46, fontSize: 10.6, dot: C.green });

card(s, 8.94, 3.2, 3.66, 2.75, "Trust & safety", "", {
  accent: C.purple, titleColor: C.purple, bodyY: 0.62,
});
dotList(s, [
  "Approval and dismissal rates",
  "Edit-before-approve rate over time",
  "False-positive / unsafe proposal rate",
  "Trace completeness and blocked-query rate",
], 9.2, 4.0, 3.08, { gap: 0.46, fontSize: 10.6, dot: C.purple });

tx(s, "INITIAL 90-DAY PILOT HYPOTHESES — TO VALIDATE", 0.7, 6.17, 3.6, 0.18, {
  fontFace: FONT_H, bold: true, fontSize: 8.8, color: C.faint, charSpacing: 1.1,
});
const targets = [
  ["<15 MIN", "to first approval", C.blue2, C.blue],
  [">80%", "high-risk exceptions caught first", C.blue2, C.blue],
  ["<1 DAY", "delivery to invoice", C.green2, C.green],
  ["0", "unsafe executed actions", C.purple2, C.purple],
];
targets.forEach(([value, label, fill, color], i) => {
  const x = 0.7 + i * 3.0;
  shape(s, "rect", x, 6.45, 2.76, 0.48, fill, fill, true);
  tx(s, value, x + 0.13, 6.58, 0.78, 0.2, {
    fontFace: FONT_H, bold: true, fontSize: 11.3, color,
  });
  tx(s, label, x + 0.88, 6.57, 1.72, 0.22, {
    fontSize: 8.9, color: C.ink, valign: "mid",
  });
});

// 12 — GTM and close
s = newSlide(C.bg, "Go-to-market");
heading(s, "From prototype to pilot", "Land with found money. Expand as trust is earned.",
  "Billing proves ROI in week one; daily operations earns the right to broader autonomy.");

card(s, 0.7, 2.05, 3.22, 4.36, "Ideal customer", "", {
  accent: C.blue, titleColor: C.blue, bodyY: 0.62,
});
tx(s, "5–50", 0.98, 2.94, 1.12, 0.54, {
  fontFace: FONT_H, bold: true, fontSize: 31, color: C.blue,
});
tx(s, "TRUCKS", 2.08, 3.15, 0.95, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.faint, charSpacing: 1.3,
});
dotList(s, [
  "For-hire fleet; owner and dispatcher are often the buyers",
  "Spreadsheets, phones, QuickBooks, or a disliked legacy TMS",
  "Feels every empty mile, late surprise, and delayed invoice",
], 0.98, 3.78, 2.62, { gap: 0.64, fontSize: 10.5, dot: C.blue });
tx(s, "Why first", 0.98, 5.86, 0.85, 0.22, {
  fontFace: FONT_H, bold: true, fontSize: 10, color: C.ink,
});
tx(s, "High pain density, measurable ROI, and short buying cycles.", 1.72, 5.82, 1.9, 0.42, {
  fontSize: 9.6, color: C.muted, valign: "mid",
});

shape(s, "rect", 4.16, 2.05, 4.67, 4.36, C.white, C.line, true);
tx(s, "TRUST LADDER", 4.42, 2.28, 2.2, 0.22, {
  fontFace: FONT_H, bold: true, fontSize: 10, color: C.green, charSpacing: 1.5,
});
const stages = [
  ["1", "Billing Auditor", "$30–40 / truck / month", "Find missed charges and shorten time-to-invoice."],
  ["2", "Alerts + Dispatch", "Expand with native telemetry", "Become the dispatcher’s daily exception workspace."],
  ["3", "Full Copilot", "$75–90 / truck / month", "Cost and safety history become the retention moat."],
];
stages.forEach(([n, title1, price, body], i) => {
  const y = 2.86 + i * 1.02;
  numberBadge(s, n, 4.43, y + 0.06, i === 0 ? C.green : C.blue);
  tx(s, title1, 4.93, y, 1.48, 0.28, {
    fontFace: FONT_H, bold: true, fontSize: 11.8, color: C.ink,
  });
  tx(s, price, 6.42, y + 0.02, 2.08, 0.22, {
    fontFace: FONT_H, bold: true, fontSize: 9.4, color: i === 0 ? C.green : C.blue,
    align: "right",
  });
  tx(s, body, 4.93, y + 0.34, 3.57, 0.32, {
    fontSize: 9.6, color: C.muted,
  });
  if (i < 2) shape(s, "line", 4.6, y + 0.48, 0, 0.55, C.white, C.line);
});
shape(s, "rect", 4.43, 5.91, 4.12, 0.28, C.green2, C.green2, true);
tx(s, "Autonomy rises only after approval and edit metrics earn it.",
  4.58, 5.98, 3.82, 0.14, { fontFace: FONT_H, bold: true, fontSize: 8.6, color: C.green, align: "center" });

card(s, 9.07, 2.05, 3.53, 4.36, "Why Trucker Path can win", "", {
  accent: C.purple, titleColor: C.purple, bodyY: 0.62,
});
dotList(s, [
  "The driver network is the funnel: scans can seed the fleet-side audit",
  "ELD / Command fleets already have the telemetry needed for activation",
  "A 14-day “billing archaeology” trial proves value before the sale",
], 9.34, 2.97, 2.98, { gap: 0.72, fontSize: 10.4, dot: C.purple });
shape(s, "line", 9.34, 5.34, 2.98, 0, C.white, C.line);
tx(s, "FIRST PILOT", 9.34, 5.6, 1.25, 0.2, {
  fontFace: FONT_H, bold: true, fontSize: 9.2, color: C.green, charSpacing: 1.2,
});
tx(s, "3–5 fleets  ·  90 days of documents + telemetry  ·  validate recovered dollars and trust",
  9.34, 5.93, 2.98, 0.28, { fontSize: 9.2, color: C.ink, valign: "mid" });

shape(s, "rect", 0.7, 6.62, 11.9, 0.34, C.navy, C.navy, true);
tx(s, "Fleet Copilot gives small fleets an AI operating layer—without taking control away from the dispatcher.",
  0.9, 6.71, 11.5, 0.17, {
    fontFace: FONT_H, bold: true, fontSize: 9.7, color: C.white, align: "center",
  });

const output = path.join(__dirname, "Fleet-Copilot-Deck.pptx");
pptx.writeFile({ fileName: output })
  .then(() => console.log(`written ${output}`))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
