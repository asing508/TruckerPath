"use client";

import { Signal, X } from "lucide-react";
import { useMemo } from "react";

import { useLive, useMessages } from "@/lib/hooks";
import { hhmm } from "@/lib/format";

export function DriverPhone({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: messages } = useMessages();
  const sim = useLive((s) => s.sim);

  const sms = useMemo(
    () => (messages ?? []).filter((m) => m.channel === "SMS").slice(0, 20),
    [messages],
  );

  if (!open) return null;

  return (
    <aside className="fixed bottom-4 right-4 z-40 w-[320px] overflow-hidden rounded-[26px] border-[6px] border-tp-navy bg-white shadow-2xl">
      <div className="flex items-center justify-between bg-tp-navy px-4 py-2 text-white">
        <span className="tp-num text-[11px]">
          {sim ? hhmm(sim.sim_now) : "--:--"}
        </span>
        <span className="text-[10px] font-medium tracking-wide text-white/70">
          DRIVER HANDSET · SIMULATED
        </span>
        <span className="flex items-center gap-1.5">
          <Signal className="h-3 w-3" />
          <button onClick={onClose} aria-label="Close phone">
            <X className="h-3.5 w-3.5" />
          </button>
        </span>
      </div>
      <div className="flex h-[420px] flex-col gap-2.5 overflow-y-auto bg-[#e9edf1] p-3">
        {sms.length === 0 && (
          <p className="m-auto max-w-[220px] text-center text-[12px] text-tp-muted">
            No dispatch messages yet. Approve an agent action that sends an SMS
            and it lands here — this is what the driver would see.
          </p>
        )}
        {sms.map((m) => (
          <div key={m.id} className="max-w-[86%] self-start">
            <p className="mb-0.5 px-1 text-[10px] font-medium text-tp-muted">
              To {m.to_name} · {hhmm(m.sent_at)}
            </p>
            <div className="rounded-2xl rounded-tl-sm bg-white px-3 py-2 text-[12.5px] leading-snug text-tp-text shadow-sm">
              {m.body}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
