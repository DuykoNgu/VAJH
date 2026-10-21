"""Tìm hình trên trang: ảnh nhúng (raster) và hình vẽ vector (đồ thị, sơ đồ hình học), rồi cắt ra PNG."""
from dataclasses import dataclass

import pymupdf

from app.features.documents.ingestion.pdf import render_png

MERGE_GAP = 12.0          # pt: các nét vẽ cách nhau ít hơn thế thuộc cùng một hình
MAX_AREA_RATIO = 0.9      # lớn hơn thế là nền/khung trang, không phải hình
MIN_SIDE = 8.0            # pt: mảnh hơn thế là đường kẻ/gạch chân
LABEL_MAX_CHARS = 4       # chữ ngắn sát hình (x, y, O, A, 1, 30°) là nhãn của hình
PADDING = 6.0


@dataclass(frozen=True)
class Figure:
    page: int          # 1-based
    index: int         # thứ tự trên trang, từ 1
    rect: pymupdf.Rect
    png: bytes


def _area(r: pymupdf.Rect) -> float:
    return abs(r.width * r.height)


def _merge(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Gộp các vùng chồng lên nhau cho tới khi không còn vùng nào chạm nhau."""
    rects = [pymupdf.Rect(r) for r in rects]
    merged = True
    while merged:
        merged = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rects[i].intersects(rects[j]):
                    rects[i] |= rects.pop(j)
                    merged = True
                    break
            if merged:
                break
    return rects


def _with_labels(rect: pymupdf.Rect, words: list) -> pymupdf.Rect:
    zone = pymupdf.Rect(rect.x0 - MERGE_GAP, rect.y0 - MERGE_GAP, rect.x1 + MERGE_GAP, rect.y1 + MERGE_GAP)
    for x0, y0, x1, y1, word, *_ in words:
        box = pymupdf.Rect(x0, y0, x1, y1)
        if len(word) <= LABEL_MAX_CHARS and box.intersects(zone):
            rect |= box
    return rect


def find_figure_rects(page: pymupdf.Page, min_area_ratio: float) -> list[pymupdf.Rect]:
    page_area = _area(page.rect)
    too_big = MAX_AREA_RATIO * page_area
    drawings = [d for d in page.get_drawings() if _area(d["rect"]) < too_big]  # bỏ khung/nền trang trước khi gom
    vector = page.cluster_drawings(drawings=drawings, x_tolerance=MERGE_GAP, y_tolerance=MERGE_GAP) if drawings else []
    words = page.get_text("words")
    candidates = [_with_labels(pymupdf.Rect(r), words) for r in vector]
    candidates += [pymupdf.Rect(info["bbox"]) for info in page.get_image_info()]
    kept = [r for r in _merge(candidates)
            if min_area_ratio * page_area <= _area(r) <= too_big and min(r.width, r.height) >= MIN_SIDE]
    return sorted(kept, key=lambda r: (r.y0, r.x0))


def extract_figures(page: pymupdf.Page, min_area_ratio: float) -> list[Figure]:
    figures = []
    for i, rect in enumerate(find_figure_rects(page, min_area_ratio), 1):
        clip = pymupdf.Rect(rect.x0 - PADDING, rect.y0 - PADDING, rect.x1 + PADDING, rect.y1 + PADDING) & page.rect
        figures.append(Figure(page.number + 1, i, clip, render_png(page, clip=clip)))
    return figures
