"""Nạp sách giáo khoa (không cần danh tính):

    python -m app.features.documents.ingest sgk/toan5-tap2.pdf --title "Toán 5 tập 2" --subject toan --grade 5

Xử lý ngay trong tiến trình (không cần worker) rồi in tóm tắt. PDF SGK không commit vào repo (bản quyền).
"""
import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

from app.config import get_settings
from app.core.storage import relational
from app.features.documents.ingestion.pdf import PdfError, open_pdf
from app.features.documents.ingestion.pipeline import (
    Deps,
    IngestionError,
    mark_failed,
    process_document,
)

SUBJECTS = ["toan", "ngu_van", "tieng_viet", "tieng_anh", "khtn", "vat_ly", "hoa_hoc", "sinh_hoc", "lich_su",
            "dia_ly", "lich_su_dia_ly", "tin_hoc", "khac"]  # khớp enum `subject` trong migrations/000_init.sql


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="python -m app.features.documents.ingest", description="Nạp một sách giáo khoa PDF")
    parser.add_argument("file", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subject", required=True, choices=SUBJECTS)
    parser.add_argument("--grade", required=True, type=int, choices=range(1, 13), metavar="1-12")
    return parser.parse_args(argv)


async def run(args, deps: Deps) -> int:
    data = args.file.read_bytes()
    try:
        open_pdf(data, deps.settings.max_pages).close()
    except PdfError as e:
        print(f"ERROR: {args.file}: {e}", file=sys.stderr)
        return 1
    doc_id = uuid.uuid4()
    key = f"sgk/{doc_id}.pdf"
    await deps.files.put(key, data, "application/pdf")
    async with relational.connection() as conn:
        await conn.execute("INSERT INTO documents (id, kind, title, subject, grade, storage_key)"
                           " VALUES (%s, 'textbook', %s, %s, %s, %s)",
                           (doc_id, args.title, args.subject, args.grade, key))
    print(f"document {doc_id}: processing {args.file.name} ...", flush=True)
    try:
        s = await process_document(doc_id, deps)
    except IngestionError as e:
        await mark_failed(doc_id, str(e))
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"document {doc_id}: ready\n"
          f"  pages {s.pages} (OCR {s.ocr_pages}) | lessons {s.lessons} (from {s.lesson_source})\n"
          f"  text chunks {s.text_chunks} | figure chunks {s.figure_chunks} (pending review) | "
          f"skipped figures {s.skipped_figures} | decorative {s.decorative_figures}\n"
          f"  outlined lessons {s.outlined_lessons}/{s.lessons}")
    return 0


class _Progress(logging.Formatter):
    """Tiến trình nạp sách trên CLI: bước, từng trang OCR / tìm hình, từng lượt gọi LLM; cộng dồn token theo route."""

    def __init__(self):
        super().__init__()
        self.tokens: dict[str, list[int]] = {}  # route → [lượt, token vào, token ra, mili giây]

    def format(self, record):
        r, message = record.__dict__, record.getMessage()
        if message == "llm call":
            total = self.tokens.setdefault(r["route"], [0, 0, 0, 0])
            for i, v in enumerate((1, r["input_tokens"] or 0, r["output_tokens"] or 0, r["latency_ms"])):
                total[i] += v
            return (f"  llm  {r['route']:<14} {r['latency_ms'] / 1000:6.1f}s  in={r['input_tokens']} "
                    f"out={r['output_tokens']} {r['outcome']}")
        if message == "step":
            return f"▶ bước: {r['step']}"
        if message == "ocr page":
            source = f"máy {r['local_s']:.1f}s, {r['raw_chars']} ký tự → sửa" if r["source"] == "local" else "LLM đọc ảnh"
            return f"  ocr  trang {r['page']:>3} ({r['done']}/{r['total']})  {source} → {r['chars']} ký tự"
        if message == "layout page":
            return f"  hình trang {r['page']:>3}  {r['figures']} hình  {r['seconds']:.1f}s"
        return f"  {message}"

    def summary(self) -> str:
        lines = ["Tổng LLM theo route:  lượt   token vào   token ra   thời gian"]
        for route, (n, tin, tout, ms) in sorted(self.tokens.items()):
            lines.append(f"  {route:<18} {n:>5} {tin:>11,} {tout:>10,} {ms / 1000:>9.0f}s")
        return "\n".join(lines)


async def main(argv=None) -> int:
    args = parse_args(argv)
    progress = _Progress()
    handler = logging.StreamHandler()
    handler.setFormatter(progress)
    logging.getLogger("lusia").addHandler(handler)
    logging.getLogger("lusia").setLevel(logging.INFO)
    if not args.file.is_file():
        print(f"ERROR: {args.file} not found", file=sys.stderr)
        return 1
    settings = get_settings()
    await relational.open_pool(settings.database_url)
    try:
        return await run(args, Deps.from_settings(settings))
    finally:
        await relational.close_pool()
        print(progress.summary())


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
