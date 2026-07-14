"use client";

import { Gauge, Pause, Play, RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useLive } from "@/lib/hooks";

const SPEEDS = [10, 30, 120, 300];

export function SimStrip() {
  const sim = useLive((s) => s.sim);
  const connected = useLive((s) => s.connected);
  const [resetting, setResetting] = useState(false);

  const clock = sim
    ? new Date(sim.sim_now).toLocaleString("en-US", {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "--:--";

  return (
    <div className="flex h-9 items-center gap-4 bg-tp-banner px-4 text-[12px] font-medium text-white">
      <span className="font-heading font-semibold tracking-wide">
        LIVE SIMULATION
      </span>
      <span className="hidden items-center gap-1.5 sm:flex">
        <span
          className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-300" : "bg-red-300"}`}
        />
        {connected ? "telemetry stream connected" : "reconnecting…"}
      </span>
      <span className="ml-auto flex items-center gap-3">
        <span className="tp-num text-[12px]">{clock}</span>
        <span className="flex items-center gap-1 rounded bg-white/15 px-1.5 py-0.5">
          <Gauge className="h-3.5 w-3.5" />
          <select
            aria-label="Simulation speed"
            className="bg-transparent text-white outline-none [&>option]:text-tp-text"
            value={sim?.speed ?? 30}
            onChange={(e) => void api.post("/api/sim/speed", { speed: Number(e.target.value) })}
          >
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                ×{s}
              </option>
            ))}
          </select>
        </span>
        <button
          aria-label={sim?.running ? "Pause simulation" : "Resume simulation"}
          className="rounded bg-white/15 p-1 hover:bg-white/25"
          onClick={() =>
            void api.post(sim?.running ? "/api/sim/pause" : "/api/sim/play")
          }
        >
          {sim?.running ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
        </button>
        <button
          aria-label="Reset world"
          disabled={resetting}
          className="flex items-center gap-1 rounded bg-white/15 px-1.5 py-1 hover:bg-white/25 disabled:opacity-50"
          onClick={async () => {
            setResetting(true);
            try {
              await api.post("/api/sim/reset");
              window.location.reload();
            } catch {
              toast.error("Reset failed - is the backend still running?");
              setResetting(false);
            }
          }}
        >
          <RotateCcw className={`h-3.5 w-3.5 ${resetting ? "animate-spin" : ""}`} />
          {resetting ? "resetting…" : "reset demo"}
        </button>
      </span>
    </div>
  );
}
