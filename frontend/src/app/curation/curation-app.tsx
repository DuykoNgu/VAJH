"use client";
// Kiểm duyệt nội dung: giáo viên chuẩn bị TRI THỨC GỐC (đoạn văn, dữ kiện hình) rồi xuất bản cho học sinh.
// Cách LUSIA diễn đạt không được lưu ở đây: "Nghe thử" chỉ là một ví dụ, mỗi lần giảng sẽ khác.
import { useEffect, useRef, useState } from "react";

import { API_URL, ApiError, api } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { createPlayer } from "@/lib/speech";

type Doc = components["schemas"]["CurationDocument"];
type Detail = components["schemas"]["CurationDetail"];
type Lesson = components["schemas"]["CurationLesson"];
type Part = components["schemas"]["CurationPart"];
type Preview = components["schemas"]["Preview"];

const SUBJECTS = { toan: "Toán", khtn: "Khoa học tự nhiên", vat_ly: "Vật lý", hoa_hoc: "Hóa học", sinh_hoc: "Sinh học",
  ngu_van: "Ngữ văn", tieng_viet: "Tiếng Việt", tieng_anh: "Tiếng Anh", lich_su: "Lịch sử", dia_ly: "Địa lý",
  lich_su_dia_ly: "Lịch sử và Địa lý", tin_hoc: "Tin học", khac: "Khác" } as const;
const REVIEW = { pending: "Chờ duyệt", approved: "Đã duyệt", rejected: "Đã từ chối" } as const;
const button = "rounded-lg border-2 px-3 py-1 focus:outline-4 disabled:opacity-50";

function detailOf(e: unknown): string {
  return e instanceof ApiError && typeof e.detail === "object" && e.detail && "detail" in e.detail
    ? String((e.detail as { detail: unknown }).detail) : "Có lỗi, thử lại nhé.";
}

function status(d: Doc): string {
  if (d.status === "processing") return `Đang xử lý (${d.processed_pages}/${d.page_count ?? "?"} trang)`;
  if (d.status === "failed") return `Lỗi: ${d.error}`;
  return d.published ? "Đã xuất bản" : `Bản nháp — ${d.pending_figures} hình chờ duyệt`;
}

