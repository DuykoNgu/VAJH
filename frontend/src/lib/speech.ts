// Giọng nói phía trình duyệt: nhận dạng (Web Speech API, vi-VN) và phát câu trả lời từng câu qua /tts.
import { API_URL } from "./api";

// ---------- Nhận dạng giọng nói (Chrome: webkitSpeechRecognition, gửi audio tới Google) ----------
type RecognitionResultList = ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { resultIndex: number; results: RecognitionResultList }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
}
type RecognitionCtor = new () => Recognition;

export function recognitionSupported(): boolean {
  return typeof window !== "undefined" && Boolean(getCtor());
}

function getCtor(): RecognitionCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** Bắt đầu nghe; gọi stop() khi thả phím → onFinal(transcript) (chuỗi rỗng nếu không nghe được gì). */
export function listen(onInterim: (text: string) => void, onFinal: (text: string) => void, onError: (e: string) => void) {
  const Ctor = getCtor();
  if (!Ctor) throw new Error("speech recognition unsupported");
  const rec = new Ctor();
  rec.lang = "vi-VN";
  rec.continuous = true;
  rec.interimResults = true;
  let finalText = "";
  let interim = "";
  rec.onresult = (e) => {
    interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    onInterim((finalText + " " + interim).trim());
  };
  rec.onerror = (e) => {
    if (e.error !== "no-speech" && e.error !== "aborted") onError(e.error);
  };
  rec.onend = () => onFinal((finalText + " " + interim).trim());
  rec.start();
  return { stop: () => rec.stop(), abort: () => rec.abort() };
}

// ---------- Phát câu trả lời: tải trước mọi câu, phát lần lượt, có thể ngắt ngay ----------
async function fetchSpeech(text: string): Promise<Blob> {
  const res = await fetch(`${API_URL}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`TTS ${res.status}`);
  return res.blob();
}

export function createPlayer(onSpeaking: (speaking: boolean) => void) {
  let generation = 0;
  let chain: Promise<void> = Promise.resolve();
  let current: HTMLAudioElement | null = null;
  let pending = 0;

  function playBlob(blob: Blob, rate: number): Promise<void> {
    return new Promise((resolve) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.playbackRate = rate; // trình duyệt giữ nguyên cao độ khi đổi tốc độ
      audio.preservesPitch = true;
      current = audio;
      const done = () => {
        URL.revokeObjectURL(url);
        current = null;
        resolve();
      };
      audio.onended = done;
      audio.onpause = done;
      audio.onerror = done;
      audio.play().catch(done);
    });
  }

  return {
    /** Xếp các câu vào hàng phát sau những gì đang phát; tải audio ngay để câu sau sẵn sàng khi câu trước xong. */
    enqueue(sentences: string[], rate: number): Promise<void> {
      const gen = generation;
      const blobs = sentences.map((s) => fetchSpeech(s).catch(() => null));
      pending += 1;
      onSpeaking(true);
      chain = chain.then(async () => {
        for (const b of blobs) {
          if (gen !== generation) break;
          const blob = await b;
          if (!blob || gen !== generation) continue;
          await playBlob(blob, rate);
        }
        pending -= 1;
        if (pending <= 0) {
          pending = 0;
          onSpeaking(false);
        }
      });
      return chain;
    },
    /** Ngắt ngay (học sinh nhấn Space/Esc để nói chen). */
    stop() {
      generation += 1;
      pending = 0;
      current?.pause();
      chain = Promise.resolve();
      onSpeaking(false);
    },
  };
}
