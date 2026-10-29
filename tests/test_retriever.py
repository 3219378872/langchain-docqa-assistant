from langchain_core.documents import Document

from docqa.retriever import BM25Retriever, tokenize

DOCS = [
    Document(
        page_content="MIT 许可证非常宽松，只要求保留版权声明和许可声明。",
        metadata={"source": "license.md"},
    ),
    Document(
        page_content="GPL 是著佐权许可证，分发派生作品时必须公开源代码。",
        metadata={"source": "license.md"},
    ),
    Document(
        page_content="git rebase 会改写提交历史，得到线性的提交记录。",
        metadata={"source": "git.md"},
    ),
]


def test_tokenize_removes_punctuation_and_stopwords():
    tokens = set(tokenize("开源许可证有哪些？MIT和GPL的区别是什么"))
    assert {"开源", "许可证", "mit", "gpl", "区别"} <= tokens
    assert not tokens & {"？", "的", "和", "是", "有", "哪些", "什么"}


def test_most_relevant_chunk_ranks_first():
    results = BM25Retriever(docs=DOCS).invoke("rebase 会改写历史吗？")
    assert results[0].page_content == DOCS[2].page_content
    assert results[0].metadata["source"] == "git.md"
    assert results[0].metadata["score"] > 0


def test_results_are_sorted_and_limited_by_k():
    results = BM25Retriever(docs=DOCS, k=2).invoke("GPL 许可证")
    assert len(results) == 2
    assert results[0].page_content == DOCS[1].page_content
    assert results[0].metadata["score"] >= results[1].metadata["score"]


def test_unrelated_query_returns_nothing():
    assert BM25Retriever(docs=DOCS).invoke("今天天气怎么样") == []


def test_single_chunk_corpus_still_has_positive_score():
    # 只有一个片段时，经典 BM25 的 IDF 公式会算出负数；这里的平滑 IDF 不会
    results = BM25Retriever(docs=DOCS[:1]).invoke("MIT 许可证")
    assert len(results) == 1
    assert results[0].metadata["score"] > 0


def test_retrieval_does_not_modify_indexed_documents():
    BM25Retriever(docs=DOCS).invoke("许可证")
    assert "score" not in DOCS[0].metadata


def test_empty_knowledge_base():
    assert BM25Retriever(docs=[]).invoke("任何问题") == []
