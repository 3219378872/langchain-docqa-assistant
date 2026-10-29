import pytest

from docqa.config import DEFAULT_BASE_URL, Settings, build_llm


def test_defaults_use_deepseek_with_high_reasoning():
    settings = Settings.from_env({"LLM_API_KEY": "sk-test"})
    assert settings.base_url == DEFAULT_BASE_URL
    assert settings.model == "deepseek-v4.1-flash"
    assert settings.reasoning_effort == "high"


def test_reads_and_normalizes_env_values():
    settings = Settings.from_env(
        {
            "LLM_API_KEY": " sk-test ",
            "LLM_BASE_URL": "http://localhost:11434/v1",
            "LLM_MODEL": "qwen3",
            "LLM_REASONING_EFFORT": "Medium",
        }
    )
    assert settings == Settings(
        api_key="sk-test",
        base_url="http://localhost:11434/v1",
        model="qwen3",
        reasoning_effort="medium",
    )


def test_empty_reasoning_effort_means_not_sent():
    settings = Settings.from_env({"LLM_API_KEY": "sk-test", "LLM_REASONING_EFFORT": ""})
    assert settings.reasoning_effort is None
    assert build_llm(settings).reasoning_effort is None


def test_missing_api_key_raises():
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        Settings.from_env({})


def test_build_llm_uses_settings():
    llm = build_llm(Settings(api_key="sk-test", base_url="http://example.com/v1", model="m"))
    assert llm.model_name == "m"
    assert llm.openai_api_base == "http://example.com/v1"
    assert llm.reasoning_effort == "high"
