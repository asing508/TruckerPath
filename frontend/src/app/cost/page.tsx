"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, ChevronDown, ChevronRight, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AgentChart } from "@/components/charts/AgentChart";
import {
  AXIS_TICK,
  GRID_STROKE,
  SERIES_COLORS,
  TOOLTIP_STYLE,
} from "@/components/charts/theme";
import { AppShell } from "@/components/shell/AppShell";
import { api } from "@/lib/api";
import { num, pct, usd } from "@/lib/format";
import { useLive } from "@/lib/hooks";
import type { AgentRunRow, ChartSpec } from "@/lib/types";

interface Kpis {
  year: string;
  total_miles: number;
  revenue: number;
  fuel_cost: number;
  maintenance_cost: number;
  cost_per_mile: number | null;
  revenue_per_mile: number | null;
  loads: number;
  on_time_rate: number;
  avg_detention_min: number;
  detention_events_over_2h: number;
  avg_deadhead_miles: number;
}

interface MonthRow {
  month: string;
  miles: number;
  cpm: number | null;
  rpm: number | null;
  fuel_cost: number;
  maintenance_cost: number;
  loads: number;
}

interface CpmRow {
  label: string;
  miles: number;
  revenue: number;
  fuel_cost: number;
  fuel_cpm: number | null;
  rpm: number | null;
  margin_per_mile: number | null;
  on_time_rate: number;
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-tp-line bg-white px-3.5 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-tp-muted">
        {label}
      </p>
      <p className="tp-num mt-1 font-heading text-[20px] font-semibold leading-none">
        {value}
      </p>
      {sub && <p className="mt-1 text-[11px] text-tp-muted">{sub}</p>}
    </div>
  );
}

