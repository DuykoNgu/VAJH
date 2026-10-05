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

// ---------- Phát câu trả lời: cả lượt nói là MỘT luồng MP3 (/tts/stream), phát ngay khi khúc đầu tới ----------
// <audio src> chờ tải hết luồng mới phát (đo: 1,4-2,8 s mỗi câu); Media Source phát sau ~0,35 s mà vẫn giữ
// playbackRate + preservesPitch (đọc chậm/nhanh không méo giọng).
const STREAM_TYPE = "audio/mpeg";

function mediaSourceSupported(): boolean {
  return typeof MediaSource !== "undefined" && MediaSource.isTypeSupported(STREAM_TYPE);
}

async function requestSpeech(sentences: string[], signal: AbortSignal): Promise<Response> {
  const res = await fetch(`${API_URL}/tts/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sentences }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`TTS ${res.status}`);
  return res;
}

/** Nối luồng vào `audio` qua Media Source, phát được ngay khi có dữ liệu. `after`: chờ lượt trước tải xong. */
async function streamInto(audio: HTMLAudioElement, sentences: string[], signal: AbortSignal,
                          after: Promise<unknown>): Promise<boolean> {
  const source = new MediaSource();
  audio.src = URL.createObjectURL(source);
  let received = false;
  try {
    await new Promise((resolve) => source.addEventListener("sourceopen", resolve, { once: true }));
    URL.revokeObjectURL(audio.src);
    const buffer = source.addSourceBuffer(STREAM_TYPE);
    buffer.mode = "sequence";
    await after;
    const reader = (await requestSpeech(sentences, signal)).body!.getReader();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      await new Promise((resolve) => {
        buffer.addEventListener("updateend", resolve, { once: true });
        buffer.appendBuffer(value);
      });
      received = true;
    }
  } catch {
    // bị ngắt lời (abort) hoặc lỗi mạng: phát phần đã nhận
  }
  try {
    if (source.readyState === "open") source.endOfStream();
  } catch {
    // đang append dở khi bị huỷ
  }
  return received;
}

/** Trình duyệt không có Media Source cho MP3: tải trọn luồng rồi phát (chậm hơn nhưng vẫn đúng). */
async function downloadInto(audio: HTMLAudioElement, sentences: string[], signal: AbortSignal,
                            after: Promise<unknown>): Promise<boolean> {
  try {
    await after;
    const blob = await (await requestSpeech(sentences, signal)).blob();
    audio.src = URL.createObjectURL(blob);
    return blob.size > 0;
  } catch {
    return false;
  }
}

export function createPlayer(onSpeaking: (speaking: boolean) => void) {
  let generation = 0;
  let chain: Promise<void> = Promise.resolve();
  let loading: Promise<unknown> = Promise.resolve(); // lượt sau chỉ tải khi lượt trước tải xong (không giành model)
  let current: HTMLAudioElement | null = null;
  let pending = 0;
  const requests = new Set<AbortController>();

  function play(audio: HTMLAudioElement, loaded: Promise<boolean>, rate: number): Promise<void> {
    return new Promise((resolve) => {
      current = audio;
      const done = () => {
        audio.onended = audio.onpause = audio.onerror = null;
        if (current === audio) current = null;
        resolve();
      };
      audio.onended = done;
      audio.onpause = done;
      audio.onerror = done;
      loaded.then((received) => {
        if (!received) done(); // không có audio (lỗi / bị huỷ): đừng chờ "ended"
      });
      audio.defaultPlaybackRate = rate; // nạp nguồn mới đặt lại playbackRate = defaultPlaybackRate
      audio.playbackRate = rate; // trình duyệt giữ nguyên cao độ khi đổi tốc độ
      audio.play().catch(done);
    });
  }

  return {
    /** Xếp lượt nói vào hàng sau những gì đang phát; tải ngay (sau lượt trước) để tới lượt là phát được liền. */
    enqueue(sentences: string[], rate: number): Promise<void> {
      const gen = generation;
      const request = new AbortController();
      requests.add(request);
      const audio = new Audio();
      audio.preservesPitch = true;
      const feed = mediaSourceSupported() ? streamInto : downloadInto;
      const loaded = feed(audio, sentences, request.signal, loading).finally(() => requests.delete(request));
      loading = loaded;
      pending += 1;
      onSpeaking(true);
      chain = chain.then(async () => {
        if (gen === generation) await play(audio, loaded, rate);
        pending -= 1;
        if (pending <= 0) {
          pending = 0;
          onSpeaking(false);
        }
      });
      return chain;
    },
    /** Ngắt ngay (học sinh nhấn Space/Esc để nói chen): dừng phát và huỷ phần server đang tổng hợp. */
    stop() {
      generation += 1;
      pending = 0;
      for (const request of requests) request.abort();
      requests.clear();
      current?.pause();
      chain = Promise.resolve();
      loading = Promise.resolve();
      onSpeaking(false);
    },
  };
}
