"use client";
// Teacher Dashboard: học sinh nào yếu bài nào (hiểu bài / hiểu hình). Duyệt hình: trang /curation.
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { components } from "@/lib/api-types";

type ClassOverview = components["schemas"]["ClassOverview"];

const PART = { concept: "hiểu bài", figure: "hiểu hình" } as const;
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

export default function DashboardApp() {
  const [classes, setClasses] = useState<ClassOverview[] | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<ClassOverview[]>("/teacher/overview").then(setClasses).catch(() => setMessage("Không tải được dữ liệu lớp."));
  }, []);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 p-6 text-lg">
      <h1 className="text-3xl font-bold">Teacher Dashboard</h1>
      <p role="status" aria-live="polite">{message}</p>

      <section aria-labelledby="tien-do" className="flex flex-col gap-4">
        <h2 id="tien-do" className="text-2xl font-semibold">Tiến độ học sinh</h2>
        {classes === null && <p>Đang tải…</p>}
        {classes?.map((c) => (
          <div key={c.class_id} className="flex flex-col gap-2">
            <h3 className="text-xl font-semibold">Lớp {c.name}</h3>
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b-2">
                  <th scope="col" className="p-2">Học sinh</th>
                  <th scope="col" className="p-2">Bài học</th>
                  <th scope="col" className="p-2">Tổng</th>
                  <th scope="col" className="p-2">Hiểu bài</th>
                  <th scope="col" className="p-2">Hiểu hình</th>
                  <th scope="col" className="p-2">Đánh giá</th>
                </tr>
              </thead>
              <tbody>
                {c.students.flatMap((s) =>
                  s.lessons.length === 0
                    ? [<tr key={s.student_id} className="border-b"><th scope="row" className="p-2">{s.full_name}</th>
                         <td className="p-2" colSpan={5}>Chưa làm bài kiểm tra nào</td></tr>]
                    : s.lessons.map((l) => (
                        <tr key={`${s.student_id}-${l.lesson_id}`} className={l.weak ? "border-b bg-amber-100" : "border-b"}>
                          <th scope="row" className="p-2">{s.full_name}</th>
                          <td className="p-2">{l.title}</td>
                          <td className="p-2">{pct(l.mastery)} ({l.answered} câu)</td>
                          <td className="p-2">{pct(l.concept_mastery)}</td>
                          <td className="p-2">{pct(l.figure_mastery)}</td>
                          <td className="p-2 font-semibold">
                            {l.weak ? `Yếu${l.weak_in.length ? ": " + l.weak_in.map((w) => PART[w]).join(", ") : ""}` : "Ổn"}
                          </td>
                        </tr>
                      )),
                )}
              </tbody>
            </table>
          </div>
        ))}
      </section>

      <p>
        Duyệt đoạn văn và hình, nghe thử và xuất bản tài liệu ở trang{" "}
        <Link href="/curation" className="font-semibold underline">Kiểm duyệt nội dung</Link>.
      </p>
    </main>
  );
}
