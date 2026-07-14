"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, ExternalLink, FileText } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import { ActionCard } from "@/components/ops/ActionQueue";
import { AppShell } from "@/components/shell/AppShell";
import { api, fileUrl } from "@/lib/api";
import { mdhm, num, usd } from "@/lib/format";
import { useActions, useLive } from "@/lib/hooks";
import type { PacketRow } from "@/lib/types";

interface PacketsResponse {
  packets: PacketRow[];
  kpis: {
    ready: number;
    audited: number;
    invoiced: number;
    avg_days_to_invoice: number | null;
    recovered_usd: number;
  };
}

interface PacketDetail extends PacketRow {
  extraction: Record<string, unknown> | null;
  reconciliation: {
    diffs: { code: string; description: string; amount_usd: number }[];
    invoice_lines: { description: string; amount: number }[];
    invoice_total: number;
    clean: boolean;
  } | null;
  audit_memo: string;
  invoice?: {
    lines: { description: string; amount: number }[];
    total: number;
    status: string;
    sent_at: string;
    days_to_invoice: number;
    pdf: string;
    email_subject: string;
    email_body: string;
  };
}

const STATUS_BADGE: Record<string, string> = {
  READY: "bg-tp-bg text-tp-muted",
  AUDITING: "bg-blue-50 text-tp-blue",
  AUDITED: "bg-amber-50 text-tp-risk",
  INVOICED: "bg-emerald-50 text-tp-ok",
};

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-tp-line bg-white px-3.5 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-tp-muted">{label}</p>
      <p className="tp-num mt-1 font-heading text-[20px] font-semibold leading-none">{value}</p>
      {sub && <p className="mt-1 text-[11px] text-tp-muted">{sub}</p>}
    </div>
  );
}

