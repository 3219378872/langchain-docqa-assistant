"""Streamlit 网页界面：上传文档 → 构建知识库 → 多轮问答（回答附带出处）。

启动方式：streamlit run app.py
"""

from __future__ import annotations

import operator
import tempfile
from functools import reduce
from pathlib import Path

import streamlit as st
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from docqa import (
    BM25Retriever,
    DocumentFileLoader,
    Settings,
    build_llm,
    build_rag_chain,
    describe_source,
    split_documents,
)

SAMPLE_DIR = Path(__file__).parent / "data" / "samples"

st.set_page_config(page_title="智能文档问答助手", page_icon="📚", layout="wide")


def init_state() -> None:
    defaults = {"messages": [], "history": [], "retriever": None, "kb_files": [], "kb_chunks": 0}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def clear_chat() -> None:
    st.session_state.messages = []
    st.session_state.history = []


def build_knowledge_base(files: list[tuple[str, Path]], chunk_size: int) -> None:
    """加载文件、切分片段并建立 BM25 索引；单个文件读取失败不影响其他文件。"""
    docs: list[Document] = []
    for name, path in files:
        try:
            docs.extend(DocumentFileLoader(path, source_name=name).load())
        except Exception as e:  # 把具体原因展示给用户，比如 PDF 加密、文件损坏
            st.warning(f"读取「{name}」失败：{e}")
    if not docs:
        st.error("没有从文件中读取到任何文本内容。")
        return
    chunks = split_documents(docs, chunk_size=chunk_size)
    st.session_state.retriever = BM25Retriever(docs=chunks)
    st.session_state.kb_files = sorted({doc.metadata["source"] for doc in docs})
    st.session_state.kb_chunks = len(chunks)
    clear_chat()  # 知识库换了，之前对话里的出处已经对不上，一并清空


def build_from_uploads(uploaded_files: list, chunk_size: int) -> None:
    """把上传的文件写入临时目录后再解析（临时文件名用序号，原始文件名作为出处）。"""
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for i, uploaded in enumerate(uploaded_files):
            path = Path(tmp) / f"{i}{Path(uploaded.name).suffix}"
            path.write_bytes(uploaded.getvalue())
            files.append((uploaded.name, path))
        build_knowledge_base(files, chunk_size)


def show_sources(docs: list[Document], query: str, question: str) -> None:
    """在回答下方展示检索用的问题和参考片段。"""
    if query.strip() != question.strip():
        st.caption(f"🔍 检索用的问题：{query.strip()}")
    if not docs:
        st.caption("没有检索到相关片段")
        return
    with st.expander(f"📎 参考来源（{len(docs)} 个片段）"):
        for i, doc in enumerate(docs, start=1):
            st.markdown(f"**[{i}] {describe_source(doc)}**　BM25 得分：{doc.metadata['score']}")
            st.code(doc.page_content, language=None, wrap_lines=True)


init_state()
try:
    settings = Settings.from_env()
except ValueError as e:
    st.error(str(e))
    st.stop()
if "llm" not in st.session_state:
    st.session_state.llm = build_llm(settings)

with st.sidebar:
    st.header("📂 知识库")
    uploaded_files = st.file_uploader(
        "上传文档",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="支持 PDF、Word（.docx）、TXT 和 Markdown，可以一次上传多个文件",
    )
    chunk_size = st.slider(
        "片段长度（字符）",
        200,
        1500,
        500,
        step=100,
        help="文档会先切成这个长度的片段，再建立检索索引",
    )
    col1, col2 = st.columns(2)
    if col1.button("构建知识库", type="primary", disabled=not uploaded_files, width="stretch"):
        with st.spinner("正在解析文档…"):
            build_from_uploads(uploaded_files, chunk_size)
    if col2.button("加载示例文档", key="load_samples", width="stretch"):
        build_knowledge_base([(p.name, p) for p in sorted(SAMPLE_DIR.glob("*.md"))], chunk_size)
    if st.session_state.retriever is not None:
        file_count, chunk_count = len(st.session_state.kb_files), st.session_state.kb_chunks
        st.success(f"已加载 {file_count} 个文件，共 {chunk_count} 个片段")
        st.caption("、".join(st.session_state.kb_files))

    st.header("⚙️ 问答设置")
    top_k = st.slider("每次检索的片段数", 1, 8, 4)
    st.button("清空对话", on_click=clear_chat, width="stretch")
    st.divider()
    st.caption(
        f"模型：`{settings.model}`  \n"
        f"推理强度：`{settings.reasoning_effort or '默认'}`  \n"
        f"接口：`{settings.base_url}`"
    )

st.title("📚 智能文档问答助手")
st.caption(
    "基于 LangChain + DeepSeek 的 RAG 应用："
    "先从文档中检索相关片段，再让大模型依据原文作答并标注出处。"
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            show_sources(message["docs"], message["query"], message["question"])

retriever: BM25Retriever | None = st.session_state.retriever
if retriever is None:
    st.info("👈 请先在左侧上传文档并点击「构建知识库」，或者点击「加载示例文档」快速体验。")

question = st.chat_input(
    "输入你的问题，例如：MIT 和 GPL 许可证有什么区别？", disabled=retriever is None
)
if question and retriever is not None:
    with st.chat_message("user"):
        st.markdown(question)

    retriever.k = top_k
    chain = build_rag_chain(st.session_state.llm, retriever)
    chunks: list[dict] = []

    def stream_answer():
        """边接收链的输出边保存，只把 answer 部分逐字交给界面显示。"""
        for chunk in chain.stream({"question": question, "chat_history": st.session_state.history}):
            chunks.append(chunk)
            if "answer" in chunk:
                yield chunk["answer"]

    with st.chat_message("assistant"):
        try:
            with st.spinner("正在检索文档并思考…"):
                answer = st.write_stream(stream_answer())
        except Exception as e:
            st.error(f"调用大模型失败：{e}")
            st.stop()
        result = reduce(operator.add, chunks)  # 流式输出的各个片段可以直接相加，拼回完整结果
        show_sources(result["docs"], result["standalone_question"], question)

    st.session_state.history += [HumanMessage(question), AIMessage(answer)]
    st.session_state.messages += [
        {"role": "user", "content": question},
        {
            "role": "assistant",
            "content": answer,
            "docs": result["docs"],
            "query": result["standalone_question"],
            "question": question,
        },
    ]
