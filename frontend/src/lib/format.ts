export const usd = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined
    ? "—"
    : n.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });

export const num = (n: number | null | undefined, digits = 0) =>
  n === null || n === undefined
    ? "—"
    : n.toLocaleString("en-US", { maximumFractionDigits: digits });

export const pct = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? "—" : `${(n * 100).toFixed(digits)}%`;

export const hhmm = (iso: string | null | undefined) =>
  iso
    ? new Date(iso).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";

export const mdhm = (iso: string | null | undefined) =>
  iso
    ? new Date(iso).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";

export const minutesAsHours = (min: number | null | undefined) =>
  min === null || min === undefined ? "—" : `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}m`;
