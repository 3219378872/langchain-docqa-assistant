"""命令行版文档问答。

用法：
    python cli.py data/samples                       # 加载整个目录，进入交互式问答
    python cli.py 报告.pdf -q "这份报告的结论是什么？"   # 只回答一个问题
"""

from __future__ import annotations

import argparse
import operator
import sys
from functools import reduce

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable

from docqa import (
    BM25Retriever,
    Settings,
    build_llm,
    build_rag_chain,
    describe_source,
    load_documents,
    split_documents,
)


def ask(chain: Runnable, question: str, history: list[BaseMessage]) -> str:
    """流式打印回答和参考来源，并把这一轮对话追加到 history。"""
    chunks = []
    for chunk in chain.stream({"question": question, "chat_history": history}):
        chunks.append(chunk)
        if "answer" in chunk:
            print(chunk["answer"], end="", flush=True)
    print()
    result = reduce(operator.add, chunks)

    if result["standalone_question"].strip() != question:
        print(f"（检索用的问题：{result['standalone_question'].strip()}）")
    print("参考来源：" if result["docs"] else "参考来源：无")
    for i, doc in enumerate(result["docs"], start=1):
        print(f"  [{i}] {describe_source(doc)}（BM25 得分 {doc.metadata['score']}）")

    history += [HumanMessage(question), AIMessage(result["answer"])]
    return result["answer"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="智能文档问答助手（命令行版）")
    parser.add_argument("paths", nargs="+", help="文档或目录路径，支持 pdf、docx、txt、md")
    parser.add_argument("-q", "--question", help="只回答这一个问题，然后退出")
    parser.add_argument("-k", "--top-k", type=int, default=4, help="每次检索的片段数（默认 4）")
    parser.add_argument("--chunk-size", type=int, default=500, help="片段长度（默认 500 字符）")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        docs = load_documents(args.paths)
    except (ValueError, OSError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    if not docs:
        print("错误：没有从指定路径读取到任何文本内容", file=sys.stderr)
        return 1

    chunks = split_documents(docs, chunk_size=args.chunk_size)
    chain = build_rag_chain(build_llm(settings), BM25Retriever(docs=chunks, k=args.top_k))
    file_count = len({doc.metadata["source"] for doc in docs})
    print(f"已加载 {file_count} 个文件，共 {len(chunks)} 个片段。模型：{settings.model}")

    history: list[BaseMessage] = []
    if args.question:
        ask(chain, args.question, history)
        return 0

    print("输入问题开始提问，输入 exit 退出。")
    while True:
        try:
            question = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"exit", "quit", "q"}:
            return 0
        if question:
            print("助手：", end="", flush=True)
            ask(chain, question, history)


if __name__ == "__main__":
    sys.exit(main())
