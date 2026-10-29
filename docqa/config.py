"""配置管理：从环境变量（或 .env 文件）读取大模型接口参数，并创建 LangChain 聊天模型。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "https://api.weblearning.fun/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_REASONING_EFFORT = "high"


@dataclass(frozen=True)
class Settings:
    """大模型接口配置。"""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    timeout: float = 120.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """读取配置。不传 environ 时，先加载项目根目录的 .env，再读取系统环境变量。"""
        if environ is None:
            load_dotenv()
            environ = os.environ
        api_key = environ.get("LLM_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "未配置 LLM_API_KEY：请把 .env.example 复制为 .env，并填入你的 API Key"
            )
        return cls(
            api_key=api_key,
            base_url=environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL,
            model=environ.get("LLM_MODEL", "").strip() or DEFAULT_MODEL,
            # 显式设成空值表示不发送 reasoning_effort（有些模型不支持这个参数）
            reasoning_effort=(
                environ.get("LLM_REASONING_EFFORT", DEFAULT_REASONING_EFFORT).strip().lower()
                or None
            ),
        )


def build_llm(settings: Settings) -> ChatOpenAI:
    """创建对接 OpenAI 兼容接口的聊天模型，DeepSeek、Ollama 等都可以通过 base_url 接入。"""
    return ChatOpenAI(
        model=settings.model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        reasoning_effort=settings.reasoning_effort,
        timeout=settings.timeout,
        max_retries=2,
    )
