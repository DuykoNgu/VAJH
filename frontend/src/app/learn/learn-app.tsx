"use client";
// Trang học voice-first, KHÔNG cần tìm nút: nhấn phím bất kỳ → LUSIA đọc danh sách bài → nói "bài hai" (hoặc
// mũi tên + Enter) → LUSIA giảng từng phần, hỏi kiểm tra, chấm. Phím dùng được ở mọi nơi: Space nói, Esc dừng,
// R nhắc lại, H trợ giúp. Lệnh nói: nhắc lại, dừng, đổi bài, chậm lại, nhanh lên, trợ giúp.
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { api, type Me } from "@/lib/api";
import type { components } from "@/lib/api-types";
import { createPlayer, listen, recognitionSupported } from "@/lib/speech";
import { type Command, matchCommand, matchLesson } from "./voice-commands";

type DocumentSummary = components["schemas"]["DocumentSummary"];
type Lesson = components["schemas"]["Lesson"];
type TurnReply = components["schemas"]["TurnReply"];
type SessionStarted = components["schemas"]["SessionStarted"];
type Phase = "start" | "menu" | "session";
type Status = "idle" | "listening" | "thinking" | "speaking";
type Entry = { role: "student" | "lusia"; text: string; reply?: TurnReply };
type MenuLesson = Lesson & { documentTitle: string };
type Unit = { title: string; name: string; documentTitle: string; lessons: MenuLesson[] };

/** Bài liền nhau cùng chủ đề (sách không ghi chủ đề → cả cuốn) thành một mục; giữ đúng thứ tự trong sách. */
function groupUnits(lessons: MenuLesson[]): Unit[] {
  const units: Unit[] = [];
  for (const l of lessons) {
    const title = l.unit ?? l.documentTitle;
    const prev = units.at(-1);
    if (prev && prev.title === title && prev.documentTitle === l.documentTitle) prev.lessons.push(l);
    else units.push({ title, name: title.replace(/^(Chủ đề|Chương) [^:]+: /, ""), documentTitle: l.documentTitle, lessons: [l] });
  }
  return units;
}

const unitLine = (u: Unit, i: number) => `Số ${i + 1}: ${u.name}, ${u.lessons.length} bài.`;
const lessonLine = (l: MenuLesson, i: number) => `Số ${i + 1}: ${l.title}.`;

const STARTING = "Mình bắt đầu bài nhé.";
const HELP =
  "Em giữ phím cách để nói với gia sư. Nói tiếp để học phần sau. Nói kiểm tra mình để làm bài. Nói nhắc lại để nghe lại. " +
  "Nói chậm lại hoặc nhanh lên để đổi tốc độ đọc. Nói đổi bài để chọn bài khác. Phím R để nghe lại, phím Escape để dừng giọng đọc.";
const AGENT_NAMES: Record<string, string> = {
  orchestrator: "Orchestrator", knowledge: "Knowledge", vision: "Vision", tutor: "Tutor", assessment: "Assessment",
};
const STATUS_TEXT: Record<Status, string> = {
  idle: "Sẵn sàng. Giữ phím cách để nói.",
  listening: "Đang nghe…",
  thinking: "Gia sư đang suy nghĩ…",
  speaking: "Gia sư đang nói. Nhấn phím cách để ngắt và nói.",
};

