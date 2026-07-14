"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { DriverPhone } from "@/components/ops/DriverPhone";
import { TraceDrawer } from "@/components/trace/TraceDrawer";
import { Toaster } from "@/components/ui/sonner";

import { NavRail } from "./NavRail";
import { SimStrip } from "./SimStrip";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const pathname = usePathname();

  if (pathname === "/deck") {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar
        onTogglePhone={() => setPhoneOpen((v) => !v)}
        onToggleTrace={() => setTraceOpen((v) => !v)}
        traceOpen={traceOpen}
      />
      <SimStrip />
      <div className="flex min-h-0 flex-1">
        <NavRail />
        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
      {traceOpen && <TraceDrawer onClose={() => setTraceOpen(false)} />}
      <DriverPhone open={phoneOpen} onClose={() => setPhoneOpen(false)} />
      <Toaster position="bottom-right" richColors />
    </div>
  );
}
