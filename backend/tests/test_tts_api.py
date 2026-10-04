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
