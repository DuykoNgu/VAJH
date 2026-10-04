"use client";
// Giám sát agent + LLM: số liệu tổng hợp, danh sách trace, dòng thời gian từng trace (agent → lượt gọi LLM), chấm điểm.
import { Fragment, useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";

type Summary = components["schemas"]["Summary"];
type TraceRow = components["schemas"]["TraceRow"];
type TraceDetail = components["schemas"]["TraceDetail"];
type Span = components["schemas"]["SpanOut"];
type RouteConfig = components["schemas"]["RouteConfig"];

const KIND = { lesson_start: "Vào bài", turn: "Lượt học", preview: "Nghe thử", ingest: "Nạp sách" } as const;
const button = "rounded-lg border-2 px-3 py-1 focus:outline-4 disabled:opacity-50";
const ms = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);
const num = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("vi-VN"));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
const time = (iso: string) => new Date(iso).toLocaleString("vi-VN");

function Table({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full border-collapse text-left text-base">
      <caption className="text-left text-xl font-semibold">{caption}</caption>
      <thead>
        <tr className="border-b-2">{head.map((h) => <th key={h} scope="col" className="p-2">{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.length === 0 && <tr><td className="p-2" colSpan={head.length}>Chưa có dữ liệu.</td></tr>}
        {rows.map((r) => (
          <tr key={String(r[0])} className="border-b">
            {r.map((c, i) => (i === 0 ? <th key={i} scope="row" className="p-2">{c}</th> : <td key={i} className="p-2">{c}</td>))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type SpanNode = Omit<Span, "parent_seq"> & { children: SpanNode[] };

/** Trace dạng JSON dễ đọc: span con (lượt gọi LLM) nằm trong `children` của span cha (agent). */
function nested(trace: TraceDetail) {
  const nodes = new Map<number, SpanNode>();
  const roots: SpanNode[] = [];
  for (const { parent_seq, ...rest } of trace.spans) {
    const node: SpanNode = { ...rest, children: [] };
    nodes.set(rest.seq, node);
    (parent_seq === null ? roots : nodes.get(parent_seq)!.children).push(node);
  }
  const { spans: _spans, ...head } = trace; // eslint-disable-line @typescript-eslint/no-unused-vars
  return { ...head, spans: roots };
}

function SpanDetail({ span }: { span: Span }) {
  const d = span.detail as Record<string, unknown>;
  const block = (label: string, value: unknown) =>
    value === undefined || value === null || value === "" ? null : (
      <div key={label}>
        <p className="font-semibold">{label}</p>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded bg-gray-100 p-2 text-sm">
          {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
        </pre>
      </div>
    );
  const payload = d.payload === "omitted" ? "Không lưu nội dung (lượt thành công không nằm trong mẫu) — chỉ giữ số liệu."
    : d.payload === "purged" ? "Nội dung đã được xoá theo thời hạn lưu — chỉ giữ số liệu." : null;
  return (
    <div className="flex flex-col gap-2 p-2">
      {payload && <p className="italic">{payload}</p>}
      {span.kind === "llm" ? [
        block("Lỗi", d.error), block("Từ chối", d.refusal), block("System prompt", d.system),
        block("Schema", d.schema),
        ...((d.messages as { role: string; content: string }[] | undefined) ?? []).map((m, i) =>
          block(`Tin nhắn ${i + 1} (${m.role})`, m.content)),
        block("Câu trả lời của LLM", d.response),
      ] : [
        block("Lỗi", d.error), block("Chế độ", d.mode), block("Đầu vào", d.input),
        block("Đoạn SGK nhận vào (chunk id)", (d.evidence as number[] | undefined)?.length ? d.evidence : null),
        block("Đầu ra", d.output), block("Chuyển tiếp (handoff)", d.handoff),
        block("Trích dẫn (chunk id)", (d.citations as number[] | undefined)?.length ? d.citations : null),
      ]}
    </div>
  );
}

function TraceView({ trace, onRated }: { trace: TraceDetail; onRated: (t: TraceDetail) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const [view, setView] = useState<"timeline" | "json">("timeline");
  const json = JSON.stringify(nested(trace), null, 2);

  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `trace-${trace.id}.json` });
    link.click();
    URL.revokeObjectURL(url);
  }
  const [note, setNote] = useState(trace.note ?? "");
  const depth = (s: Span): number => (s.parent_seq === null ? 0 : 1 + depth(trace.spans[s.parent_seq]));
  const total = Math.max(trace.duration_ms, 1);

  async function rate(rating: -1 | 1 | null) {
    onRated(await api<TraceDetail>(`/monitor/traces/${trace.id}/rating`, {
      method: "POST", body: JSON.stringify({ rating, note }),
    }));
  }

  return (
    <section aria-labelledby="chi-tiet-trace" className="flex flex-col gap-3 rounded-lg border-2 p-4">
      <h2 id="chi-tiet-trace" className="text-2xl font-semibold">
        {KIND[trace.kind as keyof typeof KIND] ?? trace.kind} — {ms(trace.duration_ms)} —{" "}
        {trace.status === "ok" ? "thành công" : "LỖI"}
      </h2>
      <p className="text-base">{time(trace.started_at)} · {trace.llm_calls} lượt LLM · token vào {num(trace.input_tokens)} / ra {num(trace.output_tokens)} · <code>{trace.id}</code></p>
      {trace.error && <p className="font-semibold text-red-700">Lỗi: {trace.error}</p>}
      {trace.input && <p><span className="font-semibold">Đầu vào:</span> {trace.input}</p>}
      {trace.output && <p><span className="font-semibold">Đầu ra:</span> {trace.output}</p>}

      <div className="flex flex-wrap items-end gap-2 rounded border p-2">
        <span className="font-semibold">Đánh giá:</span>
        <button className={`${button} ${trace.rating === 1 ? "bg-green-100" : ""}`} aria-pressed={trace.rating === 1}
                onClick={() => rate(trace.rating === 1 ? null : 1)}>👍 Tốt</button>
        <button className={`${button} ${trace.rating === -1 ? "bg-red-100" : ""}`} aria-pressed={trace.rating === -1}
                onClick={() => rate(trace.rating === -1 ? null : -1)}>👎 Chưa tốt</button>
        <label className="flex grow flex-col text-base">Ghi chú
          <input className="rounded border-2 p-1" value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="vd. giảng sai dấu, câu hỏi khó hiểu…" />
        </label>
        <button className={button} onClick={() => rate((trace.rating ?? null) as -1 | 1 | null)}>Lưu ghi chú</button>
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Cách xem trace">
        <button className={`${button} ${view === "timeline" ? "bg-gray-200 font-semibold" : ""}`} aria-pressed={view === "timeline"}
                onClick={() => setView("timeline")}>Dòng thời gian</button>
        <button className={`${button} ${view === "json" ? "bg-gray-200 font-semibold" : ""}`} aria-pressed={view === "json"}
                onClick={() => setView("json")}>JSON</button>
        <button className={button} onClick={() => navigator.clipboard.writeText(json)}>Sao chép JSON</button>
        <button className={button} onClick={download}>Tải trace-….json</button>
      </div>

      {view === "json" ? (
        <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded bg-gray-100 p-3 text-sm">{json}</pre>
      ) : (<>
      <h3 className="text-xl font-semibold">Dòng thời gian ({trace.spans.length} bước)</h3>
      <ul className="flex flex-col gap-1">
        {trace.spans.map((s) => (
          <li key={s.seq} className="rounded border">
            <button className="flex w-full items-center gap-2 p-1 text-left text-base focus:outline-4"
                    aria-expanded={open === s.seq} onClick={() => setOpen(open === s.seq ? null : s.seq)}>
              <span style={{ paddingLeft: `${depth(s) * 1.5}rem` }} className="w-72 shrink-0 truncate">
                {s.kind === "agent" ? "🤖" : "🧠"} {s.name}
                {s.kind === "llm" && <span className="text-gray-600"> · {s.model} ({s.effort})</span>}
              </span>
              <span className="relative h-4 grow rounded bg-gray-100" aria-hidden="true">
                <span className={`absolute h-4 rounded ${s.status === "ok" ? (s.kind === "llm" ? "bg-sky-500" : "bg-violet-400") : "bg-red-500"}`}
                      style={{ left: `${(s.offset_ms / total) * 100}%`, width: `${Math.max((s.duration_ms / total) * 100, 0.5)}%` }} />
              </span>
              <span className="w-56 shrink-0 text-right">
                {ms(s.duration_ms)}
                {s.kind === "llm" && ` · ${num(s.input_tokens)}→${num(s.output_tokens)}`}
                {s.status !== "ok" && ` · ${s.status === "error" ? "LỖI" : "từ chối"}`}
              </span>
            </button>
            {open === s.seq && <SpanDetail span={s} />}
          </li>
        ))}
      </ul>
      </>)}
    </section>
  );
}

export default function MonitorApp() {
  const [hours, setHours] = useState(24);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [routes, setRoutes] = useState<RouteConfig[]>([]);
  const [traces, setTraces] = useState<TraceRow[]>([]);
  const [filter, setFilter] = useState({ kind: "", status: "", rated: "", order: "recent" });
  const [selected, setSelected] = useState<TraceDetail | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const query = new URLSearchParams(Object.entries(filter).filter(([, v]) => v));
    try {
      const [s, t] = await Promise.all([api<Summary>(`/monitor/summary?hours=${hours}`), api<TraceRow[]>(`/monitor/traces?${query}`)]);
      setSummary(s);
      setTraces(t);
      setMessage("");
    } catch {
      setMessage("Không tải được số liệu giám sát.");
    }
  }, [hours, filter]);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const timer = setInterval(load, 10000); // tự làm mới mỗi 10 giây
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  useEffect(() => {
    api<RouteConfig[]>("/monitor/routes").then(setRoutes).catch(() => undefined);
  }, []);

  async function open(id: string) {
    setSelected(await api<TraceDetail>(`/monitor/traces/${id}`));
    requestAnimationFrame(() => document.getElementById("chi-tiet-trace")?.scrollIntoView({ behavior: "smooth" }));
  }

  const q = summary?.quality;
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6 text-lg">
      <h1 className="text-3xl font-bold">Giám sát agent và LLM</h1>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2">Khoảng thời gian
          <select className="rounded border-2 p-1" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={1}>1 giờ</option><option value={24}>24 giờ</option><option value={168}>7 ngày</option>
          </select>
        </label>
        <button className={button} onClick={load}>Làm mới</button>
        <span className="text-base text-gray-600">Tự làm mới mỗi 10 giây</span>
        <p role="status" aria-live="polite">{message}</p>
      </div>

      {summary && q && (
        <section aria-label="Tổng quan" className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["Lượt học", num(q.turns)],
            ["Trả lời “không có trong SGK”", pct(q.not_found_rate)],
            ["Điểm TB câu kiểm tra", q.average_score === null || q.average_score === undefined ? "—" : `${(q.average_score * 10).toFixed(1)}/10 (${q.check_answers} câu)`],
            ["Đánh giá 👍 / 👎", `${q.thumbs_up} / ${q.thumbs_down}`],
            ["Lượt LLM", num(summary.routes.reduce((a, r) => a + r.calls, 0))],
            ["Token vào / ra", `${num(summary.routes.reduce((a, r) => a + r.input_tokens, 0))} / ${num(summary.routes.reduce((a, r) => a + r.output_tokens, 0))}`],
            ["Lỗi + từ chối LLM", num(summary.routes.reduce((a, r) => a + r.errors + r.refusals, 0))],
            ["Chi phí ước tính", summary.estimated_cost_usd === null || summary.estimated_cost_usd === undefined ? "đặt LLM_PRICE_*" : `$${summary.estimated_cost_usd}`],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border-2 p-3">
              <p className="text-base">{label}</p>
              <p className="text-2xl font-bold">{value}</p>
            </div>
          ))}
        </section>
      )}

      {summary && (
        <div className="flex flex-col gap-6">
          <Table caption="Theo loại trace" head={["Loại", "Số lượt", "Lỗi", "p50", "p95"]}
                 rows={summary.kinds.map((k) => [KIND[k.kind as keyof typeof KIND] ?? k.kind, k.count, k.errors, ms(k.p50_ms), ms(k.p95_ms)])} />
          <Table caption="Theo agent" head={["Agent", "Số lần chạy", "Lỗi", "p50", "p95"]}
                 rows={summary.agents.map((a) => [a.agent, a.runs, a.errors, ms(a.p50_ms), ms(a.p95_ms)])} />
          <Table caption="Theo route LLM" head={["Route", "Model (effort)", "Lượt", "Lỗi", "Từ chối", "p50", "p95", "Token vào", "Token ra"]}
                 rows={summary.routes.map((r) => {
                   const cfg = routes.find((c) => c.route === r.route);
                   return [r.route, cfg ? `${cfg.model} (${cfg.effort})` : "—", r.calls, r.errors, r.refusals, ms(r.p50_ms), ms(r.p95_ms), num(r.input_tokens), num(r.output_tokens)];
                 })} />
        </div>
      )}

      <section aria-labelledby="ds-trace" className="flex flex-col gap-3">
        <h2 id="ds-trace" className="text-2xl font-semibold">Trace gần đây</h2>
        <div className="flex flex-wrap gap-3 text-base">
          {([
            ["kind", "Loại", [["", "Tất cả"], ...Object.entries(KIND)]],
            ["status", "Trạng thái", [["", "Tất cả"], ["ok", "Thành công"], ["error", "Lỗi"]]],
            ["rated", "Đánh giá", [["", "Tất cả"], ["down", "👎"], ["up", "👍"], ["any", "Đã đánh giá"]]],
            ["order", "Sắp xếp", [["recent", "Mới nhất"], ["slowest", "Chậm nhất"]]],
          ] as [keyof typeof filter, string, string[][]][]).map(([key, label, options]) => (
            <label key={key} className="flex items-center gap-2">{label}
              <select className="rounded border-2 p-1" value={filter[key]}
                      onChange={(e) => setFilter({ ...filter, [key]: e.target.value })}>
                {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          ))}
        </div>
        <table className="w-full border-collapse text-left text-base">
          <thead>
            <tr className="border-b-2">
              {["Thời điểm", "Loại", "Thời gian", "LLM", "Token", "Đầu vào", "Đánh giá", ""].map((h) => <th key={h} scope="col" className="p-2">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {traces.length === 0 && <tr><td colSpan={8} className="p-2">Chưa có trace nào.</td></tr>}
            {traces.map((t) => (
              <Fragment key={t.id}>
                <tr className={`border-b ${t.status === "error" ? "bg-red-50" : ""} ${selected?.id === t.id ? "bg-sky-50" : ""}`}>
                  <td className="p-2">{time(t.started_at)}</td>
                  <td className="p-2">{KIND[t.kind as keyof typeof KIND] ?? t.kind}{t.status === "error" && " · LỖI"}</td>
                  <td className="p-2">{ms(t.duration_ms)}</td>
                  <td className="p-2">{t.llm_calls}</td>
                  <td className="p-2">{num(t.input_tokens)} / {num(t.output_tokens)}</td>
                  <td className="max-w-md truncate p-2" title={t.input ?? ""}>{t.input ?? "—"}</td>
                  <td className="p-2">{t.rating === 1 ? "👍" : t.rating === -1 ? "👎" : ""}</td>
                  <td className="p-2"><button className={button} onClick={() => open(t.id)}>Xem</button></td>
                </tr>
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>

      {selected && <TraceView key={selected.id} trace={selected} onRated={(t) => { setSelected(t); load(); }} />}
    </main>
  );
}
