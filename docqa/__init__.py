"""docqa：基于 LangChain 的智能文档问答（RAG）核心模块。"""

from docqa.chain import build_rag_chain, describe_source, format_docs
from docqa.config import Settings, build_llm
from docqa.loaders import (
    SUPPORTED_SUFFIXES,
    DocumentFileLoader,
    load_documents,
    split_documents,
)
from docqa.retriever import BM25Retriever, tokenize

__version__ = "1.0.0"

__all__ = [
    "SUPPORTED_SUFFIXES",
    "BM25Retriever",
    "DocumentFileLoader",
    "Settings",
    "build_llm",
    "build_rag_chain",
    "describe_source",
    "format_docs",
    "load_documents",
    "split_documents",
    "tokenize",
]
