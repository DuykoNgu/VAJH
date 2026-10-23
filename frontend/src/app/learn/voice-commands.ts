// Lệnh giọng nói xử lý ngay trên trình duyệt (không gửi lên server) và chọn bài bằng giọng nói.

export type Command = "repeat" | "stop" | "change" | "slower" | "faster" | "help";

// So khớp CÓ DẤU: bỏ dấu thì "dừng" và "đúng" (câu trả lời) đều thành "dung".
const COMMANDS: [Command, string[]][] = [
  ["repeat", ["nhắc lại", "đọc lại", "nói lại"]],
  ["stop", ["dừng lại", "dừng"]],
  ["change", ["đổi bài", "chọn bài khác", "bài khác", "quay lại", "chủ đề khác"]],
  ["slower", ["chậm lại", "nói chậm", "đọc chậm"]],
  ["faster", ["nhanh lên", "nói nhanh", "đọc nhanh"]],
  ["help", ["trợ giúp", "giúp mình", "hướng dẫn"]],
];

function clean(text: string): string {
  return text.toLowerCase().replace(/[.,!?;:"“”]/g, " ").replace(/\s+/g, " ").trim();
}

/** Lệnh nếu câu nói NGẮN (≤ 4 từ) chứa cụm lệnh; câu dài là câu hỏi bình thường gửi cho LUSIA. */
export function matchCommand(text: string): Command | null {
  const t = clean(text);
  if (!t || t.split(" ").length > 4) return null;
  for (const [command, phrases] of COMMANDS) {
    if (phrases.some((p) => t.includes(p))) return command;
  }
  return null;
}

// ---------- Chọn bài bằng giọng nói: "bài hai", "bài số 2", hoặc vài từ trong tên bài ----------
const NUMBER_WORDS: Record<string, number> = {
  mot: 1, hai: 2, ba: 3, bon: 4, tu: 4, nam: 5, sau: 6, bay: 7, tam: 8, chin: 9, muoi: 10,
};

export function stripDiacritics(text: string): string {
  return clean(text).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d");
}

export function spokenNumber(text: string): number | null {
  const t = stripDiacritics(text);
  const digits = t.match(/(?:bai|chu de|so) (?:so )?(\d+)/) ?? t.match(/^(\d+)$/);
  if (digits) return Number(digits[1]);
  const word = t.match(/(?:bai|chu de|so) (?:so )?([a-z]+)/)?.[1] ?? (t.split(" ").length === 1 ? t : undefined);
  return word && word in NUMBER_WORDS ? NUMBER_WORDS[word] : null;
}

/** Chỉ số (0-based) trong danh sách, hoặc null. "bài 10" → bài có tên "Bài 10. …"; "số 2" → mục thứ 2 như lúc đọc. */
export function matchLesson(text: string, titles: string[]): number | null {
  const n = spokenNumber(text);
  if (n !== null) {
    const byTitle = /^so /.test(stripDiacritics(text)) ? -1
      : titles.findIndex((title) => stripDiacritics(title).startsWith(`bai ${n} `));
    if (byTitle >= 0) return byTitle;
    if (n >= 1 && n <= titles.length) return n - 1;
  }
  const words = stripDiacritics(text).split(" ").filter((w) => w.length > 2 && w !== "bai");
  let best: number | null = null;
  let bestScore = 0;
  titles.forEach((title, i) => {
    const titleWords = new Set(stripDiacritics(title).split(" "));
    const score = words.filter((w) => titleWords.has(w)).length;
    if (score > bestScore) {
      best = i;
      bestScore = score;
    }
  });
  return best;
}
