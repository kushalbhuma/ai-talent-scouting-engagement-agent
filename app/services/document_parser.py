from __future__ import annotations

from pathlib import Path


class DocumentParser:
    def parse(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Job description file not found: {path}")

        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            return self._parse_pdf(path)
        raise ValueError("Unsupported JD file type. Use .txt, .md, or .pdf.")

    def _parse_pdf(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
