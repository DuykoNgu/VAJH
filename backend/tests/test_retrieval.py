import pytest

from app.ai.fakes import FakeEmbeddings
from app.retrieval import search_knowledge
from app.storage import relational
from tests.conftest import GRAPH_DESCRIPTION


@pytest.fixture
async def pool(test_database):
    await relational.open_pool(test_database)
    yield
    await relational.close_pool()


pytestmark = pytest.mark.usefixtures("pool")


async def test_lesson_scoped_search(textbook):
    results = await search_knowledge(FakeEmbeddings(), GRAPH_DESCRIPTION, lesson_id=textbook["lessons"][2], k=6)
    assert {r.lesson_title for r in results} == {"Bài 2. Đồ thị của hàm số bậc nhất"}
    assert results[0].kind == "figure" and results[0].content == GRAPH_DESCRIPTION and results[0].unreviewed
    assert results[0].page == 5


async def test_no_lesson_searches_everything(textbook):
    assert len(await search_knowledge(FakeEmbeddings(), "bất kỳ", k=10)) == 3


async def test_rejected_figure_excluded(textbook):
    textbook["add"](2, "Hình bị từ chối", kind="figure", review="rejected")
    results = await search_knowledge(FakeEmbeddings(), "Hình bị từ chối", lesson_id=textbook["lessons"][2], k=10)
    assert "Hình bị từ chối" not in {r.content for r in results}
