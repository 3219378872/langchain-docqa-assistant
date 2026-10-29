"""RAG 问答链：问题改写 → BM25 检索 → 组装参考资料 → 大模型生成带出处的回答。"""

from __future__ import annotations

from operator import itemgetter
from typing import Any

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough

CONDENSE_SYSTEM_PROMPT = (
    "你负责改写问题，不负责回答问题。"
    "请结合对话历史，把用户最新的问题改写成一个不依赖上下文也能看懂的完整问题，"
    "补全省略的主语和“它”“这个”之类的指代。只输出改写后的问题。"
)

ANSWER_SYSTEM_PROMPT = """你是一个严谨的文档问答助手，请依据下面的【参考资料】回答用户的问题。

要求：
1. 回答准确、条理清晰，使用与用户提问相同的语言；
2. 用到某段资料时，在相应句子末尾标注资料编号，例如 [1]、[2]；
3. 只使用参考资料中的信息，不要补充资料里没有的内容；
4. 如果参考资料中没有能回答问题的信息，请直接说“文档中没有找到相关信息”，不要编造。

【参考资料】
{context}"""


def describe_source(doc: Document) -> str:
    """生成片段的出处说明，例如“report.pdf 第 3 页”。"""
    source = doc.metadata.get("source", "未知来源")
    page = doc.metadata.get("page")
    return f"{source} 第 {page} 页" if page else source


def format_docs(docs: list[Document]) -> str:
    """把检索到的片段编号后拼接成参考资料文本。"""
    if not docs:
        return "（没有检索到相关内容）"
    return "\n\n".join(
        f"[{i}] 出处：{describe_source(doc)}\n{doc.page_content}"
        for i, doc in enumerate(docs, start=1)
    )


def build_rag_chain(
    llm: BaseChatModel, retriever: BaseRetriever, max_history_messages: int = 6
) -> Runnable[dict[str, Any], dict[str, Any]]:
    """用 LCEL 组装支持多轮对话的 RAG 链。

    输入：{"question": 用户问题, "chat_history": 历史消息列表（可省略）}
    输出：在输入基础上增加 standalone_question（检索用的问题）、docs（检索到的片段）
    和 answer（回答）。调用 .stream() 时 answer 会逐字流式返回。
    """
    condense_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CONDENSE_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    answer_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ANSWER_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    condense_chain = condense_prompt | llm | StrOutputParser()

    def recent_history(inputs: dict[str, Any]) -> list:
        # 只保留最近几轮对话，避免历史越积越长、浪费 token
        history = list(inputs.get("chat_history") or [])
        return history[-max_history_messages:] if max_history_messages > 0 else []

    def standalone_question(inputs: dict[str, Any]) -> str | Runnable:
        # 第一轮没有历史，直接用原问题检索；追问时先改写，解决“它的缺点呢？”这类指代问题
        return condense_chain if inputs["chat_history"] else inputs["question"]

    answer_chain = (
        RunnablePassthrough.assign(context=lambda x: format_docs(x["docs"]))
        | answer_prompt
        | llm
        | StrOutputParser()
    )
    return (
        RunnablePassthrough.assign(chat_history=recent_history)
        .assign(standalone_question=RunnableLambda(standalone_question))
        .assign(docs=itemgetter("standalone_question") | retriever)
        .assign(answer=answer_chain)
        .with_config(run_name="DocQA")
    )
