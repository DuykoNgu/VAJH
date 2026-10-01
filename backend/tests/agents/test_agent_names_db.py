from app.agents.base import AGENT_NAMES


def test_every_agent_name_is_accepted_by_the_database(db):
    uid = db.execute("INSERT INTO users (full_name, username, password_hash) VALUES ('Em B', 'emb', '!no-credential')"
                     " RETURNING id").fetchone()[0]
    db.execute("INSERT INTO students (user_id, grade) VALUES (%s, 8)", (uid,))
    sid = db.execute("INSERT INTO learning_sessions (student_id) VALUES (%s) RETURNING id", (uid,)).fetchone()[0]
    for name in AGENT_NAMES:
        db.execute("INSERT INTO messages (session_id, role, agent, content) VALUES (%s, 'assistant', %s, 'x')",
                   (sid, name))
    assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 7