function isTyping(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  return !!el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

export default function LearnApp() {
  const [phase, setPhase] = useState<Phase>("start");
  const [me, setMe] = useState<Me | null>(null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [unit, setUnit] = useState<number | null>(null); // null = đang chọn chủ đề
  const [highlight, setHighlight] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [interim, setInterim] = useState("");
  const [typed, setTyped] = useState("");
  const [rate, setRate] = useState(1);
  const [notice, setNotice] = useState("");
  const voiceInput = useSyncExternalStore(() => () => {}, recognitionSupported, () => false);

  const player = useRef<ReturnType<typeof createPlayer> | null>(null);
  const listener = useRef<ReturnType<typeof listen> | null>(null);
  const lastSpoken = useRef<string[]>([]);
  const busy = useRef(false);

  useEffect(() => {
    player.current = createPlayer((speaking) => setStatus((s) => (speaking ? "speaking" : s === "speaking" ? "idle" : s)));
  }, []);

  const speak = useCallback(
    (sentences: string[], remember = true) => {
      if (remember) lastSpoken.current = sentences;
      return player.current?.enqueue(sentences, rate);
    },
    [rate],
  );

  const say = useCallback((text: string) => {
    setNotice(text);
    player.current?.stop();
    speak([text]);
  }, [speak]);

  // ---------- Bắt đầu: phím bất kỳ / chạm bất kỳ đâu (trình duyệt chỉ cho phát âm thanh sau thao tác đầu tiên) ----------
  const howToPick = voiceInput ? "Em giữ phím cách và nói số, ví dụ: số một. Hoặc dùng phím mũi tên rồi nhấn Enter."
                               : "Em dùng phím mũi tên lên xuống rồi nhấn Enter để chọn.";

  /** Cấp 1: đọc các chủ đề theo thứ tự học (ngắn), không đọc cả trăm bài. */
  const readUnits = useCallback((list: Unit[], name?: string) => {
    const intro = name ? `Chào ${name}. ` : "";
    const sentences = list.length
      ? [`${intro}Có ${list.length} chủ đề, em học lần lượt từ số 1.`, ...list.map(unitLine), howToPick]
      : [`${intro}Hiện chưa có bài học nào. Em nhờ thầy cô nạp và xuất bản sách nhé.`];
    player.current?.stop();
    speak(sentences);
  }, [speak, howToPick]);

  /** Cấp 2: các bài trong một chủ đề. */
  const readLessons = useCallback((u: Unit) => {
    player.current?.stop();
    speak([`${u.name} có ${u.lessons.length} bài, học theo thứ tự.`, ...u.lessons.map(lessonLine), howToPick,
           "Nói quay lại để chọn chủ đề khác."]);
  }, [speak, howToPick]);

  const openUnit = useCallback((index: number) => {
    setUnit(index);
    setHighlight(0);
    readLessons(units[index]);
  }, [units, readLessons]);

  const backToUnits = useCallback(() => {
    setHighlight(unit ?? 0);
    setUnit(null);
    readUnits(units);
  }, [unit, units, readUnits]);

  const begin = useCallback(async () => {
    setPhase("menu");
    try {
      const [who, documents] = await Promise.all([api<Me>("/me"), api<DocumentSummary[]>("/documents")]);
      setMe(who);
      setRate(who.speech_rate ?? 1);
      const ready = documents.filter((d) => d.status === "ready")
        .sort((a, b) => a.grade - b.grade || a.created_at.localeCompare(b.created_at)); // lớp dưới học trước
      const lists = await Promise.all(ready.map((d) =>
        api<Lesson[]>(`/documents/${d.id}/lessons`).then((ls) => ls.map((l) => ({ ...l, documentTitle: d.title })))));
      const grouped = groupUnits(lists.flat());
      setUnits(grouped);
      setUnit(null);
      setHighlight(0);
      readUnits(grouped, who.full_name);
    } catch {
      say("Mình không kết nối được máy chủ. Em nhờ thầy cô kiểm tra nhé.");
    }
  }, [readUnits, say]);

  // ---------- Vào bài: LUSIA giảng ngay phần 1 ----------
  const startLesson = useCallback(async (lesson: MenuLesson) => {
    if (busy.current) return;
    busy.current = true;
    player.current?.stop();
    setPhase("session");
    setStatus("thinking");
    speak([STARTING], false);
    try {
      const started = await api<SessionStarted>("/sessions", {
        method: "POST",
        body: JSON.stringify({ lesson_id: lesson.id }),
      });
      setSessionId(started.id);
      setEntries([{ role: "lusia", text: started.answer, reply: started }]);
      setStatus("idle");
      speak(started.sentences);
    } catch {
      say("Xin lỗi, mình chưa mở được bài này. Em thử lại nhé.");
      setPhase("menu");
    } finally {
      busy.current = false;
    }
  }, [speak, say]);

  const backToMenu = useCallback(async () => {
    if (sessionId) await api(`/sessions/${sessionId}/end`, { method: "POST" }).catch(() => undefined);
    setSessionId(null);
    setEntries([]);
    setPhase("menu");
    if (unit === null) readUnits(units);
    else readLessons(units[unit]);
  }, [sessionId, unit, units, readUnits, readLessons]);

  // ---------- Lệnh xử lý ngay trên trình duyệt ----------
  const runCommand = useCallback((command: Command) => {
    switch (command) {
      case "repeat":
        player.current?.stop();
        speak(lastSpoken.current, false);
        break;
      case "stop":
        player.current?.stop();
        break;
      case "help":
        player.current?.stop();
        speak([HELP], false);
        break;
      case "change":
        if (phase === "menu" && unit !== null) backToUnits();
        else backToMenu();
        break;
      case "slower":
      case "faster": {
        const next = Math.min(2, Math.max(0.5, rate + (command === "slower" ? -0.25 : 0.25)));
        setRate(next);
        player.current?.stop();
        player.current?.enqueue([command === "slower" ? "Mình sẽ đọc chậm hơn." : "Mình sẽ đọc nhanh hơn."], next);
        break;
      }
    }
  }, [speak, backToMenu, backToUnits, phase, unit, rate]);

  /** Mục đang hiện ở menu: chủ đề, hoặc các bài của chủ đề đã chọn. Chọn = mở chủ đề / vào bài. */
  const menuTitles = useMemo(
    () => (unit === null ? units.map((u) => u.title) : (units[unit]?.lessons ?? []).map((l) => l.title)), [unit, units]);
  const choose = useCallback((i: number) => {
    if (unit === null) openUnit(i);
    else startLesson(units[unit].lessons[i]);
  }, [unit, units, openUnit, startLesson]);

  const sendTurn = useCallback(async (text: string) => {
    if (!sessionId || !text.trim() || busy.current) return;
    busy.current = true;
    setEntries((e) => [...e, { role: "student", text }]);
    setStatus("thinking");
    player.current?.stop(); // xử lý im lặng (người dùng thấy câu chờ lặp lại mỗi lượt gây mệt)
    try {
      const reply = await api<TurnReply>(`/sessions/${sessionId}/turns`, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setEntries((e) => [...e, { role: "lusia", text: reply.answer, reply }]);
      setStatus("idle");
      speak(reply.sentences);
    } catch {
      setStatus("idle");
      say("Xin lỗi, mình gặp lỗi. Em thử nói lại nhé.");
    } finally {
      busy.current = false;
    }
  }, [sessionId, speak, say]);

  /** Một câu nói / câu gõ: lệnh trình duyệt, chọn bài (ở menu), hoặc gửi cho LUSIA. */
  const handleUtterance = useCallback((text: string) => {
    const command = matchCommand(text);
    if (command) return runCommand(command);
    if (phase === "menu") {
      const index = matchLesson(text, menuTitles);
      if (index === null) return say(`Mình chưa nghe rõ “${text}”. Em nói lại nhé, ví dụ: số hai.`);
      return choose(index);
    }
    if (phase === "session") sendTurn(text);
  }, [phase, menuTitles, runCommand, say, choose, sendTurn]);

  // ---------- Nghe: giữ Space hoặc nút "Giữ để nói" ----------
  const startListening = useCallback(() => {
    if (listener.current || phase === "start") return;
    player.current?.stop(); // nói chen: ngắt LUSIA ngay
    if (!voiceInput) return;
    setInterim("");
    setStatus("listening");
    listener.current = listen(
      setInterim,
      (text) => {
        listener.current = null;
        setInterim("");
        setStatus("idle");
        if (text) handleUtterance(text);
      },
      (error) => setNotice(`Lỗi nhận giọng nói: ${error}`),
    );
  }, [phase, voiceInput, handleUtterance]);

  const stopListening = useCallback(() => listener.current?.stop(), []);

  // ---------- Bàn phím dùng được ở mọi nơi ----------
  useEffect(() => {
    function down(e: KeyboardEvent) {
      if (isTyping(e.target)) return;
      if (phase === "start") {
        if (["Tab", "Shift", "Meta", "Alt", "Control"].includes(e.key)) return; // để trình đọc màn hình di chuyển
        e.preventDefault();
        begin();
        return;
      }
      if (e.key === "Escape") return runCommand("stop");
      if (e.key === "r" || e.key === "R") return runCommand("repeat");
      if (e.key === "h" || e.key === "H") return runCommand("help");
      if (e.code === "Space") {
        e.preventDefault();
        if (!e.repeat) startListening();
        return;
      }
      if (phase === "menu" && menuTitles.length && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
        e.preventDefault();
        const next = (highlight + (e.key === "ArrowDown" ? 1 : -1) + menuTitles.length) % menuTitles.length;
        setHighlight(next);
        player.current?.stop();
        speak([unit === null ? unitLine(units[next], next) : lessonLine(units[unit].lessons[next], next)], false);
        return;
      }
      if (phase === "menu" && e.key === "Enter" && highlight < menuTitles.length) {
        e.preventDefault();
        choose(highlight);
        return;
      }
      if (phase === "menu" && e.key === "Backspace" && unit !== null) {
        e.preventDefault();
        backToUnits();
      }
    }
    function up(e: KeyboardEvent) {
      if (e.code === "Space" && listener.current) {
        e.preventDefault();
        stopListening();
      }
    }
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [phase, unit, units, menuTitles.length, highlight, begin, runCommand, startListening, stopListening, choose,
      backToUnits, speak]);

  // ---------- Màn hình bắt đầu: cả trang là một nút ----------
  if (phase === "start") {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <button autoFocus onClick={begin}
                className="w-full max-w-3xl rounded-2xl border-4 p-12 text-3xl font-bold focus:outline-4">
          Học cùng gia sư — nhấn phím bất kỳ để bắt đầu
        </button>
      </main>
    );
  }

  const last = [...entries].reverse().find((e) => e.role === "lusia" && e.reply);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6 text-lg">
      <h1 className="text-3xl font-bold">Học cùng gia sư</h1>
      <p role="status" aria-live="polite" className="rounded-lg border-2 p-3 font-semibold">
        {STATUS_TEXT[status]}
        {interim && <span className="block font-normal">“{interim}”</span>}
      </p>
      {!voiceInput && (
        <p className="rounded-lg border-2 border-amber-600 p-3">
          Trình duyệt này không nhận được giọng nói: dùng phím mũi tên và Enter để chọn bài, gõ câu trả lời vào ô bên dưới.
        </p>
      )}
      {notice && <p className="rounded-lg border-2 border-amber-600 p-3">{notice}</p>}
      <p>Giữ <kbd className="rounded border px-1">phím cách</kbd> để nói · <kbd className="rounded border px-1">R</kbd> nghe lại ·{" "}
        <kbd className="rounded border px-1">H</kbd> trợ giúp · <kbd className="rounded border px-1">Esc</kbd> dừng · tốc độ {rate.toFixed(2)}×</p>

      {voiceInput && (
        <button type="button" className="rounded-lg border-2 px-4 py-3 text-xl font-semibold"
                onPointerDown={startListening} onPointerUp={stopListening} onPointerLeave={stopListening}
                aria-pressed={status === "listening"}>
          {status === "listening" ? "Đang nghe… thả ra để gửi" : "Giữ để nói"}
        </button>
      )}

      {phase === "menu" && unit === null && (
        <section aria-labelledby="chu-de" className="flex flex-col gap-2">
          <h2 id="chu-de" className="text-xl font-semibold">Chọn chủ đề — học lần lượt từ số 1</h2>
          <ol className="flex flex-col gap-2">
            {units.map((u, i) => (
              <li key={`${u.documentTitle}|${u.title}`}>
                <button onClick={() => openUnit(i)} aria-current={i === highlight}
                        className={`w-full rounded-lg border-2 p-3 text-left ${i === highlight ? "border-blue-700 font-semibold" : ""}`}>
                  Số {i + 1}: {u.title}{" "}
                  <span className="text-base font-normal">— {u.title === u.documentTitle ? "" : `${u.documentTitle} · `}{u.lessons.length} bài</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      {phase === "menu" && unit !== null && units[unit] && (
        <section aria-labelledby="bai-hoc" className="flex flex-col gap-2">
          <h2 id="bai-hoc" className="text-xl font-semibold">{units[unit].title} — chọn bài</h2>
          <button onClick={backToUnits} className="self-start rounded-lg border-2 px-3 py-1">
            ← Quay lại danh sách chủ đề <kbd className="rounded border px-1">Backspace</kbd>
          </button>
          <ol className="flex flex-col gap-2">
            {units[unit].lessons.map((l, i) => (
              <li key={l.id}>
                <button onClick={() => startLesson(l)} aria-current={i === highlight}
                        className={`w-full rounded-lg border-2 p-3 text-left ${i === highlight ? "border-blue-700 font-semibold" : ""}`}>
                  Số {i + 1}: {l.title} <span className="text-base font-normal">— {l.documentTitle}, trang {l.page_start}–{l.page_end}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      {phase === "session" && (
        <>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); handleUtterance(typed); setTyped(""); }}>
            <label className="sr-only" htmlFor="cau-hoi">Gõ câu trả lời hoặc câu hỏi</label>
            <input id="cau-hoi" className="flex-1 rounded border-2 p-2" value={typed} onChange={(e) => setTyped(e.target.value)}
                   placeholder="Hoặc gõ ở đây (ví dụ: tiếp, kiểm tra mình)" />
            <button className="rounded-lg border-2 px-4 py-2 font-semibold">Gửi</button>
          </form>

          {last?.reply && (
            <section aria-labelledby="tac-nhan" className="rounded-lg border-2 p-3">
              <h2 id="tac-nhan" className="font-semibold">Các agent vừa làm việc</h2>
              <p>{last.reply.trace.map((t) => AGENT_NAMES[t.agent] ?? t.agent).join(" → ")}</p>
              <ul className="list-disc pl-6 text-base">
                {last.reply.trace.map((t, i) => <li key={i}>{AGENT_NAMES[t.agent] ?? t.agent}: {t.summary}</li>)}
              </ul>
              {last.reply.citations.length > 0 && (
                <p className="text-base">Nguồn: {last.reply.citations.map((c) => `trang ${c.page}${c.kind === "figure" ? " (hình)" : ""}`).join(", ")}</p>
              )}
              {last.reply.mode === "quiz" && <p className="font-semibold">Đang làm bài kiểm tra</p>}
              {last.reply.mode === "teach" && <p className="font-semibold">Đang học theo từng phần</p>}
            </section>
          )}

          <section aria-labelledby="hoi-thoai" className="flex flex-col gap-2">
            <h2 id="hoi-thoai" className="text-xl font-semibold">Hội thoại {me ? `— ${me.full_name}` : ""}</h2>
            <ol aria-live="off" className="flex flex-col gap-2">
              {entries.map((e, i) => (
                <li key={i} className={e.role === "student" ? "rounded-lg border p-3" : "rounded-lg border-2 p-3"}>
                  <span className="font-semibold">{e.role === "student" ? "Em: " : "Gia sư: "}</span>{e.text}
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </main>
  );
}
