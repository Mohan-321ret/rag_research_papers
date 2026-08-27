"""File type detection: magic bytes first, extension as a tiebreaker."""

import io
import zipfile
from enum import StrEnum

from app.core.exceptions import UnsupportedMediaTypeError


class FileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    XLSX = "xlsx"


_EXTENSION_MAP = {
    "pdf": FileType.PDF,
    "docx": FileType.DOCX,
    "txt": FileType.TXT,
    "text": FileType.TXT,
    "md": FileType.TXT,
    "log": FileType.TXT,
    "html": FileType.HTML,
    "htm": FileType.HTML,
    "xlsx": FileType.XLSX,
}

SUPPORTED_EXTENSIONS = sorted(_EXTENSION_MAP)


def _detect_zip_kind(content: bytes) -> FileType | None:
    """Distinguish OOXML containers (docx vs xlsx) by their internal layout."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return None
    if any(name.startswith("word/") for name in names):
        return FileType.DOCX
    if any(name.startswith("xl/") for name in names):
        return FileType.XLSX
    return None


def _looks_like_html(content: bytes) -> bool:
    head = content[:2048].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html")) or b"<html" in head


def detect_file_type(filename: str, content: bytes) -> FileType:
    """Determine the file type, trusting content over the extension.

    Raises ``UnsupportedMediaTypeError`` for anything outside the
    supported set (PDF, DOCX, TXT, HTML, XLSX).
    """
    if content.startswith(b"%PDF"):
        return FileType.PDF
    if content.startswith(b"PK\x03\x04"):
        zip_kind = _detect_zip_kind(content)
        if zip_kind is not None:
            return zip_kind
        raise UnsupportedMediaTypeError(
            "Unsupported archive format; only .docx and .xlsx containers are accepted"
        )
    if _looks_like_html(content):
        return FileType.HTML

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    detected = _EXTENSION_MAP.get(extension)
    if detected in (FileType.TXT, FileType.HTML):
        return detected

    # Extension claims a binary format but the magic bytes did not match.
    if detected is not None:
        raise UnsupportedMediaTypeError(
            f"File content does not match its .{extension} extension"
        )
    raise UnsupportedMediaTypeError(
        "Unsupported file type. Supported: " + ", ".join(SUPPORTED_EXTENSIONS)
    )
