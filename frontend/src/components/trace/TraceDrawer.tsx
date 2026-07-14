"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useLive } from "@/lib/hooks";
import type { AgentRunRow, AgentStepRow } from "@/lib/types";

const KIND_STYLE: Record<string, string> = {
  tool_call: "text-tp-blue",
  tool_result: "text-tp-muted",
  thought: "text-violet-600",
  output: "text-tp-ok",
  error: "text-tp-crit",
};

function StepLine({ step }: { step: AgentStepRow }) {
  const [open, setOpen] = useState(false);
  const payload = useMemo(() => JSON.stringify(step.payload, null, 2), [step.payload]);
  const oneLine = useMemo(() => JSON.stringify(step.payload), [step.payload]);
  return (
    <div className="border-b border-white/5 px-3 py-1 font-mono text-[11px] leading-5">
      <button
        className="flex w-full items-start gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronRight
          className={`mt-1 h-3 w-3 shrink-0 text-white/30 transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className={`shrink-0 ${KIND_STYLE[step.kind] ?? "text-white/70"}`}>
          {step.kind}
        </span>
        {step.name && <span className="shrink-0 text-amber-300">{step.name}</span>}
        {!open && (
          <span className="truncate text-white/45">{oneLine}</span>
        )}
      </button>
      {open && (
        <pre className="mt-1 max-h-56 overflow-auto rounded bg-black/40 p-2 text-[10.5px] text-white/75">
          {payload}
        </pre>
      )}
    </div>
  );
}

export function TraceDrawer({ onClose }: { onClose: () => void }) {
  const liveRuns = useLive((s) => s.runs);
  const liveSteps = useLive((s) => s.steps);
  const [selected, setSelected] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: history } = useQuery({
    queryKey: ["agent-runs"],
    queryFn: () => api.get<AgentRunRow[]>("/api/agent/runs?limit=25"),
    refetchInterval: 25000,
  });

  const runs = useMemo(() => {
    const byId = new Map<number, AgentRunRow>();
    for (const r of history ?? []) byId.set(r.id, r);
    for (const r of Object.values(liveRuns)) {
      byId.set(r.id, { ...byId.get(r.id), ...r });
    }
    return [...byId.values()].sort((a, b) => b.id - a.id);
  }, [history, liveRuns]);

  const activeId = selected ?? runs[0]?.id ?? null;

  const { data: fetchedRun } = useQuery({
    queryKey: ["agent-run", activeId],
    queryFn: () => api.get<AgentRunRow>(`/api/agent/runs/${activeId}`),
    enabled: activeId !== null,
    refetchInterval: 6000,
  });

  const steps = useMemo(() => {
    const persisted = fetchedRun?.id === activeId ? (fetchedRun.steps ?? []) : [];
    const live = activeId !== null ? (liveSteps[activeId] ?? []) : [];
    const bySeq = new Map<number, AgentStepRow>();
    for (const s of persisted) bySeq.set(s.seq, s);
    for (const s of live) bySeq.set(s.seq, s);
    return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
  }, [fetchedRun, liveSteps, activeId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [steps.length]);

  return (
    <div className="flex h-[290px] shrink-0 flex-col border-t-2 border-tp-blue bg-tp-navy text-white">
      <div className="flex h-8 items-center gap-3 border-b border-white/10 px-3">
        <span className="font-heading text-[11px] font-semibold uppercase tracking-[0.16em] text-white/80">
          Agent execution trace
        </span>
        <span className="text-[11px] text-white/40">
          live function-calling telemetry · nothing here is scripted
        </span>
        <button onClick={onClose} className="ml-auto rounded p-1 hover:bg-white/10">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="w-[300px] shrink-0 overflow-y-auto border-r border-white/10">
          {runs.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelected(r.id)}
              className={`block w-full border-b border-white/5 px-3 py-2 text-left ${
                r.id === activeId ? "bg-white/10" : "hover:bg-white/5"
              }`}
            >
              <span className="flex items-center gap-2 text-[11px]">
                <span className="font-mono text-white/40">#{r.id}</span>
                <span className="font-semibold uppercase tracking-wide text-tp-blue">
                  {r.kind}
                </span>
                <span
                  className={`ml-auto font-mono text-[10px] ${
                    r.status === "RUNNING"
                      ? "text-emerald-300"
                      : r.status === "FAILED"
                        ? "text-red-300"
                        : "text-white/50"
                  }`}
                >
                  {r.status}
                </span>
              </span>
              <span className="mt-0.5 block truncate text-[11px] text-white/55">
                {r.summary || r.subject_id}
              </span>
            </button>
          ))}
          {runs.length === 0 && (
            <p className="p-4 text-[11px] text-white/40">
              No agent runs yet. Trigger one from Dispatch, Cost, Safety or
              Billing — or let the watchdog find something.
            </p>
          )}
        </div>
        <div ref={scrollRef} className="min-w-0 flex-1 overflow-y-auto">
          {steps.map((s) => (
            <StepLine key={s.seq} step={s} />
          ))}
          {activeId !== null && steps.length === 0 && (
            <p className="p-4 font-mono text-[11px] text-white/40">
              waiting for steps…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
