from app.migrate import migration_files


def test_test_database_is_migrated(db):
    names = [r[0] for r in db.execute("SELECT filename FROM schema_migrations ORDER BY 1")]
    assert names == [f.stem for f in migration_files()] and "003_document_processing" in names
