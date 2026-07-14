"use client";

import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/shell/AppShell";
import { FleetMap } from "@/components/map/FleetMap";
import { ActionCard } from "@/components/ops/ActionQueue";
import { ActivityFeed } from "@/components/ops/ActivityFeed";
import { api } from "@/lib/api";
import { hhmm, minutesAsHours, num } from "@/lib/format";
import { useActions, useExceptions, useFleetState } from "@/lib/hooks";

const ETA_BADGE: Record<string, string> = {
  NORMAL: "bg-emerald-50 text-tp-ok",
  WATCH: "bg-yellow-50 text-tp-watch",
  AT_RISK: "bg-amber-50 text-tp-risk",
  CRITICAL: "bg-red-50 text-tp-crit",
};

function TripTable({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const { data } = useFleetState();
  const trips = data?.trips ?? [];
  const drivers = useMemo(
    () => new Map((data?.drivers ?? []).map((d) => [d.driver_id, d])),
    [data],
  );
  return (
    <div className="h-full overflow-auto rounded-lg border border-tp-line bg-white">
      <table className="tp-table w-full text-left text-[12px]">
        <thead className="sticky top-0 bg-white shadow-[0_1px_0_var(--tp-line)]">
          <tr>
            {["Trip", "Lane", "Driver", "Progress", "ETA vs plan", "HOS left", "Last ping"].map(
              (h) => (
                <th key={h} className="px-3 py-2">
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {trips.map((t) => {
            const d = drivers.get(t.driver_id);
            const slip = t.projected_eta
              ? Math.round(
                  (new Date(t.projected_eta).getTime() -
                    new Date(t.planned_eta).getTime()) /
                    60000,
                )
              : 0;
            return (
              <tr
                key={t.trip_id}
                onClick={() => onSelect(t.trip_id === selected ? null : t.trip_id)}
                className={`cursor-pointer border-t border-tp-line/60 hover:bg-tp-bg/60 ${
                  t.trip_id === selected ? "bg-blue-50/60" : ""
                }`}
              >
                <td className="px-3 py-1.5 font-mono text-[11px]">{t.trip_id}</td>
                <td className="px-3 py-1.5">
                  {t.lane}
                  <span className="block text-[10.5px] text-tp-muted">{t.customer}</span>
                </td>
                <td className="px-3 py-1.5">{d?.name ?? t.driver_id}</td>
                <td className="px-3 py-1.5">
                  <span className="tp-num">
                    {num(t.progress_miles)}/{num(t.total_miles)} mi
                  </span>
                  <span className="mt-0.5 block h-1 w-24 overflow-hidden rounded bg-tp-line">
                    <span
                      className="block h-full bg-tp-blue"
                      style={{ width: `${(t.progress_miles / t.total_miles) * 100}%` }}
                    />
                  </span>
                </td>
                <td className="px-3 py-1.5">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10.5px] font-semibold ${ETA_BADGE[t.eta_state]}`}
                  >
                    {t.eta_state === "NORMAL"
                      ? "on plan"
                      : `${t.eta_state.toLowerCase().replace("_", " ")} ${slip > 0 ? `+${slip}m` : ""}`}
                  </span>
                  {t.status !== "IN_TRANSIT" && (
                    <span className="ml-1 text-[10.5px] text-tp-muted">
                      {t.status.toLowerCase().replaceAll("_", " ")}
                    </span>
                  )}
                </td>
                <td className="tp-num px-3 py-1.5">
                  {d ? minutesAsHours(Math.min(d.drive_min_remaining, d.window_min_remaining)) : "—"}
                </td>
                <td className="tp-num px-3 py-1.5 text-tp-muted">{hhmm(t.last_ping_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ExceptionRail() {
  const { data: exceptions } = useExceptions();
  const { data: actions } = useActions();
  const pending = (actions ?? []).filter((a) => a.status === "PENDING");
  const open = (exceptions ?? []).filter(
    (e) => e.state === "OPEN" || e.state === "TRIAGING",
  );

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-tp-line bg-white">
        <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
          <Sparkles className="h-3.5 w-3.5 text-tp-blue" />
          <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
            Action queue
          </h2>
          <span className="ml-auto rounded bg-tp-bg px-1.5 text-[11px] tp-num">
            {pending.length}
          </span>
        </header>
        <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-2.5">
          {pending.map((a) => (
            <ActionCard key={a.id} action={a} />
          ))}
          {open.map((e) => (
            <div
              key={e.id}
              className="rounded-lg border border-dashed border-tp-line bg-tp-bg/50 px-3 py-2"
            >
              <p className="text-[11px] font-semibold text-tp-risk">
                {e.severity} · {e.type.replaceAll("_", " ")}
              </p>
              <p className="text-[12px] leading-snug">{e.title}</p>
              <button
                className="mt-1.5 rounded border border-tp-line bg-white px-2 py-1 text-[11px] font-medium hover:border-tp-blue hover:text-tp-blue"
                onClick={() => void api.post(`/api/exceptions/${e.id}/triage`)}
              >
                {e.state === "TRIAGING" ? "Agent investigating…" : "Send agent to investigate"}
              </button>
            </div>
          ))}
          {pending.length === 0 && open.length === 0 && (
            <p className="px-1 py-3 text-[12px] text-tp-muted">
              Nothing needs a decision right now. When the watchdog flags a
              load, the agent investigates and its proposal lands here for your
              approval.
            </p>
          )}
        </div>
      </section>
      <section className="flex h-[38%] min-h-[170px] flex-col rounded-lg border border-tp-line bg-white">
        <header className="border-b border-tp-line px-3 py-2">
          <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
            Operations feed
          </h2>
        </header>
        <ActivityFeed />
      </section>
    </div>
  );
}

export default function OperationsPage() {
  const [selectedTrip, setSelectedTrip] = useState<string | null>(null);
  const { data } = useFleetState();
  const { data: exceptions } = useExceptions();

  const alertTrips = useMemo(
    () =>
      new Set(
        (exceptions ?? [])
          .filter((e) => e.trip_id && e.state !== "RESOLVED" && e.state !== "DISMISSED")
          .map((e) => e.trip_id as string),
      ),
    [exceptions],
  );

  return (
    <AppShell>
      <div className="grid h-full grid-cols-[1fr_360px] gap-3 p-3">
        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-0 flex-[3]">
            <FleetMap
              trips={data?.trips ?? []}
              alertTrips={alertTrips}
              selectedTrip={selectedTrip}
              onSelectTrip={setSelectedTrip}
            />
          </div>
          <div className="min-h-0 flex-[2] overflow-hidden">
            <TripTable selected={selectedTrip} onSelect={setSelectedTrip} />
          </div>
        </div>
        <ExceptionRail />
      </div>
    </AppShell>
  );
}
