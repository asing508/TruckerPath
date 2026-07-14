"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, CircleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/shell/AppShell";
import { ActionCard } from "@/components/ops/ActionQueue";
import { api } from "@/lib/api";
import { mdhm, minutesAsHours, num, pct, usd } from "@/lib/format";
import { useActions, useLive } from "@/lib/hooks";
import type { UnassignedLoad } from "@/lib/types";

interface Candidate {
  driver_id: string;
  name: string;
  home_terminal: string;
  deadhead_miles: number;
  eta_at_pickup: string;
  lane_trips_career: number;
  score: number;
  flags: string[];
  hos: {
    drive_min_remaining: number;
    window_min_remaining: number;
    cycle_min_remaining: number;
  };
  history: { on_time_rate: number; incidents_career: number };
}

interface Board {
  unassigned_loads: UnassignedLoad[];
  idle_drivers: unknown[];
}

function CandidateTable({ loadId }: { loadId: string }) {
  const { data } = useQuery({
    queryKey: ["candidates", loadId],
    queryFn: () =>
      api.get<{ candidates: Candidate[]; idle_driver_count: number }>(
        `/api/dispatch/candidates/${loadId}`,
      ),
  });
  if (!data) return <p className="p-3 text-[12px] text-tp-muted">Scoring the fleet…</p>;
  return (
    <div className="overflow-auto">
      <table className="tp-table w-full text-left text-[12px]">
        <thead>
          <tr>
            {["Rank", "Driver", "Deadhead", "At pickup", "HOS slack", "Lane trips", "On-time", "Score", "Flags"].map(
              (h) => (
                <th key={h} className="px-3 py-1.5">
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {data.candidates.map((c, i) => (
            <tr key={c.driver_id} className="border-t border-tp-line/60">
              <td className="tp-num px-3 py-1.5 text-tp-muted">{i + 1}</td>
              <td className="px-3 py-1.5">
                {c.name}
                <span className="block text-[10.5px] text-tp-muted">{c.home_terminal}</span>
              </td>
              <td className="tp-num px-3 py-1.5">{num(c.deadhead_miles)} mi</td>
              <td className="tp-num px-3 py-1.5">{mdhm(c.eta_at_pickup)}</td>
              <td className="tp-num px-3 py-1.5">
                {minutesAsHours(
                  Math.min(c.hos.drive_min_remaining, c.hos.window_min_remaining),
                )}
              </td>
              <td className="tp-num px-3 py-1.5">{c.lane_trips_career}</td>
              <td className="tp-num px-3 py-1.5">{pct(c.history.on_time_rate)}</td>
              <td className="tp-num px-3 py-1.5 font-semibold">{c.score}</td>
              <td className="px-3 py-1.5">
                {c.flags.map((f) => (
                  <span
                    key={f}
                    className="mb-0.5 mr-1 inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-tp-risk"
                  >
                    <CircleAlert className="h-3 w-3" />
                    {f}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-[11px] text-tp-muted">
        Score = deadhead + HOS slack + lane familiarity + on-time history +
        safety record. Deterministic and inspectable — the agent reasons on top
        of it, never instead of it.
      </p>
    </div>
  );
}

export default function DispatchPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const [asked, setAsked] = useState<Set<string>>(new Set());
  const { data: board } = useQuery({
    queryKey: ["dispatch"],
    queryFn: () => api.get<Board>("/api/dispatch/board"),
    refetchInterval: 20000,
  });
  const { data: actions } = useActions();
  const agentBusy = useLive((s) =>
    Object.values(s.runs).some((r) => r.kind === "dispatch" && r.status === "RUNNING"),
  );

  const pendingForLoad = useMemo(
    () =>
      new Map(
        (actions ?? [])
          .filter((a) => a.kind === "ASSIGN_DRIVER" && a.status === "PENDING")
          .map((a) => [a.subject_id, a]),
      ),
    [actions],
  );

  const loads = board?.unassigned_loads ?? [];

  return (
    <AppShell>
      <div className="grid h-full grid-cols-[minmax(430px,1fr)_minmax(430px,1fr)] gap-3 p-3">
        <section className="flex min-h-0 flex-col rounded-lg border border-tp-line bg-white">
          <header className="border-b border-tp-line px-3 py-2">
            <h1 className="font-heading text-[13px] font-semibold uppercase tracking-[0.14em]">
              Unassigned loads
            </h1>
            <p className="text-[11px] text-tp-muted">
              {loads.length} on the board · {board?.idle_drivers.length ?? 0} drivers available
            </p>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loads.map((l) => (
              <button
                key={l.load_id}
                onClick={() => setSelected(l.load_id)}
                className={`block w-full border-b border-tp-line/60 px-3 py-2.5 text-left hover:bg-tp-bg/60 ${
                  selected === l.load_id ? "bg-blue-50/70" : ""
                }`}
              >
                <span className="flex items-baseline gap-2">
                  <span className="font-mono text-[11px] text-tp-muted">{l.load_id}</span>
                  <span className="font-heading text-[13px] font-semibold">
                    {l.origin_city}, {l.origin_state} → {l.dest_city}, {l.dest_state}
                  </span>
                  <span className="tp-num ml-auto text-[13px] font-semibold text-tp-ok">
                    {usd(l.revenue)}
                  </span>
                </span>
                <span className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-tp-muted">
                  <span>{l.customer_name}</span>
                  <span className="tp-num">{num(l.distance_miles)} mi</span>
                  <span>{l.load_type}</span>
                  <span>{l.booking_type}</span>
                  <span className="tp-num">pickup {mdhm(l.pickup_window_start)}</span>
                </span>
              </button>
            ))}
            {loads.length === 0 && (
              <p className="p-4 text-[12px] text-tp-muted">
                Board is clear — every load is covered.
              </p>
            )}
          </div>
        </section>

        <section className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          {selected === null ? (
            <p className="rounded-lg border border-dashed border-tp-line p-6 text-center text-[12px] text-tp-muted">
              Pick a load to compare drivers across the fleet.
            </p>
          ) : (
            <>
              <div className="rounded-lg border border-tp-line bg-white">
                <header className="flex items-center border-b border-tp-line px-3 py-2">
                  <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
                    Fleet comparison · {selected}
                  </h2>
                  <button
                    disabled={agentBusy || asked.has(selected)}
                    onClick={() => {
                      setAsked(new Set(asked).add(selected));
                      void api.post(`/api/dispatch/recommend/${selected}`);
                    }}
                    className="ml-auto flex items-center gap-1.5 rounded-md bg-tp-blue px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-tp-blue-strong disabled:opacity-50"
                  >
                    <Bot className="h-3.5 w-3.5" />
                    {agentBusy
                      ? "Agent working…"
                      : asked.has(selected)
                        ? "Recommendation requested"
                        : "Ask agent to recommend"}
                  </button>
                </header>
                <CandidateTable loadId={selected} />
              </div>
              {pendingForLoad.has(selected) && (
                <ActionCard action={pendingForLoad.get(selected)!} />
              )}
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
