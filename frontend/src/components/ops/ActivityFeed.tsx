"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Mail,
  MessageSquareText,
  Truck,
} from "lucide-react";
import { useMemo } from "react";

import { useFeedHistory, useLive } from "@/lib/hooks";
import { hhmm } from "@/lib/format";
import type { FeedItem } from "@/lib/types";

const ICON: Record<string, typeof Truck> = {
  exception: AlertTriangle,
  resolved: CheckCircle2,
  message: MessageSquareText,
  agent_run: Bot,
  action: CheckCircle2,
  invoice: Mail,
};

function tone(item: FeedItem): string {
  if (item.kind === "exception")
    return item.severity === "CRITICAL" ? "text-tp-crit" : "text-tp-risk";
  if (item.kind === "resolved") return "text-tp-ok";
  if (item.kind === "agent_run") return "text-violet-600";
  return "text-tp-muted";
}

export function ActivityFeed() {
  const { data: history } = useFeedHistory();
  const liveFeed = useLive((s) => s.feed);

  const items = useMemo(() => {
    const all = [...liveFeed, ...(history ?? [])];
    const seen = new Set<string>();
    return all
      .filter((i) => {
        const k = `${i.ts}|${i.text}`;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .sort((a, b) => (a.ts < b.ts ? 1 : -1))
      .slice(0, 60);
  }, [liveFeed, history]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ul className="min-h-0 flex-1 space-y-0 overflow-y-auto">
        {items.map((item, i) => {
          const Icon = ICON[item.kind] ?? Truck;
          return (
            <li
              key={`${item.ts}-${i}`}
              className="flex items-start gap-2 border-b border-tp-line/70 px-3 py-2"
            >
              <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${tone(item)}`} />
              <p className="min-w-0 text-[12px] leading-snug">{item.text}</p>
              <span className="tp-num ml-auto shrink-0 text-[10px] text-tp-muted">
                {hhmm(item.ts)}
              </span>
            </li>
          );
        })}
        {items.length === 0 && (
          <p className="p-4 text-[12px] text-tp-muted">
            Quiet so far — the watchdog posts here the moment something needs
            attention.
          </p>
        )}
      </ul>
    </div>
  );
}
