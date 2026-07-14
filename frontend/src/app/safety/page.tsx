"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, ShieldAlert, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import { AppShell } from "@/components/shell/AppShell";
import { api } from "@/lib/api";
import { minutesAsHours, num, pct } from "@/lib/format";
import { useLive } from "@/lib/hooks";

interface RiskRow {
  driver_id: string;
  name: string;
  terminal: string;
  duty: string;
  risk_score: number;
  risk_level: string;
  factors: {
    cycle_used_pct: number;
    drive_min_remaining: number;
    window_min_remaining: number;
    night_driving_share: number;
    active_violations: string;
    incidents_since_2023: number;
    preventable_incidents: number;
    truck_pm_overdue: boolean;
    inspection_days_left: number | null;
  };
}

interface EquipmentRow {
  truck_id: string;
  unit: string;
  make: string;
  model_year: number;
  status: string;
  terminal: string;
  next_pm_due: string;
  pm_overdue_days: number;
  inspection_days_left: number;
  odometer: number;
}

const LEVEL_STYLE: Record<string, string> = {
  SEVERE: "bg-red-50 text-tp-crit border-red-200",
  ELEVATED: "bg-amber-50 text-tp-risk border-amber-200",
  GUARDED: "bg-yellow-50 text-tp-watch border-yellow-200",
  LOW: "bg-emerald-50 text-tp-ok border-emerald-200",
};

function HosBar({ used, total }: { used: number; total: number }) {
  const f = Math.min(1, used / total);
  const color = f > 0.92 ? "bg-tp-crit" : f > 0.75 ? "bg-tp-risk" : "bg-tp-blue";
  return (
    <span className="block h-1.5 w-full overflow-hidden rounded bg-tp-line">
      <span className={`block h-full ${color}`} style={{ width: `${f * 100}%` }} />
    </span>
  );
}

