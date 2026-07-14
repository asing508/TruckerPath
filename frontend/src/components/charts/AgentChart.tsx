"use client";

import {
  Area,
  AreaChart,
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

import type { ChartSpec } from "@/lib/types";

import { AXIS_TICK, GRID_STROKE, SERIES_COLORS, TOOLTIP_STYLE } from "./theme";

/** Renders the chart spec an agent returned from an "ask your fleet" run. */
export function AgentChart({ spec }: { spec: ChartSpec }) {
  const data = spec.x.map((x, i) => {
    const row: Record<string, string | number> = { x };
    for (const s of spec.series) row[s.name] = s.values[i] ?? 0;
    return row;
  });

  const common = (
    <>
      <CartesianGrid stroke={GRID_STROKE} vertical={false} />
      <XAxis dataKey="x" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: GRID_STROKE }} />
      <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={52} />
      <Tooltip {...TOOLTIP_STYLE} />
      {spec.series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
    </>
  );

  return (
    <figure>
      <figcaption className="mb-1 text-[12px] font-semibold">{spec.title}</figcaption>
      <ResponsiveContainer width="100%" height={240}>
        {spec.type === "bar" ? (
          <BarChart data={data} barCategoryGap="25%">
            {common}
            {spec.series.map((s, i) => (
              <Bar
                key={s.name}
                dataKey={s.name}
                fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        ) : spec.type === "area" ? (
          <AreaChart data={data}>
            {common}
            {spec.series.map((s, i) => (
              <Area
                key={s.name}
                dataKey={s.name}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                fill={SERIES_COLORS[i % SERIES_COLORS.length]}
                fillOpacity={0.14}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        ) : (
          <LineChart data={data}>
            {common}
            {spec.series.map((s, i) => (
              <Line
                key={s.name}
                dataKey={s.name}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </figure>
  );
}
