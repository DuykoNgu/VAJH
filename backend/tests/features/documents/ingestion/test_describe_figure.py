import pytest

from app.config import get_settings
from app.core.ai.fakes import FakeLLM
from app.core.ai.llm import Refusal
from app.features.documents.tools import FigureDescription, ToolError, describe_figure
from tests.pdfs import png

GOOD = "Đây là đồ thị của hàm số y bằng hai x cộng một. Đường thẳng đi lên từ trái sang phải."


def llm(*replies):
    return FakeLLM(get_settings()).script(*replies)


async def test_graph_description_stored():
    fake = llm({"kind": "graph", "description": GOOD})
    result = await describe_figure(fake, png(), "Hình 1. Đồ thị hàm số")
    assert result == FigureDescription(kind="graph", description=GOOD)
    (call,) = fake.calls
    assert call["route"] == "vision_offline" and "khiếm thị" in call["system"]
    assert [b["type"] for b in call["messages"][0]["content"]] == ["image", "text"]


async def test_decorative_is_dropped():
    assert await describe_figure(llm({"kind": "decorative", "description": "Hoa văn"}), png()) is None


async def test_notation_triggers_one_rewrite():
    fake = llm({"kind": "graph", "description": "Đồ thị y = 2x + 1."}, {"kind": "graph", "description": GOOD})
    assert (await describe_figure(fake, png())).description == GOOD
    assert len(fake.calls) == 2 and "Viết lại" in fake.calls[1]["messages"][-1]["content"]


async def test_notation_kept_after_second_attempt():
    fake = llm({"kind": "graph", "description": "y = 2x + 1"}, {"kind": "graph", "description": "y = 2x + 1 nhé"})
    assert (await describe_figure(fake, png())).description == "y = 2x + 1 nhé"
    assert len(fake.calls) == 2


async def test_refusal_is_an_error():
    with pytest.raises(ToolError, match="refused"):
        await describe_figure(llm(Refusal("other")), png())
