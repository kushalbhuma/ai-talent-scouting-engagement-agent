from pathlib import Path

from app.services.document_parser import DocumentParser


def test_document_parser_reads_text_file(tmp_path: Path) -> None:
    file_path = tmp_path / "jd.txt"
    file_path.write_text("Backend Engineer with Python and SQL", encoding="utf-8")

    parsed = DocumentParser().parse(str(file_path))

    assert "Backend Engineer" in parsed
