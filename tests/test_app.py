"""用 Streamlit 自带的 AppTest 对网页界面做冒烟测试，大模型替换为假模型，不需要联网。"""

from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from streamlit.testing.v1 import AppTest

import docqa

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")
FAKE_ANSWER = "MIT 许可证只要求保留版权声明和许可声明 [1]。"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setattr(
        docqa, "build_llm", lambda settings: FakeListChatModel(responses=[FAKE_ANSWER])
    )
    return AppTest.from_file(APP_PATH, default_timeout=60)


def test_chat_is_disabled_until_knowledge_base_is_ready(app):
    app.run()
    assert not app.exception
    assert app.title[0].value == "📚 智能文档问答助手"
    assert app.chat_input[0].disabled


def test_ask_question_with_sample_documents(app):
    app.run()
    app.button(key="load_samples").click().run()
    assert "已加载 3 个文件" in app.sidebar.success[0].value
    assert not app.chat_input[0].disabled

    app.chat_input[0].set_value("MIT 许可证有什么要求？").run()

    assert not app.exception
    user, assistant = app.chat_message
    assert user.markdown[0].value == "MIT 许可证有什么要求？"
    assert assistant.markdown[0].value == FAKE_ANSWER
    assert "参考来源" in assistant.expander[0].label
    assert "open_source_licenses.md" in assistant.expander[0].markdown[0].value
