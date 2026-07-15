"use client";

import { Gauge, Pause, Play, RotateCcw, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useLive } from "@/lib/hooks";
import { liveStore } from "@/lib/live";
import type { AiStatus, SimInfo } from "@/lib/types";

const SPEEDS = [10, 30, 120, 300];

export function SimStrip() {
  const sim = useLive((s) => s.sim);
  const ai = useLive((s) => s.ai);
  const connected = useLive((s) => s.connected);
  const [resetting, setResetting] = useState(false);
  const [pendingRunning, setPendingRunning] = useState<boolean | null>(null);
  const [pendingSpeed, setPendingSpeed] = useState<number | null>(null);
  const [pendingAuto, setPendingAuto] = useState(false);

  const displayedRunning = pendingRunning ?? sim?.running ?? false;
  const displayedSpeed = pendingSpeed ?? sim?.speed ?? 30;

  const clock = sim
    ? new Date(sim.sim_now).toLocaleString("en-US", {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "--:--";

  async function setRunning(running: boolean) {
    setPendingRunning(running);
    try {
      const update = await api.post<Pick<SimInfo, "running">>(
        running ? "/api/sim/play" : "/api/sim/pause",
      );
      liveStore.mergeSim(update);
    } catch {
      toast.error(
        `Could not ${running ? "resume" : "pause"} the simulation - is the backend running?`,
      );
    } finally {
      setPendingRunning(null);
    }
  }

  async function setAutoAi(enabled: boolean) {
    setPendingAuto(true);
    try {
      const status = await api.post<AiStatus>("/api/ai/auto", { enabled });
      liveStore.setAi(status);
      toast.success(
        enabled
          ? "Auto-investigate on: the watchdog may run the agent for CRITICAL incidents (max 1/hour)."
          : "Auto-investigate off: the agent runs only when you click investigate.",
      );
    } catch {
      toast.error("Could not update the AI gate - is the backend running?");
    } finally {
      setPendingAuto(false);
    }
  }

  async function setSpeed(speed: number) {
    setPendingSpeed(speed);
    try {
      const update = await api.post<Pick<SimInfo, "speed">>("/api/sim/speed", {
        speed,
      });
      liveStore.mergeSim(update);
    } catch {
      toast.error("Could not change simulation speed - is the backend running?");
    } finally {
      setPendingSpeed(null);
    }
  }

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
        {ai && (
          <button
            aria-label={`Auto-investigate ${ai.auto_enabled ? "on" : "off"}; ${ai.used} of ${ai.cap} Gemini requests used today`}
            title={`${ai.remaining} of ${ai.cap} Gemini requests left today (every real API call is counted; an agent run spends ~5-11). Auto-investigate ${ai.auto_enabled ? "runs the agent on CRITICAL incidents (max 1/hour)" : "is off - the agent runs only on your click"}.`}
            disabled={pendingAuto}
            className={`flex items-center gap-1 rounded px-1.5 py-0.5 disabled:opacity-60 ${
              ai.auto_enabled ? "bg-emerald-400/25" : "bg-white/15"
            } hover:bg-white/25`}
            onClick={() => void setAutoAi(!ai.auto_enabled)}
          >
            <Sparkles className="h-3.5 w-3.5" />
            auto-AI {ai.auto_enabled ? "on" : "off"}
            <span className="tp-num opacity-80">
              {ai.used}/{ai.cap}
            </span>
          </button>
        )}
        <span className="tp-num text-[12px]">{clock}</span>
        <span className="flex items-center gap-1 rounded bg-white/15 px-1.5 py-0.5">
          <Gauge className="h-3.5 w-3.5" />
          <select
            aria-label="Simulation speed"
            className="bg-transparent text-white outline-none [&>option]:text-tp-text"
            disabled={!sim || pendingSpeed !== null}
            value={displayedSpeed}
            onChange={(e) => void setSpeed(Number(e.target.value))}
          >
            {SPEEDS.map((s) => (
              <option key={s} value={s}>
                ×{s}
              </option>
            ))}
          </select>
        </span>
        <button
          aria-label={displayedRunning ? "Pause simulation" : "Resume simulation"}
          aria-busy={pendingRunning !== null}
          disabled={!sim || pendingRunning !== null}
          className="rounded bg-white/15 p-1 hover:bg-white/25 disabled:opacity-60"
          onClick={() => void setRunning(!displayedRunning)}
        >
          {displayedRunning ? (
            <Pause className="h-3.5 w-3.5" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
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
