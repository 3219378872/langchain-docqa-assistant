"""文档加载与切分：把 PDF / Word / TXT / Markdown 文件转换为 LangChain 的 Document。"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import docx2txt
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

SUPPORTED_SUFFIXES = (".pdf", ".docx", ".txt", ".md")

# 中文友好的切分符：先按段落、换行切，再按句末标点切，最后才逐字切
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "!", "?", ";", "，", ",", " ", ""]


class DocumentFileLoader(BaseLoader):
    """按扩展名加载单个文件：PDF 每页生成一个 Document 并记录页码，其他格式整篇生成一个。"""

    def __init__(self, file_path: str | Path, source_name: str | None = None) -> None:
        self.file_path = Path(file_path)
        self.suffix = self.file_path.suffix.lower()
        if self.suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(
                f"不支持的文件类型：{self.file_path.name}（支持 {'、'.join(SUPPORTED_SUFFIXES)}）"
            )
        # 网页上传的文件会先存成临时文件，用 source_name 保留用户看到的原始文件名
        self.source_name = source_name or self.file_path.name

    def lazy_load(self) -> Iterator[Document]:
        if self.suffix == ".pdf":
            for page_number, page in enumerate(PdfReader(self.file_path).pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    yield Document(
                        page_content=text,
                        metadata={"source": self.source_name, "page": page_number},
                    )
            return
        if self.suffix == ".docx":
            text = docx2txt.process(str(self.file_path))
        else:
            text = read_text(self.file_path)
        if text.strip():
            yield Document(page_content=text.strip(), metadata={"source": self.source_name})


def read_text(path: Path) -> str:
    """读取文本文件：优先按 UTF-8 解码，失败再按 GB18030（兼容 Windows 下 GBK 编码的中文文件）。"""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="replace")


def collect_files(paths: Iterable[str | Path]) -> list[Path]:
    """展开路径列表：目录会递归查找其中所有受支持的文件。"""
    files: list[Path] = []
    for path in map(Path, paths):
        if path.is_dir():
            files.extend(
                sorted(
                    f
                    for f in path.rglob("*")
                    if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES
                )
            )
        else:
            files.append(path)
    return files


def load_documents(paths: Iterable[str | Path]) -> list[Document]:
    """加载多个文件（或目录）为 Document 列表。"""
    docs: list[Document] = []
    for path in collect_files(paths):
        docs.extend(DocumentFileLoader(path).load())
    return docs


def split_documents(
    docs: list[Document], chunk_size: int = 500, chunk_overlap: int = 80
) -> list[Document]:
    """把文档切成适合检索的小片段，并给每个片段编号。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        keep_separator="end",  # 句末标点留在上一句末尾，而不是挪到下一个片段开头
    )
    chunks = splitter.split_documents(docs)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
    return chunks