function AskFleet() {
  const [question, setQuestion] = useState("");
  const [watchingRun, setWatchingRun] = useState<number | null>(null);
  const [askedAt, setAskedAt] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);
  const runs = useLive((s) => s.runs);
  const steps = useLive((s) => (watchingRun ? s.steps[watchingRun] ?? [] : []));
  const scrollRef = useRef<HTMLDivElement>(null);

  // adopt the newest analyst run started after our ask
  useEffect(() => {
    if (watchingRun !== null) return;
    const candidates = Object.values(runs).filter(
      (r) => r.kind === "analyst" && new Date(r.started_at).getTime() >= askedAt - 4000,
    );
    if (askedAt && candidates.length > 0) {
      setWatchingRun(candidates.sort((a, b) => b.id - a.id)[0].id);
    }
  }, [runs, askedAt, watchingRun]);

  const run: AgentRunRow | undefined = watchingRun ? runs[watchingRun] : undefined;
  const output = steps.find((s) => s.kind === "output")?.payload as
    | { answer_markdown: string; sql_used?: string; chart?: ChartSpec }
    | undefined;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [steps.length]);

  const EXAMPLES = [
    "Which 5 drivers have the best margin per mile this year?",
    "How did diesel price per gallon trend by month in 2024?",
    "Which customers cause the most detention over 2 hours?",
  ];

  const busy = submitting || run?.status === "RUNNING";

  async function ask(q: string) {
    setWatchingRun(null);
    setAskedAt(Date.now());
    setSubmitting(true);
    try {
      const res = await api.post<{ error?: string }>("/api/analytics/ask", { question: q });
      if (res.error) toast.error(res.error);
    } catch {
      toast.error("Could not reach the analyst agent - try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="flex min-h-0 flex-col rounded-lg border border-tp-line bg-white">
      <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
        <Bot className="h-4 w-4 text-tp-blue" />
        <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
          Ask your fleet
        </h2>
        <span className="text-[11px] text-tp-muted">
          plain English → guarded SQL over 3 years of operations
        </span>
      </header>

      <form
        className="flex gap-2 border-b border-tp-line p-2.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (!question.trim() || busy) return;
          void ask(question);
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
          placeholder="e.g. What did detention cost us by customer last quarter?"
          className="min-w-0 flex-1 rounded-md border border-tp-line px-3 py-2 text-[13px] focus:border-tp-blue focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="flex items-center gap-1.5 rounded-md bg-tp-blue px-3.5 py-2 text-[12px] font-semibold text-white hover:bg-tp-blue-strong disabled:opacity-50"
        >
          <Send className="h-3.5 w-3.5" /> {busy ? "Working…" : "Ask"}
        </button>
      </form>

      {!askedAt && (
        <div className="flex flex-wrap gap-1.5 p-2.5">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              disabled={busy}
              onClick={() => setQuestion(q)}
              className="rounded-full border border-tp-line px-2.5 py-1 text-[11px] text-tp-muted hover:border-tp-blue hover:text-tp-blue disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {askedAt > 0 && (
        <div className="min-h-0 flex-1 overflow-y-auto p-3" ref={scrollRef}>
          <div className="mb-2 space-y-0.5">
            {steps
              .filter((s) => s.kind === "tool_call")
              .map((s) => (
                <p key={s.seq} className="font-mono text-[11px] text-tp-muted">
                  <ChevronRight className="mr-1 inline h-3 w-3 text-tp-blue" />
                  {s.name}
                  {s.name === "run_sql" &&
                    `: ${String((s.payload as { sql?: string })?.sql ?? "").slice(0, 110)}…`}
                </p>
              ))}
            {run?.status === "RUNNING" && (
              <p className="font-mono text-[11px] text-tp-blue">agent working…</p>
            )}
            {run?.status === "FAILED" && (
              <p className="font-mono text-[11px] text-tp-crit">
                run failed — likely free-tier quota; try again in a minute
              </p>
            )}
          </div>
          {output && (
            <div className="space-y-3">
              <div className="prose prose-sm max-w-none text-[13px] leading-relaxed [&_p]:my-1.5 [&_table]:text-[12px]">
                <ReactMarkdown>{output.answer_markdown}</ReactMarkdown>
              </div>
              {output.chart && <AgentChart spec={output.chart} />}
              {output.sql_used && (
                <details className="rounded border border-tp-line bg-tp-bg/60 p-2">
                  <summary className="cursor-pointer text-[11px] font-medium text-tp-muted">
                    SQL the agent ran
                  </summary>
                  <pre className="mt-1 overflow-x-auto font-mono text-[11px]">{output.sql_used}</pre>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default function CostPage() {
  const [by, setBy] = useState<"driver" | "lane" | "customer">("lane");
  const { data: kpis } = useQuery({
    queryKey: ["kpis"],
    queryFn: () => api.get<Kpis>("/api/analytics/kpis?year=2024"),
  });
  const { data: monthly } = useQuery({
    queryKey: ["monthly"],
    queryFn: () => api.get<MonthRow[]>("/api/analytics/monthly"),
  });
  const { data: cpmRows } = useQuery({
    queryKey: ["cpm", by],
    queryFn: () => api.get<CpmRow[]>(`/api/analytics/cpm?by=${by}&year=2024`),
  });

  const trend = useMemo(
    () =>
      (monthly ?? []).map((m) => ({
        month: m.month.slice(2),
        "Revenue / mi": m.rpm,
        "Op. cost / mi": m.cpm,
      })),
    [monthly],
  );

  return (
    <AppShell>
      <div className="grid h-full grid-rows-[auto_1fr] gap-3 p-3">
        <div className="grid grid-cols-3 gap-2 lg:grid-cols-6">
          <Tile
            label="Op. cost / mile 2024"
            value={kpis?.cost_per_mile != null ? `$${kpis.cost_per_mile.toFixed(3)}` : "—"}
            sub="fuel + maintenance"
          />
          <Tile
            label="Revenue / mile"
            value={kpis?.revenue_per_mile != null ? `$${kpis.revenue_per_mile.toFixed(3)}` : "—"}
            sub={`${num(kpis?.loads)} loads`}
          />
          <Tile label="On-time" value={pct(kpis?.on_time_rate)} sub="deliveries 2024" />
          <Tile
            label="Avg detention"
            value={`${num(kpis?.avg_detention_min)} min`}
            sub={`${num(kpis?.detention_events_over_2h)} events > 2 h`}
          />
          <Tile
            label="Avg deadhead"
            value={`${num(kpis?.avg_deadhead_miles)} mi`}
            sub="repositioning estimate"
          />
          <Tile label="Fuel spend" value={usd(kpis?.fuel_cost)} sub={`maint ${usd(kpis?.maintenance_cost)}`} />
        </div>

        <div className="grid min-h-0 grid-cols-2 gap-3">
          <div className="flex min-h-0 flex-col gap-3">
            <section className="rounded-lg border border-tp-line bg-white p-3">
              <h2 className="mb-1 font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
                Margin per mile — 36 months
              </h2>
              <ResponsiveContainer width="100%" height={190}>
                <LineChart data={trend}>
                  <CartesianGrid stroke={GRID_STROKE} vertical={false} />
                  <XAxis dataKey="month" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: GRID_STROKE }} interval={5} />
                  <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44}
                    domain={["auto", "auto"]} tickFormatter={(v: number) => `$${v.toFixed(1)}`} />
                  <Tooltip {...TOOLTIP_STYLE} formatter={(v) => `$${Number(v).toFixed(3)}/mi`} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line dataKey="Revenue / mi" stroke={SERIES_COLORS[0]} strokeWidth={2} dot={false} />
                  <Line dataKey="Op. cost / mi" stroke={SERIES_COLORS[1]} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </section>

            <section className="flex min-h-0 flex-1 flex-col rounded-lg border border-tp-line bg-white p-3">
              <div className="mb-2 flex items-center gap-2">
                <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
                  Fuel cost per mile
                </h2>
                <div className="ml-auto flex rounded-md border border-tp-line p-0.5">
                  {(["lane", "driver", "customer"] as const).map((k) => (
                    <button
                      key={k}
                      onClick={() => setBy(k)}
                      className={`rounded px-2 py-0.5 text-[11px] font-medium capitalize ${
                        by === k ? "bg-tp-blue text-white" : "text-tp-muted hover:text-tp-text"
                      }`}
                    >
                      by {k}
                    </button>
                  ))}
                </div>
              </div>
              <div className="min-h-0 flex-1">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={cpmRows ?? []} layout="vertical" barCategoryGap="22%">
                    <CartesianGrid stroke={GRID_STROKE} horizontal={false} />
                    <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false}
                      tickFormatter={(v: number) => `$${v.toFixed(2)}`} />
                    <YAxis type="category" dataKey="label" width={168}
                      tick={{ ...AXIS_TICK, fontSize: 10 }} tickLine={false} axisLine={false} />
                    <Tooltip
                      {...TOOLTIP_STYLE}
                      formatter={(v, name) =>
                        name === "fuel_cpm" ? [`$${Number(v).toFixed(3)}/mi`, "fuel cost/mi"] : [v, name]}
                    />
                    <Bar dataKey="fuel_cpm" fill={SERIES_COLORS[0]} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>

          <AskFleet />
        </div>
      </div>
    </AppShell>
  );
}
