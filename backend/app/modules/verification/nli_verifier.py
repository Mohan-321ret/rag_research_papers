"""Fact Verification — comparing a claim against its evidence.

A query-passage relevance model (Module 7's reranker) cannot tell "same
topic" from "same fact": "Employees receive 20 days of annual leave"
scores highly relevant against evidence that actually says 25 days,
because both sentences are about the same policy. Catching that class of
hallucination needs Natural Language Inference (NLI): does the evidence
(premise) entail, contradict, or stay neutral toward the claim
(hypothesis)?

``cross-encoder/nli-deberta-v3-xsmall`` outputs a 3-way softmax over
(contradiction, entailment, neutral). Module 9 (evidence verification)
uses the entailment probability as its 0-1 ``support_score``; Module 3
(knowledge evolution) reuses this same model and the contradiction
probability to detect conflicting claims across document versions — the
full 3-way breakdown is kept on every score so both can draw from it.

Two implementations behind one ``NliVerifier`` protocol, mirroring
``context_fusion/reranker.py``:

- ``CrossEncoderNliVerifier`` — the real model, lazily loaded and run off
  the event loop.
- ``PassthroughNliVerifier`` — used only when the NLI stack genuinely
  isn't installed; callers treat this the same as "verification disabled"
  rather than trusting a fabricated score.
"""

import asyncio
import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

VERDICT_LABELS = ("contradiction", "entailment", "neutral")


def nli_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


@dataclass(frozen=True, slots=True)
class NliScore:
    """The full 3-way softmax, plus the argmax verdict label."""

    contradiction: float
    entailment: float
    neutral: float
    verdict: str  # "contradiction" | "entailment" | "neutral"


class NliVerifier(Protocol):
    model_name: str

    async def score(self, premise: str, hypothesis: str) -> NliScore:
        """Does ``premise`` entail, contradict, or stay neutral toward
        ``hypothesis``?"""
        ...


class CrossEncoderNliVerifier:
    """Real NLI cross-encoder, loaded once and reused across requests."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = asyncio.Lock()

    async def _load(self):
        async with self._lock:
            if self._model is None:
                logger.info("nli_verifier_model_loading", model=self.model_name)
                self._model = await asyncio.to_thread(self._load_sync)
                logger.info("nli_verifier_model_loaded", model=self.model_name)
        return self._model

    def _load_sync(self):
        from sentence_transformers import CrossEncoder

        return CrossEncoder(self.model_name, device="cpu")

    async def score(self, premise: str, hypothesis: str) -> NliScore:
        model = await self._load()
        probs = await asyncio.to_thread(
            model.predict,
            [(premise, hypothesis)],
            apply_softmax=True,
            show_progress_bar=False,
        )
        row = probs[0]
        verdict = VERDICT_LABELS[int(row.argmax())]
        return NliScore(
            contradiction=float(row[0]),
            entailment=float(row[1]),
            neutral=float(row[2]),
            verdict=verdict,
        )


class PassthroughNliVerifier:
    """No-op stand-in for when the NLI stack isn't installed."""

    model_name = "none"

    async def score(self, premise: str, hypothesis: str) -> NliScore:
        raise NotImplementedError(
            "PassthroughNliVerifier cannot score claims — callers must check "
            "nli_available()/verification_enabled before invoking verification."
        )


@lru_cache
def get_nli_verifier(model_name: str | None = None, enabled: bool | None = None) -> NliVerifier:
    """Application-wide NLI verifier singleton.

    Takes hashable primitives (not the Settings object) so the result is
    cacheable, matching ``get_reranker``.
    """
    settings: Settings = get_settings()
    model_name = model_name or settings.verification_model_name
    enabled = settings.verification_enabled if enabled is None else enabled

    if not enabled or not nli_available():
        if enabled:
            logger.warning(
                "nli_verifier_unavailable",
                hint="install sentence-transformers to enable evidence verification",
            )
        return PassthroughNliVerifier()
    return CrossEncoderNliVerifier(model_name)
