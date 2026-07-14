"use client";

/* Single SSE connection -> external store. Slices get new references only
   when they change, so useSyncExternalStore subscribers re-render narrowly. */

import { API_URL } from "./api";
import type {
  AgentRunRow,
  AgentStepRow,
  FeedItem,
  SimInfo,
  TruckPos,
} from "./types";

export interface LiveState {
  connected: boolean;
  sim: SimInfo | null;
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

class LiveStore {
  state: LiveState = {
    connected: false,
    sim: null,
    trucks: [],
    feed: [],
    runs: {},
    steps: {},
    lastRunUpdate: 0,
    invalidations: {},
  };
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
    es.addEventListener("tick_control", () => {
      // authoritative values arrive with the next tick
    });
    es.addEventListener("positions", (e) => {
      this.state = { ...this.state, trucks: JSON.parse(e.data).trucks };
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
      ["action", ["actions", "dispatch"]],
      ["message", ["messages"]],
      ["packet", ["packets"]],
      ["world_reset", ["exceptions", "actions", "messages", "packets", "fleet", "dispatch"]],
    ] as const) {
      es.addEventListener(event, () => {
        for (const k of keys) this.bump(k);
        this.emit();
      });
    }
  }
}

export const liveStore = new LiveStore();
