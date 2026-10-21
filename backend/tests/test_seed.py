from app.core.identity import NO_CREDENTIAL
from app.seed import seed


def test_seed_twice_is_idempotent(db, test_database):
    seed(test_database)
    seed(test_database)
    users = dict(db.execute("SELECT username, password_hash FROM users").fetchall())
    assert set(users) == {"colan", "minh8a", "hana8a"}
    assert set(users.values()) == {NO_CREDENTIAL}
    assert db.execute("SELECT count(*) FROM classes WHERE name = '8A'").fetchone()[0] == 1
    members = db.execute("SELECT u.username, s.language FROM class_students cs JOIN classes c ON c.id = cs.class_id"
                         " JOIN users u ON u.id = cs.student_id JOIN students s ON s.user_id = u.id"
                         " WHERE c.name = '8A' ORDER BY 1").fetchall()
    assert members == [("hana8a", "ja"), ("minh8a", "vi")]
    assert db.execute("SELECT count(*) FROM teachers").fetchone()[0] == 1
