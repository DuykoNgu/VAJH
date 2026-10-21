import { matchCommand, matchLesson } from "../src/app/learn/voice-commands.ts";
const titles = ["Bài 1. Hàm số bậc nhất", "Bài 2. Đồ thị của hàm số bậc nhất"];
const cases: [string, unknown, unknown][] = [
  ["matchLesson('bài hai')", matchLesson("bài hai", titles), 1],
  ["matchLesson('Bài số 1.')", matchLesson("Bài số 1.", titles), 0],
  ["matchLesson('đồ thị')", matchLesson("đồ thị", titles), 1],
  ["matchLesson('2')", matchLesson("2", titles), 1],
  ["matchLesson('lịch sử')", matchLesson("lịch sử", titles), null],
  ["matchCommand('nhắc lại')", matchCommand("Nhắc lại."), "repeat"],
  ["matchCommand('đúng')", matchCommand("đúng"), null],
  ["matchCommand('dừng lại')", matchCommand("dừng lại"), "stop"],
  ["matchCommand('nói chậm lại thôi')", matchCommand("nói chậm lại thôi"), "slower"],
  ["matchCommand(long)", matchCommand("tại sao đồ thị lại dừng ở điểm đó vậy"), null],
  ["matchCommand('tiếp')", matchCommand("tiếp"), null],
];
const bad = cases.filter(([, got, want]) => got !== want);
if (bad.length) { console.error(bad); process.exit(1); }
console.log("all voice-command checks pass");