function UploadForm({ onUploaded }: { onUploaded: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    try {
      await api("/documents", { method: "POST", body: new FormData(form) });
      form.reset();
      onUploaded("Đã tải lên, đang xử lý tài liệu.");
    } catch (err) {
      onUploaded(detailOf(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-lg border-2 p-4">
      <label className="flex flex-col gap-1">File PDF
        <input name="file" type="file" accept="application/pdf" required className="rounded border-2 p-1" />
      </label>
      <label className="flex flex-col gap-1">Tên tài liệu
        <input name="title" required className="rounded border-2 p-1" placeholder="Toán 8 — Tập 1" />
      </label>
      <label className="flex flex-col gap-1">Môn
        <select name="subject" defaultValue="toan" className="rounded border-2 p-1">
          {Object.entries(SUBJECTS).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
      </label>
      <label className="flex flex-col gap-1">Lớp
        <input name="grade" type="number" min={1} max={12} defaultValue={8} required className="w-20 rounded border-2 p-1" />
      </label>
      <button disabled={busy} className={`${button} font-semibold`}>Tải lên</button>
    </form>
  );
}

type Actions = {
  reload: (message: string) => Promise<void>;
  preview: (lesson: Lesson, part: number) => void;
};

function TextBlock({ parts, lesson, actions }: { parts: Part[]; lesson: Lesson; actions: Actions }) {
  // Một đoạn SGK có thể thành nhiều phần nhỏ khi giảng; sửa/xóa áp dụng cho cả đoạn
  const original = parts.map((p) => p.content).join(" ");
  const [text, setText] = useState(original);
  const [busy, setBusy] = useState(false);
  const id = parts[0].chunk_id;
  async function run(init: RequestInit, done: string) {
    setBusy(true);
    try {
      await api(`/curation/chunks/${id}`, init);
      await actions.reload(done);
    } catch (e) {
      await actions.reload(detailOf(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className="flex flex-col gap-2 rounded border p-3">
      <p className="text-base text-gray-700">
        Đoạn văn, trang {parts[0].page} — {parts.length > 1 ? `giảng thành ${parts.length} phần nhỏ` : "1 phần"}
      </p>
      <label className="sr-only" htmlFor={`chunk-${id}`}>Nội dung đoạn trang {parts[0].page}</label>
      <textarea id={`chunk-${id}`} className="min-h-24 rounded border-2 p-2" value={text}
                onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <button disabled={busy || text.trim() === original || !text.trim()} className={button}
                onClick={() => run({ method: "PATCH", body: JSON.stringify({ content: text }) }, "Đã lưu đoạn văn.")}>
          Lưu
        </button>
        <button disabled={busy} className={button} onClick={() => run({ method: "DELETE" }, "Đã xóa đoạn văn.")}>
          Xóa đoạn
        </button>
        {parts.map((p) => p.number !== null && (
          <button key={p.number} className={button} onClick={() => actions.preview(lesson, p.number!)}>
            Nghe thử phần {p.number}
          </button>
        ))}
      </div>
    </li>
  );
}

function FigureBlock({ part, lesson, actions }: { part: Part; lesson: Lesson; actions: Actions }) {
  const [text, setText] = useState(part.content);
  const [busy, setBusy] = useState(false);
  async function review(action: "approve" | "reject") {
    setBusy(true);
    try {
      await api(`/teacher/figures/${part.chunk_id}/review`, {
        method: "POST",
        body: JSON.stringify(action === "approve" ? { action, description: text } : { action }),
      });
      await actions.reload(action === "approve" ? "Đã duyệt hình." : "Đã từ chối hình.");
    } finally {
      setBusy(false);
    }
  }
  const pending = part.review === "pending";
  return (
    <li className={`flex flex-col gap-2 rounded border-2 p-3 ${pending ? "border-amber-500" : ""}`}>
      <p className="font-semibold">
        Hình, trang {part.page} — {REVIEW[part.review ?? "pending"]}
        {part.number === null && " (không được giảng)"}
      </p>
      {/* eslint-disable-next-line @next/next/no-img-element -- ảnh từ API backend, không qua tối ưu ảnh của Next */}
      <img src={`${API_URL}${part.image_url}`} alt={`Hình trang ${part.page}`} className="max-h-72 w-fit border" />
      <label className="flex flex-col gap-1">
        Dữ kiện của hình (kiểm tra đúng và đủ; LUSIA tự diễn đạt khi giảng)
        <textarea className="min-h-28 rounded border-2 p-2" value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button disabled={busy} className={`${button} font-semibold`} onClick={() => review("approve")}>
          {text !== part.content ? "Lưu và duyệt" : "Duyệt"}
        </button>
        <button disabled={busy || part.review === "rejected"} className={button} onClick={() => review("reject")}>
          Từ chối
        </button>
        {part.number !== null && (
          <button className={button} onClick={() => actions.preview(lesson, part.number!)}>Nghe thử phần {part.number}</button>
        )}
      </div>
    </li>
  );
}

function LessonView({ lesson, actions }: { lesson: Lesson; actions: Actions }) {
  // gom các phần chữ liền nhau của cùng một đoạn SGK
  const blocks: Part[][] = [];
  for (const p of lesson.parts) {
    const last = blocks.at(-1);
    if (p.kind === "text" && last?.[0].kind === "text" && last[0].chunk_id === p.chunk_id) last.push(p);
    else blocks.push([p]);
  }
  const count = lesson.parts.filter((p) => p.number !== null).length;
  return (
    <section aria-labelledby={`lesson-${lesson.id}`} className="flex flex-col gap-3">
      <h3 id={`lesson-${lesson.id}`} className="text-xl font-semibold">
        {lesson.title} <span className="font-normal">(trang {lesson.page_start}–{lesson.page_end}, {count} phần)</span>
      </h3>
      {blocks.length === 0 ? <p>Bài này chưa có nội dung.</p> : (
        <ul className="flex flex-col gap-3">
          {blocks.map((b) => b[0].kind === "figure"
            ? <FigureBlock key={`f${b[0].chunk_id}-${b[0].content}`} part={b[0]} lesson={lesson} actions={actions} />
            : <TextBlock key={`t${b[0].chunk_id}-${b.map((p) => p.content).join()}`} parts={b} lesson={lesson}
                         actions={actions} />)}
        </ul>
      )}
    </section>
  );
}

export default function CurationApp() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [message, setMessage] = useState("");
  const [sample, setSample] = useState<(Preview & { title: string }) | null>(null);
  const player = useRef<ReturnType<typeof createPlayer> | null>(null);

  const loadDocs = () => api<Doc[]>("/curation/documents").then(setDocs).catch(() => setMessage("Không tải được tài liệu."));

  useEffect(() => {
    loadDocs();
  }, []);

  const processing = docs?.some((d) => d.status === "processing");
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(loadDocs, 3000); // theo dõi tiến độ xử lý
    return () => clearInterval(timer);
  }, [processing]);

  async function open(id: string) {
    setSelected(id);
    setSample(null);
    setDetail(await api<Detail>(`/curation/documents/${id}`));
  }

  async function reload(text: string) {
    setMessage(text);
    await loadDocs();
    if (selected) setDetail(await api<Detail>(`/curation/documents/${selected}`));
  }

  async function publish(action: "publish" | "unpublish") {
    try {
      await api(`/curation/documents/${selected}/${action}`, { method: "POST" });
      await reload(action === "publish" ? "Đã xuất bản: học sinh đã có thể học tài liệu này." : "Đã chuyển về bản nháp.");
    } catch (e) {
      setMessage(detailOf(e));
    }
  }

  function preview(lesson: Lesson, part: number) {
    setSample(null);
    setMessage(`Đang soạn ví dụ phần ${part}…`);
    api<Preview>("/curation/preview", { method: "POST", body: JSON.stringify({ lesson_id: lesson.id, part }) })
      .then((p) => {
        setSample({ ...p, title: lesson.title });
        setMessage("");
        player.current ??= createPlayer(() => undefined);
        player.current.stop();
        player.current.enqueue(p.sentences, 1);
      })
      .catch((e) => setMessage(detailOf(e)));
  }

  const doc = detail?.document;
  const actions: Actions = { reload, preview };
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6 text-lg">
      <h1 className="text-3xl font-bold">Kiểm duyệt nội dung</h1>
      <p>
        Bước 1 — chuẩn bị tri thức: tải sách lên, kiểm tra đoạn văn và dữ kiện của từng hình, rồi xuất bản.
        Học sinh chỉ học tài liệu đã xuất bản. Đây là cơ sở của bài học; cách LUSIA diễn đạt sẽ linh hoạt mỗi lần giảng.
      </p>
      <p role="status" aria-live="polite" className="font-semibold">{message}</p>

      <UploadForm onUploaded={(m) => { setMessage(m); loadDocs(); }} />

      <section aria-labelledby="tai-lieu" className="flex flex-col gap-2">
        <h2 id="tai-lieu" className="text-2xl font-semibold">Tài liệu</h2>
        {docs === null && <p>Đang tải…</p>}
        <ul className="flex flex-col gap-2">
          {docs?.map((d) => (
            <li key={d.id}>
              <button onClick={() => open(d.id)} disabled={d.status !== "ready"} aria-current={d.id === selected}
                      className={`${button} w-full text-left ${d.id === selected ? "bg-gray-100" : ""}`}>
                <span className="font-semibold">{d.title}</span> — {SUBJECTS[d.subject as keyof typeof SUBJECTS]} lớp{" "}
                {d.grade} · {d.lessons} bài · {status(d)}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {doc && detail && (
        <section aria-labelledby="chi-tiet" className="flex flex-col gap-4">
          <h2 id="chi-tiet" className="text-2xl font-semibold">{doc.title}</h2>
          <div className="flex flex-wrap items-center gap-3 rounded-lg border-2 p-3">
            <span>{status(doc)}</span>
            {doc.published
              ? <button className={button} onClick={() => publish("unpublish")}>Chuyển về bản nháp</button>
              : <button className={`${button} font-semibold`} disabled={doc.pending_figures > 0}
                        aria-describedby="ly-do" onClick={() => publish("publish")}>Xuất bản</button>}
            {!doc.published && doc.pending_figures > 0 && (
              <span id="ly-do">Chưa xuất bản được: còn {doc.pending_figures} hình chưa duyệt.</span>
            )}
          </div>
          {sample && (
            // nổi ở góc màn hình: thấy ngay cạnh nút vừa bấm dù đang cuộn tới đâu
            <aside aria-label="Ví dụ cách LUSIA giảng"
                   className="fixed right-4 bottom-4 left-4 z-10 ml-auto flex max-h-[50vh] max-w-xl flex-col gap-2 overflow-y-auto rounded-lg border-2 border-sky-600 bg-white p-4 shadow-lg">
              <h3 className="font-semibold">Nghe thử: {sample.title}, phần {sample.part}/{sample.parts}</h3>
              <p>{sample.answer}</p>
              <p className="text-base italic">{sample.note}</p>
              <div className="flex gap-2">
                <button className={button} onClick={() => player.current?.stop()}>Dừng đọc</button>
                <button className={button} onClick={() => { player.current?.stop(); setSample(null); }}>Đóng</button>
              </div>
            </aside>
          )}
          {detail.lessons.map((l) => <LessonView key={l.id} lesson={l} actions={actions} />)}
        </section>
      )}
    </main>
  );
}
