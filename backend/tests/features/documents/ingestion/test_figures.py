import pymupdf

from app.features.documents.ingestion.figures import extract_figures, find_figure_rects
from tests import pdfs


def pages(data):
    return pymupdf.open(stream=data, filetype="pdf")


def test_vector_graph_found_with_its_labels_and_decorations_ignored():
    with pages(pdfs.figures_pdf()) as doc:
        (rect,) = find_figure_rects(doc[0], 0.02)       # đồ thị; icon 10x10 và khung viền trang bị bỏ
        for label in ("x", "y", "O", "1"):
            (box,) = [pymupdf.Rect(w[:4]) for w in doc[0].get_text("words") if w[4] == label]
            assert rect.contains(box), label
        assert rect.width < 300                         # không nuốt cả khung trang


def test_embedded_image_found():
    with pages(pdfs.figures_pdf()) as doc:
        (rect,) = find_figure_rects(doc[1], 0.02)
        assert rect == pymupdf.Rect(150, 450, 450, 650)


def test_text_only_and_scanned_pages_have_no_figures():
    with pages(pdfs.figures_pdf()) as doc:
        assert find_figure_rects(doc[2], 0.02) == []
    with pages(pdfs.special_pages_pdf()) as doc:
        assert find_figure_rects(doc[3], 0.02) == []    # ảnh chiếm cả trang = trang scan, không phải hình


def test_extract_renders_png_crops():
    with pages(pdfs.lessons_pdf()) as doc:
        (fig,) = extract_figures(doc[5], 0.02)
        assert (fig.page, fig.index) == (6, 1) and fig.png.startswith(b"\x89PNG")
        assert pymupdf.Pixmap(fig.png).width > fig.rect.width  # render ở 200 dpi > 72 dpi
