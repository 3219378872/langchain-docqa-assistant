import zipfile
from pathlib import Path

import pytest
from langchain_core.documents import Document

from docqa.loaders import DocumentFileLoader, collect_files, load_documents, split_documents


def make_pdf(path: Path, pages: list[str]) -> None:
    """手写一个最简单的多页 PDF（只含英文文本），测试时不必依赖额外的 PDF 生成库。"""
    font_id = 3 + 2 * len(pages)
    page_ids = [3 + 2 * i for i in range(len(pages))]
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>",
        font_id: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for page_id, text in zip(page_ids, pages, strict=True):
        stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents {page_id + 1} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        objects[page_id + 1] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"

    data = b"%PDF-1.4\n"
    offsets = {}
    for obj_id in sorted(objects):
        offsets[obj_id] = len(data)
        data += f"{obj_id} 0 obj\n{objects[obj_id]}\nendobj\n".encode()
    xref_offset = len(data)
    data += f"xref\n0 {font_id + 1}\n0000000000 65535 f \n".encode()
    data += "".join(f"{offsets[i]:010d} 00000 n \n" for i in range(1, font_id + 1)).encode()
    data += f"trailer\n<< /Size {font_id + 1} /Root 1 0 R >>\n".encode()
    data += f"startxref\n{xref_offset}\n%%EOF\n".encode()
    path.write_bytes(data)


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """生成只包含正文的最简 .docx（.docx 本质上是一个 zip 包）。"""
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)


def test_load_markdown(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# 标题\n\n正文内容\n", encoding="utf-8")
    assert DocumentFileLoader(path).load() == [
        Document(page_content="# 标题\n\n正文内容", metadata={"source": "note.md"})
    ]


def test_load_gbk_encoded_text(tmp_path):
    path = tmp_path / "gbk.txt"
    path.write_bytes("Windows 记事本保存的中文".encode("gbk"))
    assert DocumentFileLoader(path).load()[0].page_content == "Windows 记事本保存的中文"


def test_load_pdf_records_page_numbers(tmp_path):
    path = tmp_path / "upload.pdf"
    make_pdf(path, ["Hello PDF", "Second page"])
    docs = DocumentFileLoader(path, source_name="报告.pdf").load()
    assert [doc.metadata for doc in docs] == [
        {"source": "报告.pdf", "page": 1},
        {"source": "报告.pdf", "page": 2},
    ]
    assert "Hello PDF" in docs[0].page_content
    assert "Second page" in docs[1].page_content


def test_load_docx(tmp_path):
    path = tmp_path / "doc.docx"
    make_docx(path, ["第一段", "第二段"])
    docs = DocumentFileLoader(path).load()
    assert len(docs) == 1
    assert "第一段" in docs[0].page_content and "第二段" in docs[0].page_content


def test_empty_file_produces_no_documents(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("  \n", encoding="utf-8")
    assert DocumentFileLoader(path).load() == []


def test_unsupported_file_type(tmp_path):
    with pytest.raises(ValueError, match="不支持的文件类型"):
        DocumentFileLoader(tmp_path / "image.png")


def test_collect_files_from_directory(tmp_path):
    (tmp_path / "a.md").write_text("A", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("B", encoding="utf-8")
    (tmp_path / "skip.png").write_bytes(b"not a document")
    assert collect_files([tmp_path]) == [tmp_path / "a.md", tmp_path / "sub" / "b.txt"]
    assert [doc.page_content for doc in load_documents([tmp_path])] == ["A", "B"]


def test_split_documents_respects_sentences_and_keeps_metadata():
    text = "".join(f"第{i}句话的内容稍微长一些。" for i in range(60))
    chunks = split_documents(
        [Document(page_content=text, metadata={"source": "a.txt"})],
        chunk_size=100,
        chunk_overlap=20,
    )
    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= 100 for chunk in chunks)
    assert all(chunk.page_content.endswith("。") for chunk in chunks)  # 没有在句子中间断开
    assert all(chunk.metadata["source"] == "a.txt" for chunk in chunks)
    assert [chunk.metadata["chunk_id"] for chunk in chunks] == list(range(len(chunks)))
