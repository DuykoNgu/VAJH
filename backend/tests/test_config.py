import pytest

from app.config import ConfigError, load_settings

BASE = {"DATABASE_URL": "postgresql://x@localhost/db", "REDIS_URL": "redis://localhost:6379"}


@pytest.fixture
def env(monkeypatch):
    for name in ["DATABASE_URL", "REDIS_URL", "APP_ENV", "AUTH_MODE", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                 "LLM_PROVIDER", "EMBEDDING_PROVIDER", "OPENAI_LLM_MODEL", "LLM_ROUTES", "FILES_DIR"]:
        monkeypatch.delenv(name, raising=False)

    def set_env(**values):
        for k, v in values.items():
            monkeypatch.setenv(k, v)
        return load_settings(_env_file=None)

    return set_env


def test_missing_required_setting_is_named(env):
    with pytest.raises(ConfigError) as e:
        env(REDIS_URL="redis://localhost:6379")
    assert "DATABASE_URL" in str(e.value)


def test_provider_key_optional_outside_production(env):
    s = env(**BASE, APP_ENV="test")
    assert s.anthropic_api_key is None
    assert s.llm_provider == "fake" and s.embedding_provider == "fake"


def test_provider_key_required_in_production(env):
    with pytest.raises(ConfigError) as e:
        env(**BASE, APP_ENV="production", LLM_PROVIDER="anthropic", OPENAI_API_KEY="k")
    assert "ANTHROPIC_API_KEY" in str(e.value)


def test_openai_key_required_in_production(env):
    with pytest.raises(ConfigError) as e:
        env(**BASE, APP_ENV="production", OPENAI_LLM_MODEL="m")
    assert "OPENAI_API_KEY" in str(e.value)


def test_default_provider_is_openai_with_model_from_setting(env):
    s = env(**BASE, APP_ENV="development", OPENAI_LLM_MODEL="some-openai-model")
    assert s.llm_provider == "openai"
    assert {r.model for r in s.llm_routes.values()} == {"some-openai-model"}
    assert s.llm_routes["orchestrator"].effort == "low"


def test_openai_model_required_in_production(env):
    with pytest.raises(ConfigError) as e:
        env(**BASE, APP_ENV="production", OPENAI_API_KEY="k")
    assert "OPENAI_LLM_MODEL" in str(e.value)


def test_openai_model_optional_in_development(env):
    s = env(**BASE, APP_ENV="development")
    assert s.llm_routes["tutor"].model == ""  # lỗi ở lần gọi LLM đầu tiên, không phải lúc khởi động


def test_anthropic_provider_defaults_to_claude(env):
    s = env(**BASE, APP_ENV="development", LLM_PROVIDER="anthropic")
    assert {r.model for r in s.llm_routes.values()} == {"claude-opus-5-5"}


def test_dev_identity_refused_in_production(env):
    with pytest.raises(ConfigError) as e:
        env(**BASE, APP_ENV="production", OPENAI_API_KEY="k", OPENAI_LLM_MODEL="m")
    assert "AUTH_MODE" in str(e.value) and "APP_ENV" in str(e.value)


def test_route_override(env, monkeypatch):
    monkeypatch.setenv("LLM_ROUTES", '{"orchestrator": {"model": "other-model", "effort": "low"}}')
    s = env(**BASE, APP_ENV="test")
    assert s.llm_routes["orchestrator"].model == "other-model"
    assert s.llm_routes["tutor"].model == "claude-opus-5-5" and s.llm_routes["tutor"].effort == "low"


def test_ingestion_defaults_and_relative_files_dir(env):
    from app.config import BACKEND_DIR

    s = env(**BASE, APP_ENV="test", FILES_DIR="data/x")
    assert s.files_dir == BACKEND_DIR / "data" / "x"
    assert (s.file_store, s.max_upload_mb, s.max_pages, s.chunk_max_chars, s.chunk_overlap_chars) == \
        ("local", 50, 400, 1500, 200)
    assert (s.figure_min_area_ratio, s.llm_concurrency, s.ingest_timeout_s) == (0.02, 4, 3600)
