"use client";

import { Smartphone, TerminalSquare } from "lucide-react";

import { useLive } from "@/lib/hooks";

function TPLogo() {
  /* Trucker Path mark: white rounded square with road cut */
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid h-7 w-7 place-items-center rounded-[6px] bg-white">
        <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
          <rect x="2" y="2" width="20" height="20" rx="3" fill="#10151d" />
          <path d="M9 22 L11 2 h2 L15 22 Z" fill="#fff" />
          <path
            d="M12 4 v2.4 M12 9 v2.4 M12 14 v2.4 M12 19 v2.4"
            stroke="#10151d"
            strokeWidth="1.4"
          />
        </svg>
      </span>
      <span className="font-heading text-[15px] font-bold uppercase tracking-[0.14em] text-white">
        Trucker Path
      </span>
    </span>
  );
}

export function TopBar({
  onTogglePhone,
  onToggleTrace,
  traceOpen,
}: {
  onTogglePhone: () => void;
  onToggleTrace: () => void;
  traceOpen: boolean;
}) {
  const running = useLive((s) => Object.values(s.runs).some((r) => r.status === "RUNNING"));

  return (
    <header className="flex h-14 items-center gap-4 bg-tp-navy px-4">
      <TPLogo />
      <span className="mt-0.5 hidden border-l border-white/20 pl-4 font-heading text-[13px] font-semibold uppercase tracking-[0.18em] text-tp-blue sm:block">
        Fleet Copilot
      </span>
      <span className="ml-auto hidden text-[12px] text-white/60 md:block">
        Sunbelt Carriers · Dallas / Houston / OKC · 14 trucks
      </span>
      <button
        onClick={onTogglePhone}
        className="flex items-center gap-1.5 rounded-md border border-white/15 px-2.5 py-1.5 text-[12px] font-medium text-white/85 hover:bg-white/10"
      >
        <Smartphone className="h-3.5 w-3.5" />
        Driver phone
      </button>
      <button
        onClick={onToggleTrace}
        className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[12px] font-medium ${
          traceOpen
            ? "border-tp-blue bg-tp-blue text-white"
            : "border-white/15 text-white/85 hover:bg-white/10"
        }`}
      >
        <TerminalSquare className="h-3.5 w-3.5" />
        Agent trace
        {running && (
          <span className="ml-1 h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
        )}
      </button>
    </header>
  );
}
