"use client";

import { ArrowLeft, ArrowRight, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

/* Product deck as a route — same content ships as docs/Fleet-Copilot-Deck.pptx.
   Arrow keys / click zones to navigate. */

function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 font-heading text-[13px] font-semibold uppercase tracking-[0.22em] text-tp-blue">
      {children}
    </p>
  );
}

function H(props: { children: React.ReactNode }) {
  return (
    <h2 className="mb-6 max-w-4xl font-heading text-[40px] font-bold leading-[1.12] text-tp-navy">
      {props.children}
    </h2>
  );
}

function Cell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-tp-line bg-white p-4">
      <h3 className="mb-1.5 font-heading text-[14px] font-semibold text-tp-navy">{title}</h3>
      <p className="text-[13px] leading-relaxed text-tp-muted">{children}</p>
    </div>
  );
}

const SLIDES: React.ReactNode[] = [
  // 1 — title
  <div key="t" className="flex h-full flex-col justify-center bg-tp-navy px-24 text-white">
    <p className="mb-4 font-heading text-[13px] font-semibold uppercase tracking-[0.24em] text-tp-blue">
      Trucker Path PM take-home · working prototype
    </p>
    <h1 className="max-w-4xl font-heading text-[64px] font-bold leading-[1.05]">
      Fleet Copilot
    </h1>
    <p className="mt-5 max-w-2xl text-[19px] leading-relaxed text-white/75">
      An AI-native operations assistant for 5–50 truck fleets — it watches every
      load, investigates its own alarms, and hands the dispatcher decisions
      instead of dashboards.
    </p>
    <p className="mt-10 text-[13px] text-white/50">
      All five problem areas · real LLM tool-calling on live telemetry · July 2026
    </p>
  </div>,

  // 2 — problem
  <div key="p" className="flex h-full flex-col justify-center px-24">
    <Kicker>The problem</Kicker>
    <H>A 14-truck dispatcher runs on phone calls, spreadsheets, and adrenaline.</H>
    <div className="grid max-w-5xl grid-cols-2 gap-3">
      <Cell title="8:05 AM">
        Three loads to cover. Who&apos;s closest? Who has hours left? Six phone
        calls to find out — and the answer changes while you dial.
      </Cell>
      <Cell title="11:40 AM">
        A load goes dark in Arkansas. You find out at 4 PM — when the customer
        calls you.
      </Cell>
      <Cell title="3:15 PM">
        Owner asks &quot;why is cost per mile up 9%?&quot; The answer lives in
        fuel receipts, ELD logs, and a QuickBooks export that don&apos;t talk.
      </Cell>
      <Cell title="6:30 PM">
        Chasing drivers for PODs and receipts. Invoices go out 4–5 days late,
        detention goes unbilled, and nobody notices until quarter end.
      </Cell>
    </div>
  </div>,

  // 3 — insight
  <div key="i" className="flex h-full flex-col justify-center px-24">
    <Kicker>The insight</Kicker>
    <H>Fleet software has been a system of record. The unlock is a system of agency.</H>
    <div className="grid max-w-5xl grid-cols-2 gap-6">
      <div className="rounded-lg border border-tp-line bg-white p-6">
        <h3 className="mb-3 font-heading text-[16px] font-semibold text-tp-muted">
          System of record — status quo
        </h3>
        <ul className="space-y-2 text-[14px] leading-relaxed text-tp-muted">
          <li>Shows a dot moving on a map</li>
          <li>Fires an alert, then waits</li>
          <li>Human does the investigation, the math, the phone calls, the email</li>
          <li>Value ceiling: visibility</li>
        </ul>
      </div>
      <div className="rounded-lg border-2 border-tp-blue bg-white p-6">
        <h3 className="mb-3 font-heading text-[16px] font-semibold text-tp-blue">
          System of agency — Fleet Copilot
        </h3>
        <ul className="space-y-2 text-[14px] leading-relaxed">
          <li>Detects the exception with deterministic watchdogs</li>
          <li>Agent investigates via tool calls: HOS, lane history, nearby trucks, customer SLA</li>
          <li>Proposes one concrete action with a drafted SMS / email and dollar impact</li>
          <li>Human edits inline and approves — every action stays human-gated</li>
        </ul>
      </div>
    </div>
    <p className="mt-6 max-w-4xl text-[15px] text-tp-muted">
      No chat sidebar. The dispatcher&apos;s unit of work is a <b>decision</b>,
      not a conversation.
    </p>
  </div>,

  // 4 — product map
  <div key="m" className="flex h-full flex-col justify-center px-24">
    <Kicker>The prototype</Kicker>
    <H>Five surfaces. Five pain points. Nothing else.</H>
    <div className="grid max-w-5xl grid-cols-2 gap-3">
      <Cell title="Operations — Proactive Alerts">
        Live map + watchdog: dark loads, route deviation, ETA slip, dock
        detention, HOS risk. Each HIGH/CRITICAL exception auto-dispatches the
        triage agent; its proposal lands in the Action Queue.
      </Cell>
      <Cell title="Dispatch — Smart Dispatch">
        Deterministic candidate scoring (deadhead, HOS slack, lane familiarity,
        on-time, safety) + agent recommendation memo + editable driver SMS.
      </Cell>
      <Cell title="Cost — Cost Intelligence">
        CPM decomposition over 85k historical trips, margin-per-mile trend, and
        &quot;Ask your fleet&quot;: English → guarded SQL → answer + chart.
      </Cell>
      <Cell title="Safety — Safety & Compliance">
        FMCSA HOS ledger (11h/14h/70h/8d, 30-min break), fatigue features,
        equipment PM/inspection tracking, agent-written coaching briefs.
      </Cell>
      <Cell title="Billing — Document Automation">
        Gemini Vision reads rate cons, BOLs, PODs, receipts → deterministic
        reconciler diffs them against the system of record and GPS dwell →
        invoice drafted, human approves.
      </Cell>
      <Cell title="Everywhere — Trust primitives">
        Agent Trace console shows every tool call live. Every draft is
        inline-editable. Every execution requires a click. Nothing is scripted.
      </Cell>
    </div>
  </div>,

  // 5 — AI design
  <div key="a" className="flex h-full flex-col justify-center px-24">
    <Kicker>How the AI is built</Kicker>
    <H>The model reasons. The code computes. The human decides.</H>
    <div className="grid max-w-5xl grid-cols-3 gap-3">
      <Cell title="Real tool-calling loops">
        Gemini 3.5 Flash with 10 read-only fleet tools (get_trip_state,
        get_candidate_drivers, find_nearby_drivers…). Every step is persisted
        and streamed to the trace console over SSE.
      </Cell>
      <Cell title="Guardrails by construction">
        NL→SQL runs on a read-only SQLite connection with an authorizer:
        SELECT-only, denylisted tables, row caps, VM-step budget. Money math is
        never delegated to the model — the reconciler and HOS ledger are code.
      </Cell>
      <Cell title="Human in the loop">
        Agents end at a PendingAction: title, rationale, dollar impact, and
        editable drafts. Approve executes; dismiss archives. The model never
        sends anything itself.
      </Cell>
    </div>
    <p className="mt-6 max-w-4xl rounded-lg border border-tp-line bg-white p-4 font-mono text-[12.5px] text-tp-muted">
      exception #14 DETENTION → agent: get_exception → get_trip_state →
      get_detention_math → get_customer_profile → proposal: notify customer AP,
      $142.50 detention documented via POD 19:05→22:59, GPS dwell corroborates
      · [Edit] [Approve & execute]
    </p>
  </div>,

  // 6 — data
  <div key="d" className="flex h-full flex-col justify-center px-24">
    <Kicker>Data foundation</Kicker>
    <H>Real operations data. Honestly simulated telemetry.</H>
    <div className="grid max-w-5xl grid-cols-2 gap-3">
      <Cell title="Historical warehouse — real">
        Public 3-year Class 8 carrier dataset: 85,410 loads/trips, 196k fuel
        purchases, 170k delivery events with detention minutes, maintenance and
        incident history. Powers every analytic and every scorer feature.
      </Cell>
      <Cell title="Live plane — simulated forward">
        The dataset has no GPS pings or HOS, so the sim supplies them: positions
        replayed along real OSRM road geometry, duty ledgers ticked by a
        deterministic engine (seeded, resettable).
      </Cell>
      <Cell title="Faults are injected, detection is earned">
        Demo incidents (GPS blackout, slowdown, off-route drift, dock dwell) are
        scripted into <i>telemetry</i>. The watchdog has to detect them from the
        data — alerts are never hardcoded.
      </Cell>
      <Cell title="The LLM is never mocked">
        Every recommendation, triage, brief, extraction, and answer is a live
        Gemini call — visible, step by step, in the trace console.
      </Cell>
    </div>
  </div>,

  // 7 — tradeoffs
  <div key="tr" className="flex h-full flex-col justify-center px-24">
    <Kicker>What I traded off</Kicker>
    <H>Cut scope, kept honesty.</H>
    <div className="grid max-w-5xl grid-cols-2 gap-3">
      <Cell title="No auth, no multi-tenant">
        One fleet, one dispatcher persona. The interesting risk was the agentic
        loop, not login forms.
      </Cell>
      <Cell title="Simulated world, not integrations">
        Samsara/Motive/TP ELD integration is a connector problem with known
        shape. I spent the time on what the system does <i>after</i> the data
        arrives.
      </Cell>
      <Cell title="Reroute/relay stop at the proposal">
        Approving a reroute logs and notifies but doesn&apos;t re-optimize the
        whole board — honest about where the prototype ends.
      </Cell>
      <Cell title="Free-tier LLM quotas">
        Engineered around, not hidden: model cascade across quota buckets,
        paced calls, serialized auto-triage. Swap in a paid key and it simply
        gets faster.
      </Cell>
    </div>
  </div>,

  // 8 — metrics
  <div key="me" className="flex h-full flex-col justify-center px-24">
    <Kicker>How I&apos;d measure success</Kicker>
    <H>One activation metric, three P&L metrics, two trust metrics.</H>
    <div className="max-w-5xl space-y-3">
      <div className="rounded-lg border-2 border-tp-blue bg-white p-4">
        <h3 className="font-heading text-[15px] font-semibold text-tp-blue">
          Activation: time-to-first-approved-action
        </h3>
        <p className="text-[13.5px] text-tp-muted">
          The product is working the first time a dispatcher approves an agent
          proposal. Target: under 15 minutes from install.
        </p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Cell title="Deadhead % of miles">
          Better assignments → fewer empty miles. Baseline from fleet history;
          target −15% in 90 days.
        </Cell>
        <Cell title="Days-to-invoice">
          Audit-to-invoice in minutes, not days. Target: 4.6 → &lt;1.0 average;
          detention recovery per 100 loads as the kicker.
        </Cell>
        <Cell title="Exceptions caught before customer call">
          Share of late/dark loads the system flagged first. The &quot;never go
          dark again&quot; promise, quantified.
        </Cell>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Cell title="Approval rate">
          Approved / proposed. Below ~60% means the agent is noisy; above ~95%
          means it&apos;s too timid to be useful.
        </Cell>
        <Cell title="Edit-before-approve rate">
          How often dispatchers fix drafts. Falling edit rate = growing trust —
          the leading indicator for expanding autonomy.
        </Cell>
      </div>
    </div>
  </div>,

  // 9 — GTM
  <div key="g" className="flex h-full flex-col justify-center px-24">
    <Kicker>Go-to-market</Kicker>
    <H>Trucker Path already owns the funnel.</H>
    <div className="grid max-w-5xl grid-cols-3 gap-3">
      <Cell title="ICP">
        5–50 truck for-hire fleets — ~50k US carriers. One dispatcher wearing
        four hats; no TMS, or a TMS they hate. Willingness to pay tracks saved
        hours and recovered detention, both measurable in-product.
      </Cell>
      <Cell title="Wedge & pricing">
        Land with Billing Audit (fast, provable ROI: found money on real
        paperwork) at $30–40/truck/mo. Expand to full Copilot at
        $75–90/truck/mo once the trust metrics clear. 30-truck fleet ≈ $32k ACV.
      </Cell>
      <Cell title="Acquisition">
        1M+ drivers already run Trucker Path in the cab: driver-side doc scans
        seed the fleet product. Upsell path from ELD/Command install base — CAC
        near zero versus cold outbound.
      </Cell>
    </div>
    <p className="mt-6 max-w-4xl text-[15px] text-tp-muted">
      Sequencing: billing wedge → dispatch + alerts once telemetry is native →
      cost & safety complete the retention moat.
    </p>
  </div>,

  // 10 — roadmap/close
  <div key="r" className="flex h-full flex-col justify-center bg-tp-navy px-24 text-white">
    <Kicker>If this ships</Kicker>
    <h2 className="mb-6 max-w-4xl font-heading text-[40px] font-bold leading-[1.12]">
      Next 3 moves, in order.
    </h2>
    <ol className="max-w-3xl space-y-4 text-[16px] leading-relaxed text-white/85">
      <li>
        <b className="text-tp-blue">1 · Real telemetry.</b> Swap the sim for TP
        ELD / Command streams — the watchdog and agents don&apos;t change, only
        the ingest does. That&apos;s the point of the two-plane design.
      </li>
      <li>
        <b className="text-tp-blue">2 · Autonomy ladder.</b> Per-action-type
        trust levels: propose → auto-execute-with-undo → autonomous within
        budget. Gated by each fleet&apos;s own approval/edit history.
      </li>
      <li>
        <b className="text-tp-blue">3 · Multi-load optimization.</b> From
        one-load recommendations to board-level assignment (deadhead-aware
        matching across tomorrow&apos;s loads) — the ripple-effect problem.
      </li>
    </ol>
    <p className="mt-10 text-[13px] text-white/50">
      Thanks — the prototype is live; every agent decision you saw was a real
      model call.
    </p>
  </div>,
];

