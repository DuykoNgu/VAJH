import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 p-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.svg" alt="Gia sư AI cho học sinh khiếm thị" width={96} height={96} className="self-center"/>
      <nav className="flex flex-col gap-4 text-xl">
        <Link href="/learn" className="rounded-lg border-2 p-4 focus:outline-4">
          🎓 Học sinh – Học cùng gia sư
        </Link>
        <Link href="/dashboard" className="rounded-lg border-2 p-4 focus:outline-4">
          👩‍🏫 Giáo viên – Teacher Dashboard
        </Link>
        <Link href="/curation" className="rounded-lg border-2 p-4 focus:outline-4">
          📚 Giáo viên – Kiểm duyệt nội dung
        </Link>
        <Link href="/monitor" className="rounded-lg border-2 p-4 focus:outline-4">
          📈 Giám sát agent và LLM
        </Link>
      </nav>
    </main>
  );
}
