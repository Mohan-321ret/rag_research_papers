"""Language detection over cleaned document text."""

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

_SAMPLE_CHARS = 4000  # detection on a prefix is fast and accurate enough


@dataclass(frozen=True, slots=True)
class LanguageResult:
    language: str  # ISO 639-1 code, or "unknown"
    confidence: float


def detect_language(text: str) -> LanguageResult:
    sample = text[:_SAMPLE_CHARS].replace("\f", "\n").strip()
    if len(sample) < 20:
        return LanguageResult(language="unknown", confidence=0.0)

    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0  # make detection deterministic
        candidates = detect_langs(sample)
    except Exception as exc:
        logger.warning("language_detection_failed", error=type(exc).__name__)
        return LanguageResult(language="unknown", confidence=0.0)

    if not candidates:
        return LanguageResult(language="unknown", confidence=0.0)
    best = candidates[0]
    return LanguageResult(language=best.lang, confidence=round(best.prob, 4))
