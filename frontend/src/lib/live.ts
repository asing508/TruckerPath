"use client";

/* Single SSE connection -> immutable external-store snapshots. */

import { toast } from "sonner";

import { API_URL } from "./api";
import type {
  AgentRunRow,
  AgentStepRow,
  AiStatus,
  FeedItem,
  SimInfo,
  TruckPos,
} from "./types";

export interface LiveState {
  connected: boolean;
  sim: SimInfo | null;
  ai: AiStatus | null;
  trucks: TruckPos[];
  feed: FeedItem[];
  runs: Record<number, AgentRunRow>;
  steps: Record<number, AgentStepRow[]>;
  lastRunUpdate: number;
  invalidations: Record<string, number>; // queryKey -> version
}

type Listener = () => void;

const FEED_CAP = 120;
const STEP_CAP = 160;

const INITIAL_STATE: LiveState = {
  connected: false,
  sim: null,
  ai: null,
  trucks: [],
  feed: [],
  runs: {},
  steps: {},
  lastRunUpdate: 0,
  invalidations: {},
};

class LiveStore {
  state: LiveState = INITIAL_STATE;
  private listeners = new Set<Listener>();
  private source: EventSource | null = null;

  subscribe = (fn: Listener) => {
    this.listeners.add(fn);
    this.ensureConnected();
    return () => {
      this.listeners.delete(fn);
    };
  };

  getSnapshot = () => this.state;
  getServerSnapshot = () => INITIAL_STATE;

  private emit() {
    for (const fn of this.listeners) fn();
  }

  private bump(key: string) {
    this.state = {
      ...this.state,
      invalidations: {
        ...this.state.invalidations,
        [key]: (this.state.invalidations[key] ?? 0) + 1,
      },
    };
  }

  setAi = (ai: AiStatus) => {
    this.state = { ...this.state, ai };
    this.emit();
  };

  mergeSim = (patch: Partial<SimInfo>) => {
    const current = this.state.sim;
    if (
      !current &&
      (typeof patch.sim_now !== "string" ||
        typeof patch.speed !== "number" ||
        typeof patch.running !== "boolean")
    ) {
      return;
    }
    const sim = { ...current, ...patch } as SimInfo;
    if (
      current &&
      sim.sim_now === current.sim_now &&
      sim.speed === current.speed &&
      sim.running === current.running &&
      sim.t0 === current.t0
    ) {
      return;
    }
    this.state = { ...this.state, sim };
    this.emit();
  };

  ensureConnected() {
    if (this.source || typeof window === "undefined") return;
    const es = new EventSource(`${API_URL}/api/stream`);
    this.source = es;
    es.onopen = () => {
      this.state = { ...this.state, connected: true };
      this.emit();
    };
    es.onerror = () => {
      this.state = { ...this.state, connected: false };
      this.emit();
    };

    es.addEventListener("tick", (e) => {
      this.state = { ...this.state, sim: JSON.parse(e.data) };
      this.emit();
    });
    es.addEventListener("tick_control", (e) => {
      this.mergeSim(JSON.parse(e.data) as Partial<SimInfo>);
    });
    es.addEventListener("ai_status", (e) => {
      this.setAi(JSON.parse(e.data) as AiStatus);
    });
    es.addEventListener("ai_denied", (e) => {
      const { reason } = JSON.parse(e.data) as { reason: string };
      toast.warning(`AI run refused: ${reason}`);
    });
    es.addEventListener("positions", (e) => {
      this.state = { ...this.state, trucks: JSON.parse(e.data).trucks };
      this.bump("fleet");
      this.bump("safety");
      this.emit();
    });
    es.addEventListener("feed", (e) => {
      const item: FeedItem = JSON.parse(e.data);
      this.state = {
        ...this.state,
        feed: [item, ...this.state.feed].slice(0, FEED_CAP),
      };
      this.bump("exceptions");
      this.emit();
    });
    es.addEventListener("agent_run", (e) => {
      const run = JSON.parse(e.data) as AgentRunRow;
      const prev = this.state.runs[run.id] ?? {};
      this.state = {
        ...this.state,
        runs: { ...this.state.runs, [run.id]: { ...prev, ...run } },
        lastRunUpdate: Date.now(),
      };
      this.emit();
    });
    es.addEventListener("agent_step", (e) => {
      const step = JSON.parse(e.data) as AgentStepRow & { run_id: number };
      const arr = this.state.steps[step.run_id] ?? [];
      this.state = {
        ...this.state,
        steps: {
          ...this.state.steps,
          [step.run_id]: [...arr, step].slice(-STEP_CAP),
        },
        lastRunUpdate: Date.now(),
      };
      this.emit();
    });
    for (const [event, keys] of [
      ["exception", ["exceptions", "fleet"]],
      ["action", ["actions", "dispatch", "candidates", "fleet"]],
      ["message", ["messages"]],
      ["packet", ["packets", "packet"]],
      [
        "world_reset",
        [
          "exceptions",
          "actions",
          "messages",
          "packets",
          "packet",
          "fleet",
          "dispatch",
          "candidates",
          "safety",
        ],
      ],
    ] as const) {
      es.addEventListener(event, () => {
        for (const k of keys) this.bump(k);
        this.emit();
      });
    }
  }
}

export const liveStore = new LiveStore();
