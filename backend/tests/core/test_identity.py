import pytest
from fastapi import Depends

from app.core.identity import UserContext, current_student, current_teacher
from tests.conftest import as_user, override_identity


@pytest.fixture
async def app_client(client):
    """App thật + 2 endpoint thử: một cần học sinh, một cần giáo viên."""
    async def student_endpoint(user: UserContext = Depends(current_student)):
        return {"username": user.username, "role": user.role, "language": user.language}

    async def teacher_endpoint(user: UserContext = Depends(current_teacher)):
        return {"username": user.username, "role": user.role}

    client.app.add_api_route("/_t/student", student_endpoint)
    client.app.add_api_route("/_t/teacher", teacher_endpoint)
    return client


async def test_student_context_fields(app_client, make_student):
    uid = make_student("minh5a")
    r = await app_client.get("/me")
    assert r.json() == {"mode": "dev", "user_id": str(uid), "full_name": "Em Minh", "username": "minh5a",
                        "role": "student", "grade": 5, "language": "vi", "speech_rate": 1.0}


async def test_teacher_context_fields(app_client, make_teacher):
    uid = make_teacher("colan")
    r = await app_client.get("/me", headers=as_user("colan"))
    assert r.json()["role"] == "teacher" and r.json()["user_id"] == str(uid) and r.json()["grade"] is None


async def test_default_student(app_client, make_student):
    make_student("minh5a")
    assert (await app_client.get("/_t/student")).json()["username"] == "minh5a"


async def test_default_teacher(app_client, make_teacher):
    make_teacher("colan")
    assert (await app_client.get("/_t/teacher")).json()["username"] == "colan"


async def test_header_selects_another_student_normalised(app_client, make_student):
    make_student("minh5a")
    make_student("hana5a", language="ja", full_name="Hana")
    r = await app_client.get("/_t/student", headers=as_user("Hana5A "))
    assert r.json() == {"username": "hana5a", "role": "student", "language": "ja"}


async def test_header_names_user_with_wrong_role(app_client, make_teacher):
    make_teacher("colan")
    r = await app_client.get("/_t/student", headers=as_user("colan"))
    assert r.status_code == 400 and "colan" in r.json()["detail"] and "not a student" in r.json()["detail"]


async def test_unknown_user(app_client):
    r = await app_client.get("/me", headers=as_user("nobody"))
    assert r.status_code == 400 and "'nobody' does not exist" in r.json()["detail"]


async def test_default_user_not_seeded(app_client):
    r = await app_client.get("/_t/student")
    assert r.status_code == 503 and "python -m app.seed" in r.json()["detail"]


async def test_me_japanese_student(app_client, make_student):
    make_student("hana5a", language="ja")
    r = await app_client.get("/me", headers=as_user("hana5a"))
    assert r.json()["role"] == "student" and r.json()["language"] == "ja"


async def test_dependency_override_helper(app_client, make_student):
    uid = make_student("minh5a")
    fake = UserContext(uid, "Em Minh", "minh5a", "student", 5, "vi", 1.0)
    override_identity(app_client.app, fake)
    assert (await app_client.get("/_t/student", headers=as_user("nobody"))).json()["username"] == "minh5a"
