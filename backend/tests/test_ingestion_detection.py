"""Unit tests for file type detection and extractor behavior."""

import io
import zipfile

import pytest

from app.core.exceptions import UnsupportedMediaTypeError
from app.modules.ingestion.detection import FileType, detect_file_type
from app.modules.ingestion.extractors import PdfExtractor


def _zip_with(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "x")
    return buffer.getvalue()


def test_detects_pdf_by_magic_bytes() -> None:
    assert detect_file_type("anything.bin", b"%PDF-1.7 ...") == FileType.PDF


def test_detects_docx_and_xlsx_by_zip_layout() -> None:
    assert detect_file_type("f.docx", _zip_with("word/document.xml")) == FileType.DOCX
    assert detect_file_type("f.xlsx", _zip_with("xl/workbook.xml")) == FileType.XLSX


def test_detects_html_by_content_even_with_txt_extension() -> None:
    html = b"<!doctype html><html><body>hi</body></html>"
    assert detect_file_type("page.txt", html) == FileType.HTML


def test_plain_text_falls_back_to_extension() -> None:
    assert detect_file_type("notes.txt", b"just some text") == FileType.TXT
    assert detect_file_type("notes.md", b"# heading") == FileType.TXT


def test_unsupported_type_raises() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        detect_file_type("app.exe", b"\x00\x01\x02binary")


def test_mismatched_binary_extension_raises() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        detect_file_type("fake.pdf", b"\x00\x01\x02 not a pdf")


def test_scanned_pdf_without_ocr_gets_warning(minimal_pdf_factory) -> None:
    extractor = PdfExtractor(ocr_engine=None)
    result = extractor.extract(minimal_pdf_factory(""))  # no text -> looks scanned
    assert result.text == ""
    assert any("OCR" in warning for warning in result.warnings)
