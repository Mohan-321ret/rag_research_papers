"""OCR fallback for scanned PDFs.

Uses pypdfium2 to rasterize pages (no external poppler dependency) and
Tesseract via pytesseract for recognition. The Tesseract binary is an
external system dependency, so availability is probed at runtime and the
pipeline degrades gracefully (with a warning) when it is missing.
"""

from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)

_RENDER_SCALE = 2.0  # ~144 dpi; a reasonable speed/accuracy trade-off
_MAX_OCR_PAGES = 50


class TesseractOcrEngine:
    """OCR engine backed by the Tesseract binary."""

    @staticmethod
    @lru_cache
    def is_available() -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
        except Exception:
            return False
        return True

    def extract_pdf_text(self, content: bytes) -> str:
        """Rasterize each PDF page and run OCR over it."""
        import pypdfium2 as pdfium
        import pytesseract

        pdf = pdfium.PdfDocument(content)
        try:
            page_texts: list[str] = []
            for index, page in enumerate(pdf):
                if index >= _MAX_OCR_PAGES:
                    logger.warning("ocr_page_limit_reached", limit=_MAX_OCR_PAGES)
                    break
                bitmap = page.render(scale=_RENDER_SCALE)
                image = bitmap.to_pil()
                page_texts.append(pytesseract.image_to_string(image))
            # \f page separators mirror the native-extraction format.
            return "\f".join(page_texts).strip("\f").strip()
        finally:
            pdf.close()
