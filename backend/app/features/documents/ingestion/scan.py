"""Trang scan (cả trang là một ảnh, không có lớp chữ): đọc chữ và tìm hình NGAY TRÊN MÁY, không tốn lượt gọi LLM.

- Chữ: OCR của macOS (Apple Vision, đọc được tiếng Việt). Máy không có (Linux) → None, pipeline OCR bằng LLM như cũ.
- Hình: model bố cục DocLayout-YOLO khoanh hình/bảng; LLM chỉ còn viết dữ kiện cho từng hình đã cắt.
"""
import functools
import logging
from pathlib import Path

import pymupdf

from app.features.documents.ingestion.figures import Figure
from app.features.documents.ingestion.pdf import render_png

log = logging.getLogger("lusia.ingestion")

SCAN_COVERAGE = 0.9      # một ảnh phủ ≥ 90% trang = trang scan
OCR_DPI = 150
LAYOUT_DPI = 110         # model bố cục chạy ở ảnh 1024 px; to hơn không chính xác hơn
FIGURE_CLASSES = {"figure", "table"}
MIN_CONFIDENCE = 0.3
PADDING = 6.0            # pt


def is_scanned(page: pymupdf.Page) -> bool:
    page_area = abs(page.rect)
    return any(abs(pymupdf.Rect(i["bbox"]) & page.rect) >= SCAN_COVERAGE * page_area for i in page.get_image_info())


def local_ocr(page: pymupdf.Page) -> str | None:
    """Chữ của trang theo thứ tự đọc, hoặc None nếu máy không có OCR của macOS."""
    try:
        import Vision
        from Foundation import NSData
    except ImportError:
        return None
    png = page.get_pixmap(dpi=OCR_DPI).tobytes("png")
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(NSData.dataWithBytes_length_(png, len(png)),
                                                                          None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["vi-VT", "en-US"])
    request.setUsesLanguageCorrection_(True)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"local OCR failed: {error}")
    return "\n".join(o.topCandidates_(1)[0].string() for o in request.results() or [])


@functools.cache
def _layout_model(path: str):
    from doclayout_yolo import (
        YOLOv10,  # nặng (torch): chỉ nạp khi thật sự gặp trang scan
    )

    return YOLOv10(path)


def keep_boxes(boxes: list[tuple[str, float, tuple[float, float, float, float]]], scale: float,
               page_rect: pymupdf.Rect, min_area_ratio: float) -> list[pymupdf.Rect]:
    """Khung hình/bảng đủ tin cậy và đủ lớn (bỏ biểu tượng, linh vật nhỏ), đổi từ pixel sang toạ độ trang."""
    kept = []
    for name, confidence, (x0, y0, x1, y1) in boxes:
        rect = pymupdf.Rect(x0 * scale, y0 * scale, x1 * scale, y1 * scale) & page_rect
        if name in FIGURE_CLASSES and confidence >= MIN_CONFIDENCE and abs(rect) >= min_area_ratio * abs(page_rect):
            kept.append(rect)
    return sorted(kept, key=lambda r: (r.y0, r.x0))


def detect_figures(page: pymupdf.Page, model_path: Path, min_area_ratio: float) -> list[Figure]:
    if not model_path.is_file():
        log.warning("layout model missing, figures on scanned pages skipped", extra={"path": str(model_path)})
        return []
    from PIL import Image

    pix = page.get_pixmap(dpi=LAYOUT_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    result = _layout_model(str(model_path)).predict(image, imgsz=1024, conf=MIN_CONFIDENCE, device="cpu",
                                                    verbose=False)[0]
    boxes = [(result.names[int(c)], float(s), tuple(b.tolist()))
             for c, s, b in zip(result.boxes.cls, result.boxes.conf, result.boxes.xyxy, strict=True)]
    figures = []
    for i, rect in enumerate(keep_boxes(boxes, 72 / LAYOUT_DPI, page.rect, min_area_ratio), 1):
        clip = pymupdf.Rect(rect.x0 - PADDING, rect.y0 - PADDING, rect.x1 + PADDING, rect.y1 + PADDING) & page.rect
        figures.append(Figure(page.number + 1, i, clip, render_png(page, clip=clip)))
    return figures