export default function DeckPage() {
  const [i, setI] = useState(0);
  const next = useCallback(() => setI((v) => Math.min(v + 1, SLIDES.length - 1)), []);
  const prev = useCallback(() => setI((v) => Math.max(v - 1, 0)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " ") next();
      if (e.key === "ArrowLeft") prev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  return (
    <div className="fixed inset-0 flex flex-col bg-tp-bg">
      <div className="relative min-h-0 flex-1">{SLIDES[i]}</div>
      <footer className="flex h-12 items-center gap-3 border-t border-tp-line bg-white px-4">
        <Link
          href="/"
          className="flex items-center gap-1.5 rounded-md border border-tp-line px-2.5 py-1.5 text-[12px] font-medium text-tp-muted hover:text-tp-text"
        >
          <X className="h-3.5 w-3.5" /> Back to app
        </Link>
        <span className="ml-auto font-mono text-[12px] text-tp-muted">
          {i + 1} / {SLIDES.length}
        </span>
        <button onClick={prev} disabled={i === 0} className="rounded-md border border-tp-line p-1.5 disabled:opacity-40">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <button
          onClick={next}
          disabled={i === SLIDES.length - 1}
          className="rounded-md bg-tp-blue p-1.5 text-white disabled:opacity-40"
        >
          <ArrowRight className="h-4 w-4" />
        </button>
      </footer>
    </div>
  );
}
