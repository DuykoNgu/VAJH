// Giám sát agent + LLM: trace từng lượt, độ trễ, token, lỗi, đánh giá chất lượng.
import MonitorApp from "./monitor-app";

export const metadata = { title: "Giám sát" };

export default function MonitorPage() {
  return <MonitorApp />;
}