function BriefPanel({ driver }: { driver: RiskRow }) {
  const [requestedAt, setRequestedAt] = useState(0);
  const [runId, setRunId] = useState<number | null>(null);
  const runs = useLive((s) => s.runs);
  const steps = useLive((s) => (runId ? s.steps[runId] ?? [] : []));

  useEffect(() => {
    setRunId(null);
    setRequestedAt(0);
  }, [driver.driver_id]);

  useEffect(() => {
    if (runId !== null || !requestedAt) return;
    const match = Object.values(runs)
      .filter(
        (r) =>
          r.kind === "safety" &&
          r.subject_id === driver.driver_id &&
          new Date(r.started_at).getTime() >= requestedAt - 4000,
      )
      .sort((a, b) => b.id - a.id)[0];
    if (match) setRunId(match.id);
  }, [runs, runId, requestedAt, driver.driver_id]);

  const output = steps.find((s) => s.kind === "output")?.payload as
    | { risk_level: string; brief_markdown: string; talking_points: string[] }
    | undefined;
  const running = runId !== null && runs[runId]?.status === "RUNNING";

  return (
    <div className="rounded-lg border border-tp-line bg-white">
      <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
        <h3 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
          Coaching brief · {driver.name}
        </h3>
        <button
          disabled={running}
          onClick={() => {
            setRequestedAt(Date.now());
            setRunId(null);
            void api.post(`/api/safety/brief/${driver.driver_id}`);
          }}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-tp-blue px-2.5 py-1.5 text-[11.5px] font-semibold text-white hover:bg-tp-blue-strong disabled:opacity-50"
        >
          <Bot className="h-3.5 w-3.5" />
          {running ? "Writing…" : output ? "Regenerate" : "Generate brief"}
        </button>
      </header>
      <div className="max-h-[300px] overflow-y-auto p-3">
        {!requestedAt && !output && (
          <p className="text-[12px] text-tp-muted">
            The agent reads this driver&apos;s computed risk profile and incident
            history, then writes a manager-ready 5-minute check-in brief.
          </p>
        )}
        {running && (
          <p className="font-mono text-[11.5px] text-tp-blue">
            pulling risk profile → incident history → drafting…
          </p>
        )}
        {output && (
          <div className="space-y-2">
            <span
              className={`inline-block rounded border px-2 py-0.5 text-[11px] font-semibold ${LEVEL_STYLE[output.risk_level]}`}
            >
              agent assessment: {output.risk_level}
            </span>
            <div className="prose prose-sm max-w-none text-[12.5px] leading-relaxed [&_p]:my-1.5">
              <ReactMarkdown>{output.brief_markdown}</ReactMarkdown>
            </div>
            <ul className="space-y-1 rounded bg-tp-bg/70 p-2.5">
              {output.talking_points.map((t, i) => (
                <li key={i} className="flex gap-2 text-[12px]">
                  <span className="tp-num shrink-0 font-semibold text-tp-blue">{i + 1}.</span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SafetyPage() {
  const { data } = useQuery({
    queryKey: ["safety"],
    queryFn: () =>
      api.get<{ drivers: RiskRow[]; equipment: EquipmentRow[] }>("/api/safety/board"),
    refetchInterval: 20000,
  });
  const [selected, setSelected] = useState<string | null>(null);

  const drivers = data?.drivers ?? [];
  const selectedDriver = drivers.find((d) => d.driver_id === selected) ?? drivers[0];
  const equipment = (data?.equipment ?? []).filter(
    (e) => e.pm_overdue_days > 0 || e.inspection_days_left < 30,
  );

  return (
    <AppShell>
      <div className="grid h-full grid-cols-[minmax(500px,3fr)_minmax(380px,2fr)] gap-3 p-3">
        <section className="flex min-h-0 flex-col rounded-lg border border-tp-line bg-white">
          <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
            <ShieldAlert className="h-4 w-4 text-tp-blue" />
            <h1 className="font-heading text-[13px] font-semibold uppercase tracking-[0.14em]">
              Driver risk watchlist
            </h1>
            <span className="text-[11px] text-tp-muted">
              HOS pressure · fatigue signals · violations · incident history
            </span>
          </header>
          <div className="min-h-0 flex-1 overflow-auto">
            <table className="tp-table w-full text-left text-[12px]">
              <thead className="sticky top-0 bg-white shadow-[0_1px_0_var(--tp-line)]">
                <tr>
                  {["Driver", "Risk", "Drive left", "14h window", "Cycle used", "Night %", "Violations", "Incidents"].map(
                    (h) => (
                      <th key={h} className="px-3 py-2">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {drivers.map((d) => (
                  <tr
                    key={d.driver_id}
                    onClick={() => setSelected(d.driver_id)}
                    className={`cursor-pointer border-t border-tp-line/60 hover:bg-tp-bg/60 ${
                      selectedDriver?.driver_id === d.driver_id ? "bg-blue-50/60" : ""
                    }`}
                  >
                    <td className="px-3 py-2">
                      {d.name}
                      <span className="block text-[10.5px] text-tp-muted">
                        {d.terminal} · {d.duty.toLowerCase().replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded border px-1.5 py-0.5 text-[10.5px] font-semibold ${LEVEL_STYLE[d.risk_level]}`}
                      >
                        {d.risk_level} {d.risk_score}
                      </span>
                    </td>
                    <td className="w-28 px-3 py-2">
                      <span className="tp-num text-[11px]">
                        {minutesAsHours(d.factors.drive_min_remaining)}
                      </span>
                      <HosBar used={660 - d.factors.drive_min_remaining} total={660} />
                    </td>
                    <td className="w-28 px-3 py-2">
                      <span className="tp-num text-[11px]">
                        {minutesAsHours(d.factors.window_min_remaining)}
                      </span>
                      <HosBar used={840 - d.factors.window_min_remaining} total={840} />
                    </td>
                    <td className="tp-num px-3 py-2">{d.factors.cycle_used_pct}%</td>
                    <td className="tp-num px-3 py-2">{pct(d.factors.night_driving_share, 0)}</td>
                    <td className="px-3 py-2">
                      {d.factors.active_violations === "none" ? (
                        <span className="text-tp-muted">—</span>
                      ) : (
                        <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-tp-crit">
                          {d.factors.active_violations}
                        </span>
                      )}
                    </td>
                    <td className="tp-num px-3 py-2">
                      {d.factors.incidents_since_2023}
                      {d.factors.preventable_incidents > 0 && (
                        <span className="text-tp-risk"> ({d.factors.preventable_incidents} prev.)</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="flex min-h-0 flex-col gap-3 overflow-y-auto">
          {selectedDriver && <BriefPanel driver={selectedDriver} />}
          <section className="rounded-lg border border-tp-line bg-white">
            <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
              <Wrench className="h-4 w-4 text-tp-blue" />
              <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
                Equipment compliance
              </h2>
            </header>
            <div className="divide-y divide-tp-line/60">
              {equipment.map((e) => (
                <div key={e.truck_id} className="flex items-center gap-3 px-3 py-2 text-[12px]">
                  <span className="font-mono text-[11px]">#{e.unit}</span>
                  <span>
                    {e.make} ’{String(e.model_year).slice(2)}
                    <span className="block text-[10.5px] text-tp-muted">
                      {e.terminal} · {num(e.odometer)} mi
                    </span>
                  </span>
                  <span className="ml-auto text-right">
                    {e.pm_overdue_days > 0 && (
                      <span className="block rounded bg-red-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-tp-crit">
                        PM overdue {e.pm_overdue_days} d
                      </span>
                    )}
                    {e.inspection_days_left < 30 && (
                      <span className="mt-0.5 block rounded bg-amber-50 px-1.5 py-0.5 text-[10.5px] font-semibold text-tp-risk">
                        DOT inspection in {e.inspection_days_left} d
                      </span>
                    )}
                  </span>
                </div>
              ))}
              {equipment.length === 0 && (
                <p className="p-3 text-[12px] text-tp-muted">All equipment within PM and inspection windows.</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
