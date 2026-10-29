from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from docqa.chain import build_rag_chain, format_docs
from docqa.retriever import BM25Retriever

DOCS = [
    Document(
        page_content="Apache 2.0 包含明确的专利授权条款。",
        metadata={"source": "license.pdf", "page": 3},
    ),
    Document(
        page_content="git revert 会新建一个提交来抵消之前的修改。", metadata={"source": "git.md"}
    ),
]


class PromptRecorder(BaseCallbackHandler):
    """记录每次发给大模型的消息列表，方便检查提示词。"""

    def __init__(self) -> None:
        self.prompts = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.append(messages[0])


def test_first_question_is_used_directly_for_retrieval():
    llm = FakeListChatModel(responses=["有，Apache 2.0 包含专利授权条款 [1]。"])
    recorder = PromptRecorder()
    chain = build_rag_chain(llm, BM25Retriever(docs=DOCS, k=1))

    result = chain.invoke(
        {"question": "Apache 2.0 有专利条款吗？"}, config={"callbacks": [recorder]}
    )

    assert result["standalone_question"] == "Apache 2.0 有专利条款吗？"
    assert [doc.metadata["source"] for doc in result["docs"]] == ["license.pdf"]
    assert result["answer"] == "有，Apache 2.0 包含专利授权条款 [1]。"
    assert len(recorder.prompts) == 1  # 第一轮不需要改写问题，只调用一次大模型
    system_prompt = recorder.prompts[0][0].content
    assert "[1] 出处：license.pdf 第 3 页\nApache 2.0 包含明确的专利授权条款。" in system_prompt


def test_follow_up_question_is_rewritten_before_retrieval():
    # 第一次调用模型返回改写后的问题，第二次返回最终回答
    llm = FakeListChatModel(responses=["git revert 的作用是什么？", "它会新建一个提交 [1]。"])
    chain = build_rag_chain(llm, BM25Retriever(docs=DOCS, k=1))
    history = [HumanMessage("git 怎么撤销提交？"), AIMessage("可以用 git revert。")]

    # 原问题“它的作用是什么？”本身检索不到任何内容，必须依靠改写
    result = chain.invoke({"question": "它的作用是什么？", "chat_history": history})

    assert result["standalone_question"] == "git revert 的作用是什么？"
    assert [doc.metadata["source"] for doc in result["docs"]] == ["git.md"]
    assert result["answer"] == "它会新建一个提交 [1]。"


def test_chat_history_is_trimmed():
    llm = FakeListChatModel(responses=["改写后的问题", "回答"])
    recorder = PromptRecorder()
    chain = build_rag_chain(llm, BM25Retriever(docs=DOCS), max_history_messages=2)
    history = [HumanMessage(f"问题{i}") if i % 2 == 0 else AIMessage(f"回答{i}") for i in range(10)]

    result = chain.invoke(
        {"question": "继续", "chat_history": history}, config={"callbacks": [recorder]}
    )

    assert result["chat_history"] == history[-2:]
    assert len(recorder.prompts[-1]) == 4  # system + 2 条历史 + 当前问题


def test_stream_returns_answer_token_by_token():
    chain = build_rag_chain(FakeListChatModel(responses=["流式回答"]), BM25Retriever(docs=DOCS))
    chunks = list(chain.stream({"question": "Apache 专利"}))
    answer_parts = [chunk["answer"] for chunk in chunks if "answer" in chunk]
    assert len(answer_parts) > 1
    assert "".join(answer_parts) == "流式回答"


def test_format_docs():
    assert format_docs([]) == "（没有检索到相关内容）"
    text = format_docs(DOCS)
    assert text.startswith("[1] 出处：license.pdf 第 3 页\nApache 2.0")
    assert "\n\n[2] 出处：git.md\ngit revert" in text
