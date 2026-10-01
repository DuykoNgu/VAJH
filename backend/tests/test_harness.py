def test_test_database_is_migrated(db):
    names = [r[0] for r in db.execute("SELECT filename FROM schema_migrations ORDER BY 1")]
    assert names == ["000_init", "001_student_language_agent_name"]
