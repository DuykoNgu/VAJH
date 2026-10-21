from tests.conftest import running_app


async def test_tts_returns_audio_with_maths_spoken(test_database):
    async with running_app() as client:
        r = await client.post("/tts", json={"text": "y = 2x + 1"})
    assert r.status_code == 200 and r.content == "FAKEAUDIO:y bằng hai x cộng một".encode()


async def test_tts_rejects_empty_and_too_long(test_database):
    async with running_app() as client:
        assert (await client.post("/tts", json={"text": ""})).status_code == 422
        assert (await client.post("/tts", json={"text": "   "})).status_code == 422
        assert (await client.post("/tts", json={"text": "a" * 601})).status_code == 422


async def test_stream_speaks_sentences_in_order_with_maths_spoken(test_database):
    async with running_app() as client:
        r = await client.post("/tts/stream", json={"sentences": ["Phần 1.", "y = 2x + 1", "Em hiểu chưa?"]})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/x-fake"
    assert r.content.decode().splitlines() == ["FAKEAUDIO:Phần một.", "FAKEAUDIO:y bằng hai x cộng một",
                                               "FAKEAUDIO:Em hiểu chưa?"]


async def test_stream_rejects_bad_requests(test_database):
    async with running_app() as client:
        for body in ({"sentences": []}, {"sentences": ["ok", "  "]}, {"sentences": ["a"] * 61},
                     {"sentences": ["a" * 601]}):
            assert (await client.post("/tts/stream", json=body)).status_code == 422, body
