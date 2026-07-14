"use client";

import {
  FileCheck2,
  LineChart,
  Map as MapIcon,
  Presentation,
  Route,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Operations", icon: MapIcon },
  { href: "/dispatch", label: "Dispatch", icon: Route },
  { href: "/cost", label: "Cost", icon: LineChart },
  { href: "/safety", label: "Safety", icon: ShieldCheck },
  { href: "/billing", label: "Billing", icon: FileCheck2 },
];

export function NavRail() {
  const pathname = usePathname();
  return (
    <nav className="flex w-[76px] shrink-0 flex-col items-center gap-1 bg-tp-navy-800 py-3">
      {ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`flex w-[64px] flex-col items-center gap-1 rounded-md py-2.5 text-[10px] font-medium tracking-wide ${
              active
                ? "bg-tp-blue text-white"
                : "text-white/55 hover:bg-white/5 hover:text-white/90"
            }`}
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </Link>
        );
      })}
      <Link
        href="/deck"
        className={`mt-auto flex w-[64px] flex-col items-center gap-1 rounded-md py-2.5 text-[10px] font-medium tracking-wide ${
          pathname === "/deck"
            ? "bg-tp-blue text-white"
            : "text-white/55 hover:bg-white/5 hover:text-white/90"
        }`}
      >
        <Presentation className="h-[18px] w-[18px]" />
        Deck
      </Link>
    </nav>
  );
}