function PacketDetailPane({ packetId }: { packetId: number }) {
  const { data: packet } = useQuery({
    queryKey: ["packet", packetId],
    queryFn: () => api.get<PacketDetail>(`/api/billing/packets/${packetId}`),
    refetchInterval: 6000,
  });
  const { data: actions } = useActions();
  const auditing = useLive((s) =>
    Object.values(s.runs).some(
      (r) => r.kind === "billing" && r.status === "RUNNING" && r.subject_id === packet?.load_id,
    ),
  );

  const pendingInvoice = useMemo(
    () =>
      (actions ?? []).find(
        (a) =>
          a.kind === "SEND_INVOICE" &&
          a.status === "PENDING" &&
          a.subject_id === String(packetId),
      ),
    [actions, packetId],
  );

  if (!packet) return null;

  return (
    <div className="flex min-h-0 flex-col gap-3 overflow-y-auto pr-0.5">
      <section className="rounded-lg border border-tp-line bg-white">
        <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
          <h2 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
            {packet.load_id} · {packet.customer}
          </h2>
          <span className={`rounded px-1.5 py-0.5 text-[10.5px] font-semibold ${STATUS_BADGE[packet.status]}`}>
            {packet.status}
          </span>
          {packet.status === "READY" && (
            <button
              disabled={auditing}
              onClick={() => void api.post(`/api/billing/packets/${packetId}/audit`)}
              className="ml-auto flex items-center gap-1.5 rounded-md bg-tp-blue px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-tp-blue-strong disabled:opacity-50"
            >
              <Bot className="h-3.5 w-3.5" />
              {auditing ? "Auditing…" : "Run agent audit"}
            </button>
          )}
        </header>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 px-3 py-2 text-[12px]">
          <p><span className="text-tp-muted">Lane · </span>{packet.lane}</p>
          <p><span className="text-tp-muted">Delivered · </span>{mdhm(packet.delivered_at)} ({packet.age_days} d ago)</p>
          <p><span className="text-tp-muted">Quoted revenue · </span><span className="tp-num">{usd(packet.revenue, 2)}</span></p>
          <p><span className="text-tp-muted">Booking · </span>{packet.booking_type}</p>
        </div>
        <div className="flex flex-wrap gap-1.5 border-t border-tp-line px-3 py-2">
          {packet.docs.map((d) => (
            <a
              key={d.filename}
              href={fileUrl(`/api/billing/doc/${packet.load_id}/${d.filename}`)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 rounded border border-tp-line px-2 py-1 text-[11px] font-medium hover:border-tp-blue hover:text-tp-blue"
            >
              <FileText className="h-3 w-3" />
              {d.title}
              <ExternalLink className="h-2.5 w-2.5 opacity-60" />
            </a>
          ))}
        </div>
      </section>

      {auditing && (
        <p className="rounded-lg border border-tp-line bg-white p-3 font-mono text-[11.5px] text-tp-blue">
          Gemini Vision reading documents → reconciling against system of record →
          drafting invoice… follow along in the Agent trace.
        </p>
      )}

      {packet.reconciliation && (
        <section className="rounded-lg border border-tp-line bg-white">
          <header className="border-b border-tp-line px-3 py-2">
            <h3 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
              Reconciliation — documents vs system of record
            </h3>
          </header>
          <div className="p-3">
            {packet.reconciliation.diffs.length === 0 ? (
              <p className="rounded bg-emerald-50 px-2.5 py-1.5 text-[12px] font-medium text-tp-ok">
                Clean packet — documents match the system on rate, weight,
                accessorials, receipts and dock time.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {packet.reconciliation.diffs.map((d) => (
                  <li key={d.code} className="flex items-start gap-2 rounded bg-amber-50/70 px-2.5 py-1.5">
                    <span className="mt-0.5 shrink-0 rounded bg-white px-1.5 py-0.5 font-mono text-[10px] font-semibold text-tp-risk">
                      {d.code}
                    </span>
                    <span className="text-[12px] leading-snug">{d.description}</span>
                    {d.amount_usd > 0 && (
                      <span className="tp-num ml-auto shrink-0 font-semibold text-tp-ok">
                        +{usd(d.amount_usd, 2)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {packet.audit_memo && (
              <details className="mt-2 rounded border border-tp-line bg-tp-bg/60 p-2">
                <summary className="cursor-pointer text-[11px] font-medium text-tp-muted">
                  Agent audit memo
                </summary>
                <div className="prose prose-sm mt-1 max-w-none text-[12px] [&_p]:my-1">
                  <ReactMarkdown>{packet.audit_memo}</ReactMarkdown>
                </div>
              </details>
            )}
          </div>
        </section>
      )}

      {pendingInvoice && <ActionCard action={pendingInvoice} />}

      {packet.invoice && (
        <section className="rounded-lg border border-tp-line bg-white">
          <header className="flex items-center gap-2 border-b border-tp-line px-3 py-2">
            <h3 className="font-heading text-[12px] font-semibold uppercase tracking-[0.14em]">
              Invoice — {packet.invoice.status}
            </h3>
            <span className="text-[11px] text-tp-muted">
              sent {packet.invoice.days_to_invoice} days after delivery
            </span>
            <a
              href={fileUrl(packet.invoice.pdf)}
              target="_blank"
              rel="noreferrer"
              className="ml-auto flex items-center gap-1 rounded border border-tp-line px-2 py-1 text-[11px] font-medium hover:border-tp-blue hover:text-tp-blue"
            >
              <FileText className="h-3 w-3" /> PDF
            </a>
          </header>
          <div className="p-3">
            {packet.invoice.lines.map((l, i) => (
              <p key={i} className="flex justify-between border-b border-tp-line/50 py-1 text-[12px]">
                {l.description}
                <span className="tp-num">{usd(l.amount, 2)}</span>
              </p>
            ))}
            <p className="flex justify-between pt-1.5 text-[13px] font-semibold">
              TOTAL <span className="tp-num">{usd(packet.invoice.total, 2)}</span>
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

export default function BillingPage() {
  const { data } = useQuery({
    queryKey: ["packets"],
    queryFn: () => api.get<PacketsResponse>("/api/billing/packets"),
    refetchInterval: 12000,
  });
  const [selected, setSelected] = useState<number | null>(null);
  const packets = data?.packets ?? [];
  const active = selected ?? packets[0]?.id ?? null;

  return (
    <AppShell>
      <div className="grid h-full grid-rows-[auto_1fr] gap-3 p-3">
        <div className="grid grid-cols-5 gap-2">
          <Tile label="Awaiting audit" value={String(data?.kpis.ready ?? "—")} sub="packets ready" />
          <Tile label="Audited" value={String(data?.kpis.audited ?? "—")} sub="pending your approval" />
          <Tile label="Invoiced" value={String(data?.kpis.invoiced ?? "—")} />
          <Tile
            label="Days to invoice"
            value={data?.kpis.avg_days_to_invoice != null ? String(data.kpis.avg_days_to_invoice) : "—"}
            sub="avg once approved · was ~4-5 manual"
          />
          <Tile label="Recovered" value={usd(data?.kpis.recovered_usd, 2)} sub="missed charges found by audit" />
        </div>

        <div className="grid min-h-0 grid-cols-[minmax(430px,2fr)_minmax(430px,3fr)] gap-3">
          <section className="flex min-h-0 flex-col rounded-lg border border-tp-line bg-white">
            <header className="border-b border-tp-line px-3 py-2">
              <h1 className="font-heading text-[13px] font-semibold uppercase tracking-[0.14em]">
                Delivered load packets
              </h1>
              <p className="text-[11px] text-tp-muted">
                rate con · BOL · POD · fuel receipts, as submitted by drivers
              </p>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {packets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelected(p.id)}
                  className={`block w-full border-b border-tp-line/60 px-3 py-2 text-left hover:bg-tp-bg/60 ${
                    active === p.id ? "bg-blue-50/70" : ""
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-tp-muted">{p.load_id}</span>
                    <span className="truncate text-[12.5px] font-medium">{p.customer}</span>
                    <span className={`ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[p.status]}`}>
                      {p.status}
                    </span>
                  </span>
                  <span className="mt-0.5 flex items-center gap-2 text-[11px] text-tp-muted">
                    <span className="truncate">{p.lane}</span>
                    <span className="tp-num ml-auto shrink-0">{p.age_days} d old</span>
                    <span className="tp-num shrink-0">{num(p.docs.length)} docs</span>
                  </span>
                  {p.findings && p.findings.length > 0 && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {p.findings.map((f) => (
                        <span key={f} className="rounded bg-amber-50 px-1.5 py-0.5 font-mono text-[9.5px] font-semibold text-tp-risk">
                          {f}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>
          {active !== null && <PacketDetailPane packetId={active} />}
        </div>
      </div>
    </AppShell>
  );
}
