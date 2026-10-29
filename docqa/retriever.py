"""中文 BM25 检索器：jieba 分词 + BM25 打分，继承 LangChain 的 BaseRetriever。

BM25 是搜索引擎常用的关键词相关性算法。它不需要 Embedding 向量接口，
建索引快、可以离线运行，检索结果也容易解释（命中了哪些词）。
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from typing import Any

import jieba
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import PrivateAttr

jieba.setLogLevel(logging.WARNING)  # 关闭 jieba 首次加载词典时打印的日志

# 常见的虚词、代词和疑问词，对区分文档内容没有帮助
STOPWORDS = frozenset(
    "的 了 着 过 和 与 及 或 而 是 在 有 就 都 也 还 又 被 把 让 给 对 从 向 于 "
    "这 那 这个 那个 这些 那些 它 它们 我 你 他 她 我们 你们 他们 "
    "吗 呢 吧 啊 呀 么 什么 怎么 怎样 如何 为什么 哪些 哪个 多少 请 请问 一下 一个".split()
)
_HAS_WORD_CHAR = re.compile(r"\w")


def tokenize(text: str) -> list[str]:
    """分词：jieba 搜索引擎模式（长词会再细切，提高召回），统一小写，去掉标点和停用词。"""
    tokens = (token.strip() for token in jieba.lcut_for_search(text.lower()))
    return [t for t in tokens if t and t not in STOPWORDS and _HAS_WORD_CHAR.search(t)]


class BM25Retriever(BaseRetriever):
    """基于倒排索引的 BM25 检索器。

    IDF 采用 Lucene 的平滑公式 log(1 + (N - df + 0.5) / (df + 0.5))，
    即使知识库只有一两个片段也不会出现负分。
    """

    docs: list[Document]
    k: int = 4  # 每次返回的片段数量
    k1: float = 1.5  # 词频饱和参数：同一个词出现越多次，加分越少
    b: float = 0.75  # 长度归一化参数：越长的片段，单个词的权重越低

    _postings: dict[str, list[tuple[int, int]]] = PrivateAttr(default_factory=dict)
    _idf: dict[str, float] = PrivateAttr(default_factory=dict)
    _doc_lens: list[int] = PrivateAttr(default_factory=list)
    _avgdl: float = PrivateAttr(default=1.0)

    def model_post_init(self, context: Any, /) -> None:
        """创建检索器时建立倒排索引：词 -> [(片段下标, 词频), ...]。"""
        super().model_post_init(context)
        postings: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
        doc_lens: list[int] = []
        for i, doc in enumerate(self.docs):
            term_freqs = Counter(tokenize(doc.page_content))
            doc_lens.append(sum(term_freqs.values()))
            for term, freq in term_freqs.items():
                postings[term].append((i, freq))

        n = len(self.docs)
        self._postings = dict(postings)
        self._doc_lens = doc_lens
        self._idf = {
            term: math.log(1 + (n - len(hits) + 0.5) / (len(hits) + 0.5))
            for term, hits in postings.items()
        }
        self._avgdl = (sum(doc_lens) / n) if sum(doc_lens) else 1.0

    def get_scores(self, query: str) -> dict[int, float]:
        """计算查询与各片段的 BM25 得分，只包含至少命中一个查询词的片段。"""
        scores: defaultdict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            for i, freq in self._postings.get(term, []):
                norm = self.k1 * (1 - self.b + self.b * self._doc_lens[i] / self._avgdl)
                scores[i] += self._idf[term] * freq * (self.k1 + 1) / (freq + norm)
        return dict(scores)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        ranked = sorted(self.get_scores(query).items(), key=lambda item: item[1], reverse=True)
        # 返回副本并附上得分，避免改动索引里的原始片段
        return [
            Document(
                page_content=self.docs[i].page_content,
                metadata={**self.docs[i].metadata, "score": round(score, 3)},
            )
            for i, score in ranked[: self.k]
        ]
