import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 p-6">
      <h1 className="text-4xl font-bold">LUSIA</h1>
      <p className="text-lg">Listen • Understand • Share • Inspire • Assist</p>
      <nav className="flex flex-col gap-4 text-xl">
        <Link href="/learn" className="rounded-lg border-2 p-4 focus:outline-4">
          🎓 Học sinh – Học cùng LUSIA
        </Link>
        <Link href="/dashboard" className="rounded-lg border-2 p-4 focus:outline-4">
          👩‍🏫 Giáo viên – Teacher Dashboard
        </Link>
        <Link href="/curation" className="rounded-lg border-2 p-4 focus:outline-4">
          📚 Giáo viên – Kiểm duyệt nội dung
        </Link>
      </nav>
    </main>
  );
}
