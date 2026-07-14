"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, ChevronUp, XIcon } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import type { PendingActionRow } from "@/lib/types";

const KIND_LABEL: Record<string, string> = {
  ASSIGN_DRIVER: "Dispatch assignment",
  SMS_DRIVER: "Driver SMS",
  EMAIL_CUSTOMER: "Customer email",
  MONITOR: "Monitoring plan",
  SEND_INVOICE: "Invoice",
};

function DraftField({
  label,
  value,
  onChange,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.1em] text-tp-muted">
        {label} <span className="normal-case font-normal">(editable)</span>
      </span>
      <textarea
        value={value}
        rows={rows}
        onChange={(e) => onChange(e.target.value)}
        className="w-full resize-y rounded border border-tp-line bg-amber-50/40 p-2 text-[12px] leading-snug focus:border-tp-blue focus:outline-none"
      />
    </label>
  );
}

export function ActionCard({ action }: { action: PendingActionRow }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>(action.draft);

  const decide = useMutation({
    mutationFn: (approve: boolean) =>
      approve
        ? api.post(`/api/actions/${action.id}/approve`, { draft_override: draft })
        : api.post(`/api/actions/${action.id}/dismiss`),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["actions"] }),
  });

  const impact = action.impact as {
    deadhead_miles?: number;
    estimate?: string;
    invoice_total?: number;
    recovered_usd?: number;
    findings?: string[];
    risks?: string[];
  };

  return (
    <article className="rounded-lg border border-tp-line bg-white shadow-sm">
      <header className="flex items-start gap-2 border-b border-tp-line px-3 py-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-tp-blue">
            {KIND_LABEL[action.kind] ?? action.kind} · agent proposal
          </p>
          <h3 className="truncate font-heading text-[13px] font-semibold leading-tight">
            {action.title}
          </h3>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto mt-0.5 shrink-0 rounded p-1 text-tp-muted hover:bg-tp-bg"
          aria-label="Toggle rationale"
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </header>

      <div className="space-y-2.5 px-3 py-2.5">
        <div className="flex flex-wrap gap-1.5 text-[10.5px]">
          {impact.deadhead_miles !== undefined && (
            <span className="rounded bg-tp-bg px-1.5 py-0.5 tp-num">
              deadhead {impact.deadhead_miles} mi
            </span>
          )}
          {impact.invoice_total !== undefined && (
            <span className="rounded bg-tp-bg px-1.5 py-0.5 tp-num">
              total {usd(impact.invoice_total, 2)}
            </span>
          )}
          {impact.recovered_usd !== undefined && impact.recovered_usd > 0 && (
            <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-medium text-tp-ok tp-num">
              +{usd(impact.recovered_usd, 2)} recovered
            </span>
          )}
          {impact.estimate && (
            <span className="rounded bg-tp-bg px-1.5 py-0.5">{impact.estimate}</span>
          )}
          {(impact.findings ?? []).map((f) => (
            <span key={f} className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-tp-risk">
              {f}
            </span>
          ))}
        </div>

        {expanded && (
          <div className="prose prose-sm max-w-none rounded bg-tp-bg/70 p-2 text-[12px] leading-snug [&_p]:my-1 [&_ul]:my-1">
            <ReactMarkdown>{action.rationale}</ReactMarkdown>
          </div>
        )}

        {typeof draft.sms_body === "string" && (
          <DraftField
            label={`SMS to ${(draft.driver_name as string) ?? "driver"}`}
            value={draft.sms_body}
            onChange={(v) => setDraft({ ...draft, sms_body: v })}
          />
        )}
        {typeof draft.email_subject === "string" && (
          <DraftField
            label="Email subject"
            rows={1}
            value={draft.email_subject}
            onChange={(v) => setDraft({ ...draft, email_subject: v })}
          />
        )}
        {typeof draft.email_body === "string" && (
          <DraftField
            label="Email body"
            rows={5}
            value={draft.email_body}
            onChange={(v) => setDraft({ ...draft, email_body: v })}
          />
        )}
      </div>

      <footer className="flex items-center gap-2 border-t border-tp-line px-3 py-2">
        <button
          onClick={() => decide.mutate(false)}
          disabled={decide.isPending}
          className="flex items-center gap-1 rounded-md border border-tp-line px-2.5 py-1.5 text-[12px] font-medium text-tp-muted hover:bg-tp-bg disabled:opacity-50"
        >
          <XIcon className="h-3.5 w-3.5" /> Dismiss
        </button>
        <button
          onClick={() => decide.mutate(true)}
          disabled={decide.isPending}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-tp-blue px-3 py-1.5 text-[12px] font-semibold text-white hover:bg-tp-blue-strong disabled:opacity-50"
        >
          <Check className="h-3.5 w-3.5" />
          {decide.isPending ? "Executing…" : "Approve & execute"}
        </button>
      </footer>
    </article>
  );
}
